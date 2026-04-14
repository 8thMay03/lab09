# Báo Cáo Cá Nhân — Lab Day 09: Multi-Agent Orchestration

**Họ và tên:** Nguyễn Quang Minh
**Vai trò trong nhóm:** MCP Owner
**Ngày nộp:** 14/04/2026
**Độ dài yêu cầu:** 500–800 từ

---

> **Lưu ý quan trọng:**
> - Viết ở ngôi **"tôi"**, gắn với chi tiết thật của phần bạn làm
> - Phải có **bằng chứng cụ thể**: tên file, đoạn code, kết quả trace, hoặc commit
> - Nội dung phân tích phải khác hoàn toàn với các thành viên trong nhóm
> - Deadline: Được commit **sau 18:00** (xem SCORING.md)
> - Lưu file với tên: `reports/individual/[ten_ban].md` (VD: `nguyen_van_a.md`)

---

## 1. Tôi phụ trách phần nào? (100–150 từ)

> Mô tả cụ thể module, worker, contract, hoặc phần trace bạn trực tiếp làm.
> Không chỉ nói "tôi làm Sprint X" — nói rõ file nào, function nào, quyết định nào.

**Module/file tôi chịu trách nhiệm:**
- File chính: `mcp_server.py`
- Functions tôi implement: `tool_search_kb()` (modified), `create_app()` (new – HTTP MCP server optional)  

Khác với template gốc chỉ sử dụng retrieval worker như một abstraction, tôi refactor lại `tool_search_kb()` để **ưu tiên query trực tiếp ChromaDB**, sau đó mới fallback xuống retrieval worker, và cuối cùng mới fallback về mock data. Điều này giúp MCP server trở thành **entry point thực sự cho external capability**, thay vì chỉ là wrapper.

Ngoài ra, tôi bổ sung `create_app()` để expose MCP server qua FastAPI (optional advanced), cho phép worker gọi qua HTTP thay vì direct function call.

**Cách công việc của tôi kết nối với phần của thành viên khác:**

Policy worker sử dụng `dispatch_tool()` để gọi MCP thay vì truy cập trực tiếp ChromaDB. Điều này tách rõ dependency giữa worker và data layer.

**Bằng chứng (commit hash, file có comment tên bạn, v.v.):**

`mcp_server.py`

---

## 2. Tôi đã ra một quyết định kỹ thuật gì? (150–200 từ)

> Chọn **1 quyết định** bạn trực tiếp đề xuất hoặc implement trong phần mình phụ trách.
> Giải thích:
> - Quyết định là gì?
> - Các lựa chọn thay thế là gì?
> - Tại sao bạn chọn cách này?
> - Bằng chứng từ code/trace cho thấy quyết định này có effect gì?

**Quyết định:** Tôi chọn thiết kế `tool_search_kb()` theo mô hình **multi-level fallback (ChromaDB → retrieval worker → mock data)** thay vì chỉ dùng retrieval worker như template gốc.


**Ví dụ:**
> "Tôi chọn dùng keyword-based routing trong supervisor_node thay vì gọi LLM để classify.
>  Lý do: keyword routing nhanh hơn (~5ms vs ~800ms) và đủ chính xác cho 5 categories.
>  Bằng chứng: trace gq01 route_reason='task contains P1 SLA keyword', latency=45ms."

**Lý do:**

- Template gốc chỉ gọi `retrieve_dense()` → coupling chặt với worker layer  
- Tôi muốn MCP đóng vai trò **external capability thực sự**, nên phải có khả năng:
  1. Query trực tiếp DB (production-like)
  2. Reuse logic nội bộ (fallback)
  3. Fail gracefully (mock data)

Cách này giúp hệ thống resilient hơn khi:
- ChromaDB chưa init
- Retrieval worker lỗi
- Pipeline vẫn cần trả về kết quả để trace không bị crash

**Trade-off đã chấp nhận:**

- Code phức tạp hơn (nested try/except)
- Latency có thể tăng do nhiều fallback layer
- Harder to debug nếu không log rõ từng stage

**Bằng chứng từ trace/code:**

