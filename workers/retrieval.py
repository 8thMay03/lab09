"""
workers/retrieval.py — Retrieval Worker
Sprint 2: Implement retrieval từ ChromaDB, trả về chunks + sources.

Input (từ AgentState):
    - task: câu hỏi cần retrieve
    - (optional) retrieved_chunks nếu đã có từ trước

Output (vào AgentState):
    - retrieved_chunks: list of {"text", "source", "score", "metadata"}
    - retrieved_sources: list of source filenames
    - worker_io_log: log input/output của worker này

Gọi độc lập để test:
    python workers/retrieval.py
"""

import os
import sys
import re
from dotenv import load_dotenv
from pathlib import Path

CHROMA_DB_DIR = Path(__file__).parent.parent / "chroma_db"


load_dotenv(override=True)

# ─────────────────────────────────────────────
# Worker Contract (xem contracts/worker_contracts.yaml)
# Input:  {"task": str, "top_k": int = 3}
# Output: {"retrieved_chunks": list, "retrieved_sources": list, "error": dict | None}
# ─────────────────────────────────────────────

WORKER_NAME = "retrieval_worker"
DEFAULT_TOP_K = 3

_model = None

def _get_embedding_fn():
    """
    Trả về embedding function.
    TODO Sprint 1: Implement dùng OpenAI hoặc Sentence Transformers.
    """
    global _model

    # Option A: Sentence Transformers (offline, không cần API key)
    try:
        from sentence_transformers import SentenceTransformer

        if _model is None:
            print("🔄 Loading embedding model (once)...")
            _model = SentenceTransformer("all-MiniLM-L6-v2")

        def embed(text: str) -> list:
            return _model.encode([text])[0].tolist()
        return embed
    except ImportError:
        pass

    # Option B: OpenAI (cần API key)
    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        def embed(text: str) -> list:
            resp = client.embeddings.create(input=text, model="text-embedding-3-small")
            return resp.data[0].embedding
        return embed
    except ImportError:
        pass

    # Fallback: random embeddings cho test (KHÔNG dùng production)
    import random
    def embed(text: str) -> list:
        return [random.random() for _ in range(384)]
    print("⚠️  WARNING: Using random embeddings (test only). Install sentence-transformers.")
    return embed


def _get_collection():
    """
    Kết nối ChromaDB collection.
    TODO Sprint 2: Đảm bảo collection đã được build từ Step 3 trong README.
    """
    import chromadb
    client = chromadb.PersistentClient(path="./chroma_db")
    try:
        collection = client.get_collection("day09_docs")
    except Exception:
        # Auto-create nếu chưa có
        collection = client.get_or_create_collection(
            "day09_docs",
            metadata={"hnsw:space": "cosine"}
        )
        print(f"⚠️  Collection 'day09_docs' chưa có data. Chạy index script trong README trước.")
    return collection


def retrieve_dense(query: str, top_k: int = DEFAULT_TOP_K) -> list:
    """
    Dense retrieval: embed query → query ChromaDB → trả về top_k chunks.

    TODO Sprint 2: Implement phần này.
    - Dùng _get_embedding_fn() để embed query
    - Query collection với n_results=top_k
    - Format result thành list of dict

    Returns:
        list of {"text": str, "source": str, "score": float, "metadata": dict}
    """
    # TODO: Implement dense retrieval
    embed = _get_embedding_fn()
    query_embedding = embed(query)

    try:
        collection = _get_collection()
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents", "distances", "metadatas"]
        )

        chunks = []
        for i, (doc, dist, meta) in enumerate(zip(
            results["documents"][0],
            results["distances"][0],
            results["metadatas"][0]
        )):
            # Chroma cosine distance: 0 = giống nhất; có thể >1 → clamp similarity về [0,1]
            sim = max(0.0, min(1.0, 1.0 - float(dist)))
            chunks.append({
                "text": doc,
                "source": meta.get("source", "unknown"),
                "score": round(sim, 4),
                "metadata": meta,
            })
        return chunks

    except Exception as e:
        print(f"⚠️  ChromaDB query failed: {e}")
        # Fallback: return empty (abstain)
        return []


def _tokenize(text: str) -> list[str]:
    """Tokenize đơn giản cho sparse retrieval."""
    return re.findall(r"\w+", (text or "").lower())


