# Báo Cáo Cá Nhân — Lab Day 09: Multi-Agent Orchestration

**Họ và tên:** Nguyễn Quốc Khánh  
**Vai trò trong nhóm:** Supervisor Owner  
**Ngày nộp:** 14/04/2026  
**Độ dài yêu cầu:** 500–800 từ

---

## 1. Tôi phụ trách phần nào? (100–150 từ)

Tôi phụ trách phần điều phối trung tâm của pipeline multi-agent, tập trung vào `graph.py` (supervisor orchestrator) và liên quan tới contract trace xuất ra `artifacts/traces/*.json`. Các hàm tôi trực tiếp implement/chỉnh gồm `supervisor_node()`, `_should_route_policy_tool()`, `_policy_route_reason()`, `route_decision()`, `build_trace_record()` và `save_trace()`.  

Mục tiêu phần của tôi là đảm bảo mỗi task được route đúng worker, có `route_reason` giải thích được, và kết quả cuối có log đủ để debug theo từng bước (`workers_called`, `mcp_tool_calls`, `latency_ms`, `worker_io_logs`). Phần này kết nối trực tiếp với Worker Owner (retrieval/policy/synthesis) vì nếu route sai thì worker tốt cũng không cứu được chất lượng answer; đồng thời kết nối với MCP Owner vì `needs_tool` quyết định có gọi `search_kb`/`get_ticket_info` hay không.

**Module/file tôi chịu trách nhiệm:**
- File chính: `graph.py`
- Functions tôi implement: `supervisor_node`, `_should_route_policy_tool`, `_policy_route_reason`, `build_trace_record`, `save_trace`

**Cách công việc của tôi kết nối với phần của thành viên khác:**

Supervisor nhận task, chọn đường đi, rồi chuyển state đúng contract cho worker; worker trả output nào cũng được chuẩn hóa lại vào trace để Trace/Docs Owner có thể chấm và phân tích.

**Bằng chứng (commit hash, file có comment tên bạn, v.v.):**

Comment đầu file `graph.py` ghi rõ phạm vi Sprint 1–2 cho supervisor; các trace như `run_20260414_160621.json`, `run_20260414_160624.json`, `run_20260414_160705.json` đều chứa `supervisor_route` và `route_reason` theo logic tôi viết.

---

## 2. Tôi đã ra một quyết định kỹ thuật gì? (150–200 từ)

**Quyết định:** Tôi chọn chiến lược routing dạng hybrid rule-based có factual override trong `supervisor_node()` thay vì route thuần keyword hoặc dùng classifier LLM.

**Lý do:**

Trong bộ câu hỏi lab có nhiều câu lai giữa factual và policy. Nếu route thuần keyword, câu “hoàn tiền trong bao nhiêu ngày” dễ bị đẩy sang `policy_tool_worker`, làm tăng MCP call không cần thiết. Tôi thêm nhánh override trong `supervisor_node()` để nhận diện câu factual kiểu “bao nhiêu ngày/mấy ngày” và giữ route ở `retrieval_worker`, đồng thời vẫn để `_should_route_policy_tool()` bắt các case access/escalation/flash sale/temporal exception.

**Trade-off đã chấp nhận:**

Tôi chấp nhận chi phí bảo trì rule thủ công (phải cập nhật keyword và heuristic) để đổi lấy tốc độ và traceability. Rule-based cho `route_reason` rất rõ, dễ review theo từng run; nhược điểm là có thể miss các phrasing mới nếu ngoài coverage hiện tại.

**Bằng chứng từ trace/code:**

```python
# graph.py (supervisor_node)
elif ("hoàn tiền" in t or "refund" in t) and any(
    x in t for x in ["bao nhiêu ngày", "trong bao nhiêu ngày", "bao lâu", "mấy ngày"]
):
    route = "retrieval_worker"
    route_parts.append("factual refund window / days → retrieval (not policy-only)")
```

`run_20260414_160621.json` cho thấy câu refund-window được route `retrieval_worker`; trong khi `run_20260414_160624.json` và `run_20260414_160705.json` được route `policy_tool_worker` với `needs_tool=true` và có MCP calls đúng ngữ cảnh.