```
def tool_search_kb(query: str, top_k: int = 3) -> dict:
    """
    Tìm kiếm Knowledge Base bằng semantic search.

    TODO Sprint 3: Kết nối với ChromaDB thực.
    Hiện tại: Delegate sang retrieval worker.
    """
    try:
        # Try ChromaDB first
        import chromadb
        client = chromadb.PersistentClient(path="./chroma_db")
        collection = client.get_collection(name="day09_docs")

        results = collection.query(
            query_texts=[query],
            n_results=top_k
        )

        chunks = []
        for i in range(len(results["documents"][0])):
            chunks.append({
                "text": results["documents"][0][i],
                "source": results["metadatas"][0][i].get("source", "chroma"),
                "score": results["distances"][0][i],
            })

        return {
            "chunks": chunks,
            "sources": list({c["source"] for c in chunks}),
            "total_found": len(chunks),
        }
    except Exception as e:
        print(f"Error occurred while querying ChromaDB: {e}")
        # Fallback → existing retrieval worker
        try:
            # Tái dùng retrieval logic từ workers/retrieval.py
            import sys
            sys.path.insert(0, os.path.dirname(__file__))
            from workers.retrieval import retrieve_dense
            chunks = retrieve_dense(query, top_k=top_k)
            sources = list({c["source"] for c in chunks})
            return {
                "chunks": chunks,
                "sources": sources,
                "total_found": len(chunks),
            }
        except Exception as e:
            # Fallback: return mock data nếu ChromaDB chưa setup
            return {
                "chunks": [
                    {
                        "text": f"[MOCK] Không thể query ChromaDB: {e}. Kết quả giả lập.",
                        "source": "mock_data",
                        "score": 0.5,
                    }
                ],
                "sources": ["mock_data"],
                "total_found": 1,
            }
```

---

## 3. Tôi đã sửa một lỗi gì? (150–200 từ)

> Mô tả 1 bug thực tế bạn gặp và sửa được trong lab hôm nay.
> Phải có: mô tả lỗi, symptom, root cause, cách sửa, và bằng chứng trước/sau.

**Lỗi:** ModuleNotFoundError: workers.retrieval khi gọi fallback từ mcp_server.py

**Symptom (pipeline làm gì sai?):**

Khi ChromaDB chưa setup → fallback sang retrieval worker
Pipeline crash với lỗi import
Trace không ghi được mcp_tools_used

**Root cause (lỗi nằm ở đâu — indexing, routing, contract, worker logic?):**

mcp_server.py nằm ở root
workers/ là subfolder → Python không tự nhận path
Template gốc thiếu sys.path handling

**Cách sửa:**

Tôi thêm dynamic path injection trước khi import

**Bằng chứng trước/sau:**
> Dán trace/log/output trước khi sửa và sau khi sửa.

import sys
sys.path.insert(0, os.path.dirname(__file__))
from workers.retrieval import retrieve_dense

ModuleNotFoundError: No module named 'workers.retrieval'
PIPELINE_ERROR: search_kb failed

mcp_tool_called: search_kb
retrieved_sources: ["sla_p1_2026.txt"]
workers_called: ["policy_tool_worker", "synthesis_worker"]
---

## 4. Tôi tự đánh giá đóng góp của mình (100–150 từ)

> Trả lời trung thực — không phải để khen ngợi bản thân.

**Tôi làm tốt nhất ở điểm nào?**

Tôi thiết kế MCP server theo hướng gần production hơn template, đặc biệt là cơ chế fallback giúp pipeline không bị crash khi dependency fail.

**Tôi làm chưa tốt hoặc còn yếu ở điểm nào?**

Chưa implement logging chi tiết cho từng fallback stage, nên khi debug trace vẫn phải suy luận thay vì đọc log trực tiếp.

**Nhóm phụ thuộc vào tôi ở đâu?** _(Phần nào của hệ thống bị block nếu tôi chưa xong?)_

Policy worker phụ thuộc hoàn toàn vào MCP để gọi search_kb. Nếu MCP fail, toàn bộ policy reasoning sẽ bị block.

**Phần tôi phụ thuộc vào thành viên khác:** _(Tôi cần gì từ ai để tiếp tục được?)_

Tôi phụ thuộc vào retrieval worker (retrieve_dense) để làm fallback, và vào ChromaDB index từ Sprint 2 để query trực tiếp.

---

## 5. Nếu có thêm 2 giờ, tôi sẽ làm gì? (50–100 từ)

> Nêu **đúng 1 cải tiến** với lý do có bằng chứng từ trace hoặc scorecard.
> Không phải "làm tốt hơn chung chung" — phải là:
> *"Tôi sẽ thử X vì trace của câu gq___ cho thấy Y."*

Tôi sẽ thêm structured logging cho từng MCP tool call (ví dụ: stage=chroma|fallback|mock) vì trace hiện tại chỉ ghi mcp_tool_called mà không biết tool chạy ở layer nào.

Trong một số trace, khi sources=["mock_data"], không rõ do DB fail hay retrieval fail → gây khó debug accuracy issue.

---

*Lưu file này với tên: `reports/individual/[ten_ban].md`*  
*Ví dụ: `reports/individual/nguyen_van_a.md`*
