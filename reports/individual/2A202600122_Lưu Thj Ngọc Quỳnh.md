# Báo Cáo Cá Nhân — Lab Day 09: Multi-Agent Orchestration

**Họ và tên:** Lưu Thị Ngọc Quỳnh
**Vai trò trong nhóm:** Suoervisor Owner, Trace & Docs Owner  
**Ngày nộp:** 14 - 04 - 2026
**Độ dài yêu cầu:** 500 - 800 từ

---

## 1. Tôi phụ trách phần nào? (100–150 từ)

**Module/file tôi chịu trách nhiệm:**
- File chính: `Routing_decisions.md`, `graph.py`
- Functions tôi implement: `# 4. Worker nodes (gọi workers thật)`, `5. Graph`

**Cách công việc của tôi kết nối với phần của thành viên khác:**
Tôi phụ trách lớp supervisor orchestration và phần trace của hệ thống. Trong `graph.py`, tôi nối supervisor với các worker thật qua `retrieval_worker_node`, `policy_tool_worker_node`, `synthesis_worker_node`, rồi viết lại `build_graph()` theo flow: supervisor -> worker phù hợp -> synthesis. Phần này kết nối trực tiếp với code của các bạn làm worker trong thư mục `workers/`, vì nếu graph không gọi đúng `run(state)` thì retrieval, policy check và synthesis không đi vào pipeline thật. Ở phía docs, tôi dùng `docs/routing_decisions.md` để ghi lại route và lý do route, sau đó đối chiếu với `supervisor_route`, `route_reason`, `workers_called` trong trace.

**Bằng chứng (commit hash, file có comment tên bạn, v.v.):**
- Commit `c883baa` với message `graph` do tôi commit ngày 14/04/2026.
- Trong diff commit này, tôi thay các placeholder ở `graph.py` bằng lời gọi worker thật: `return retrieval_run(state)`, `return policy_tool_run(state)`, `return synthesis_run(state)`.
- Tôi cũng thêm phần lưu trace chuẩn trong `build_trace_record()` và `save_trace()`, gồm các field như `supervisor_route`, `route_reason`, `workers_called`, `mcp_tools_used`, `confidence`, `latency_ms`.

---

## 2. Tôi đã ra một quyết định kỹ thuật gì? (150–200 từ)

**Quyết định:** Tôi tách riêng nhóm câu hỏi "refund dạng fact" như "khách hàng có thể yêu cầu hoàn tiền trong bao nhiêu ngày?" sang `retrieval_worker` thay vì route hết các câu có từ "refund/hoàn tiền" vào `policy_tool_worker`.

**Lý do:**
Tôi nhận ra không phải mọi câu có từ "refund" đều là policy exception. Một số câu chỉ cần truy xuất fact đơn giản từ tài liệu, ví dụ số ngày được hoàn tiền. Nếu route tất cả qua `policy_tool_worker`, supervisor sẽ bật `needs_tool=True` và kéo thêm policy analysis hoặc MCP không cần thiết. Vì vậy tôi thêm một nhánh ưu tiên trong `supervisor_node()` để bắt các mẫu `"bao nhiêu ngày"`, `"bao lâu"`, `"mấy ngày"` đi cùng `"hoàn tiền"` hoặc `"refund"`, rồi route thẳng sang retrieval. Quyết định này cũng khớp với `data/test_questions.json`, vì câu `q02` có expected route là `retrieval_worker`.

**Trade-off đã chấp nhận:**
Trade-off là logic supervisor dài hơn và phụ thuộc vào pattern thủ công. Cách này nhanh, dễ debug và khớp bộ test lab, nhưng nếu câu hỏi diễn đạt quá khác mẫu thì có thể route sai.

**Bằng chứng từ trace/code:**

``` 
elif ("hoàn tiền" in t or "refund" in t) and any(
    x in t for x in ["bao nhiêu ngày", "trong bao nhiêu ngày", "bao lâu", "mấy ngày"]
):
    route = "retrieval_worker"
    route_parts.append("factual refund window / days → retrieval (not policy-only)")
elif _should_route_policy_tool(t):
    route = "policy_tool_worker"

Trong `data/test_questions.json`, câu `q02` là:
"Khách hàng có thể yêu cầu hoàn tiền trong bao nhiêu ngày?"
expected_route = "retrieval_worker"
```

---

## 3. Tôi đã sửa một lỗi gì? (150–200 từ)