---

## 3. Tôi đã sửa một lỗi gì? (150–200 từ)

**Lỗi:** Supervisor route sai nhóm câu refund factual sang policy path, làm pipeline chậm và nhiễu source.

**Symptom (pipeline làm gì sai?):**

Ở bản route trước khi thêm override, câu hỏi factual dạng “bao nhiêu ngày” thường vào `policy_tool_worker`, kéo theo `search_kb` dù không cần. Hậu quả là latency tăng và đôi khi answer mang thêm điều kiện policy dài dòng thay vì trả fact ngắn, làm confidence dao động.

**Root cause (lỗi nằm ở đâu — indexing, routing, contract, worker logic?):**

Root cause nằm ở routing logic của supervisor: điều kiện `if "hoàn tiền" in t or "refund" in t` quá rộng, không tách câu factual khỏi câu policy/exception. Đây là lỗi phân loại tuyến xử lý, không phải lỗi retrieval index hay synthesis.

**Cách sửa:**

Tôi sửa trong `supervisor_node()` bằng cách thêm nhánh ưu tiên factual refund-window trước khi gọi `_should_route_policy_tool()`. Đồng thời giữ logic policy route cho các câu có dấu hiệu exception (flash sale, temporal scope 31/01-01/02, license).

**Bằng chứng trước/sau:**
> Dán trace/log/output trước khi sửa và sau khi sửa.

Sau sửa, `run_20260414_160621.json` có `route_reason = "factual refund window / days → retrieval (not policy-only)"`, `workers_called = ["retrieval_worker","synthesis_worker"]`, `mcp_tools_used = []`, `latency_ms = 2499`.  
Trong khi các câu policy thực sự vẫn đi đúng nhánh: `run_20260414_160646.json` route `policy_tool_worker` với `route_reason` liên quan flash sale/exception và có `mcp_tools_used = ["search_kb"]`.

---

## 4. Tôi tự đánh giá đóng góp của mình (100–150 từ)

**Tôi làm tốt nhất ở điểm nào?**

Tôi làm tốt ở việc giữ supervisor logic “giải thích được”: mỗi route đều có `route_reason` và dấu vết rõ trong `history`, giúp debug nhanh khi QA fail. Tôi cũng chủ động chuẩn hóa trace fields để đội trace/docs đọc được ngay mà không cần map thủ công.

**Tôi làm chưa tốt hoặc còn yếu ở điểm nào?**

Tôi vẫn phụ thuộc khá nhiều vào keyword/rule tay; coverage chưa đủ bền với các cách diễn đạt lạ. Một số run đúng nội dung nhưng confidence thấp cho thấy tôi chưa phối hợp đủ sớm với worker side về chiến lược calibration confidence.

**Nhóm phụ thuộc vào tôi ở đâu?** _(Phần nào của hệ thống bị block nếu tôi chưa xong?)_

Nếu supervisor và trace contract chưa ổn định, nhóm không thể chấm đúng theo worker path, khó tách lỗi route hay lỗi worker.

**Phần tôi phụ thuộc vào thành viên khác:** _(Tôi cần gì từ ai để tiếp tục được?)_

Tôi phụ thuộc vào Worker/MCP Owner ở chất lượng output của từng worker và độ đúng của tool result; supervisor chỉ route tốt khi contract input-output phía sau nhất quán.

---

## 5. Nếu có thêm 2 giờ, tôi sẽ làm gì? (50–100 từ)

Tôi sẽ thêm một lớp “source-domain guard” ngay ở supervisor/policy path để lọc chunk lệch domain trước synthesis, vì trace `run_20260414_160624.json` cho thấy câu hỏi cấp quyền Level 3 vẫn kéo `hr/leave-policy-2026.pdf` vào `sources`, làm confidence chỉ 0.15 dù answer đúng. Cải tiến này giúp giảm nhiễu bằng chứng và làm confidence phản ánh chất lượng thực hơn.