def retrieve_sparse(query: str, top_k: int = DEFAULT_TOP_K, candidate_limit: int = 200) -> list:
    """
    Sparse retrieval (BM25-lite): lấy candidate từ Chroma collection.get(),
    chấm điểm bằng token overlap có trọng số query-term coverage.
    """
    try:
        collection = _get_collection()
        all_docs = collection.get(
            include=["documents", "metadatas"],
            limit=candidate_limit,
        )
        docs = all_docs.get("documents") or []
        metas = all_docs.get("metadatas") or []
        if not docs:
            return []

        query_tokens = _tokenize(query)
        if not query_tokens:
            return []
        q_unique = set(query_tokens)

        scored = []
        for doc, meta in zip(docs, metas):
            text_tokens = _tokenize(doc)
            if not text_tokens:
                continue
            token_set = set(text_tokens)
            overlap = q_unique.intersection(token_set)
            if not overlap:
                continue

            # coverage ưu tiên số lượng term query match; density nhẹ để tránh bias doc dài
            coverage = len(overlap) / max(1, len(q_unique))
            density = len(overlap) / max(20, len(token_set))
            sparse_score = min(1.0, coverage * 0.85 + density * 0.15)
            scored.append(
                {
                    "text": doc,
                    "source": (meta or {}).get("source", "unknown"),
                    "score": round(sparse_score, 4),
                    "metadata": meta or {},
                }
            )

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]
    except Exception as e:
        print(f"⚠️  Sparse retrieval failed: {e}")
        return []


def retrieve_hybrid(query: str, top_k: int = DEFAULT_TOP_K) -> list:
    """
    Hybrid retrieval: dense + sparse, fusion bằng Reciprocal Rank Fusion (RRF).
    """
    dense = retrieve_dense(query, top_k=max(top_k * 2, 6))
    sparse = retrieve_sparse(query, top_k=max(top_k * 2, 6))

    # Merge key: source + prefix text để dedupe
    def key_of(chunk: dict) -> str:
        text_prefix = (chunk.get("text", "") or "")[:120]
        return f"{chunk.get('source', 'unknown')}::{text_prefix}"

    rank_fused = {}
    base_payload = {}
    k = 60  # RRF constant

    for rank, c in enumerate(dense, start=1):
        ck = key_of(c)
        rank_fused[ck] = rank_fused.get(ck, 0.0) + (1.0 / (k + rank))
        base_payload.setdefault(ck, c)
    for rank, c in enumerate(sparse, start=1):
        ck = key_of(c)
        rank_fused[ck] = rank_fused.get(ck, 0.0) + (1.0 / (k + rank))
        base_payload.setdefault(ck, c)

    if not rank_fused:
        return []

    max_rrf = max(rank_fused.values())
    merged = []
    for ck, rrf_score in rank_fused.items():
        payload = dict(base_payload[ck])
        payload["score"] = round(rrf_score / max_rrf, 4)
        merged.append(payload)

    merged.sort(key=lambda x: x["score"], reverse=True)
    return merged[:top_k]


def run(state: dict) -> dict:
    """
    Worker entry point — gọi từ graph.py.

    Args:
        state: AgentState dict

    Returns:
        Updated AgentState với retrieved_chunks và retrieved_sources
    """
    task = state.get("task", "")
    top_k = state.get("retrieval_top_k", DEFAULT_TOP_K)

    state.setdefault("workers_called", [])
    state.setdefault("history", [])

    state["workers_called"].append(WORKER_NAME)

    # Log worker IO (theo contract)
    worker_io = {
        "worker": WORKER_NAME,
        "input": {"task": task, "top_k": top_k},
        "output": None,
        "error": None,
    }

    try:
        # Hybrid retrieval mặc định để tăng recall + precision cho multi-hop/policy queries.
        chunks = retrieve_hybrid(task, top_k=top_k)

        sources = list({c["source"] for c in chunks})

        state["retrieved_chunks"] = chunks
        state["retrieved_sources"] = sources

        worker_io["output"] = {
            "chunks_count": len(chunks),
            "sources": sources,
        }
        state["history"].append(
            f"[{WORKER_NAME}] retrieved {len(chunks)} chunks from {sources}"
        )

    except Exception as e:
        worker_io["error"] = {"code": "RETRIEVAL_FAILED", "reason": str(e)}
        state["retrieved_chunks"] = []
        state["retrieved_sources"] = []
        state["history"].append(f"[{WORKER_NAME}] ERROR: {e}")

    # Ghi worker IO vào state để trace
    state.setdefault("worker_io_logs", []).append(worker_io)


    return state


# ─────────────────────────────────────────────
# Test độc lập
# ─────────────────────────────────────────────


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    print("=" * 50)
    print("Retrieval Worker — Standalone Test")
    print("=" * 50)

    test_queries = [
        "SLA ticket P1 là bao lâu?",
        "Điều kiện được hoàn tiền là gì?",
        "Ai phê duyệt cấp quyền Level 3?",
    ]

    for query in test_queries:
        print(f"\n>> Query: {query}")
        result = run({"task": query})
        chunks = result.get("retrieved_chunks", [])
        print(f"  Retrieved: {len(chunks)} chunks")
        for c in chunks[:2]:
            print(f"    [{c['score']:.3f}] {c['source']}: {c['text'][:80]}...")
        print(f"  Sources: {result.get('retrieved_sources', [])}")

    print("\n✅ retrieval_worker test done.")