**Lỗi:** `graph.py` vẫn dùng worker placeholder thay vì gọi worker thật, làm cho pipeline chạy "được" nhưng không chạy đúng kiến trúc supervisor-worker của nhóm.

**Symptom (pipeline làm gì sai?):**
Graph tự ghi dữ liệu giả vào state. `retrieval_worker_node()` trả về một chunk mẫu về SLA P1, `policy_tool_worker_node()` tạo `policy_result` mặc định, còn `synthesis_worker_node()` trả lời theo mẫu `[PLACEHOLDER]...`. Nghĩa là supervisor có route khác nhau nhưng output cuối vẫn không phản ánh worker thật.

**Root cause (lỗi nằm ở đâu — indexing, routing, contract, worker logic?):**
Root cause nằm ở orchestration layer trong `graph.py`, không phải ở index hay worker logic. Các import worker thật vẫn còn bị comment, trong khi các wrapper node chỉ append log rồi trả output mẫu.

**Cách sửa:**
Tôi thay toàn bộ placeholder wrapper bằng lời gọi trực tiếp tới worker thật: `return retrieval_run(state)`, `return policy_tool_run(state)`, `return synthesis_run(state)`. Sau đó tôi viết lại `build_graph()` để route xong thì gọi worker tương ứng, nếu policy worker chưa có `retrieved_chunks` thì fallback sang retrieval, rồi luôn synthesis ở cuối. Tôi cũng bổ sung `build_trace_record()` và `save_trace()` để trace sau khi sửa phản ánh đúng pipeline thực tế.

**Bằng chứng trước/sau:**
Trước khi sửa, trong version trước commit `c883baa`:

```python
# TODO Sprint 2: Thay bằng retrieval_run(state)
state["retrieved_chunks"] = [
    {"text": "SLA P1: phản hồi 15 phút, xử lý 4 giờ.", "source": "sla_p1_2026.txt", "score": 0.92}
]
state["final_answer"] = f"[PLACEHOLDER] Câu trả lời được tổng hợp từ {len(chunks)} chunks."
```

Sau khi sửa, trong commit `c883baa`:

```python
def retrieval_worker_node(state: AgentState) -> AgentState:
    return retrieval_run(state)

def policy_tool_worker_node(state: AgentState) -> AgentState:
    return policy_tool_run(state)

def synthesis_worker_node(state: AgentState) -> AgentState:
    return synthesis_run(state)
```

---

## 4. Tôi tự đánh giá đóng góp của mình (100–150 từ)

**Tôi làm tốt nhất ở điểm nào?**
Tôi làm tốt nhất ở chỗ biến phần supervisor từ mô tả trong README thành orchestration có thể trace được. Tôi không chỉ route task mà còn để lại `route_reason`, `workers_called`, `needs_tool`, `latency_ms`, nên khi nhóm debug có thể biết pipeline đi nhánh nào và vì sao.

**Tôi làm chưa tốt hoặc còn yếu ở điểm nào?**
Điểm tôi còn yếu là phần hoàn thiện cuối chưa đủ kỹ. Tôi đã nối được graph với worker thật và trace format, nhưng vẫn còn chỗ cần rà thêm như import, merge log, và kiểm thử end-to-end để tránh lỗi runtime.

**Nhóm phụ thuộc vào tôi ở đâu?** _(Phần nào của hệ thống bị block nếu tôi chưa xong?)_
Nhóm phụ thuộc vào tôi ở lớp orchestration. Nếu tôi chưa xong `graph.py`, các worker dù viết đúng vẫn không đi vào pipeline chung; phần trace/doc cũng không có dữ liệu chuẩn để đối chiếu.

**Phần tôi phụ thuộc vào thành viên khác:** _(Tôi cần gì từ ai để tiếp tục được?)_
Tôi phụ thuộc vào các bạn làm `workers/retrieval.py`, `workers/policy_tool.py`, `workers/synthesis.py` và MCP mock. Supervisor chỉ route tốt khi contract đầu vào/đầu ra của các worker ổn định.

---

## 5. Nếu có thêm 2 giờ, tôi sẽ làm gì? (50–100 từ)

Nếu có thêm 2 giờ, tôi sẽ ưu tiên viết một vòng kiểm thử end-to-end cho riêng `graph.py` với các câu `q02`, `q13`, `q15`. Lý do là code hiện có nhiều nhánh routing tinh chỉnh cho refund fact, access control và multi-hop P1, nhưng các nhánh này chỉ có giá trị khi được chạy xuyên suốt qua worker thật và lưu trace ổn định.
