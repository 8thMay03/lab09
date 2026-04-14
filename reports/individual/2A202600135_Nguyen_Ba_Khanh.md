# Báo Cáo Cá Nhân — Lab Day 09: Multi-Agent Orchestration

**Họ và tên:** Nguyễn Bá Khánh  
**Vai trò trong nhóm:** Supervisor Owner 
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
- File chính: `graph.py`
- Functions tôi implement: '2. Supervisor' , ' 1. Shared State — dữ liệu đi xuyên toàn graph', '3. Human Review (HITL placeholder)'

**Cách công việc của tôi kết nối với phần của thành viên khác:**

Với tư cách là người thiết kế Supervisor và luồng chạy chính, công việc của tôi là "trạm kiểm soát" cho các worker do các bạn khác làm (Retrieval Worker, Policy Tool Worker, Synthesis Worker). 
- `AgentState` mà tôi thiết kế quy định format chung (như biến `retrieved_chunks`, `policy_result`, v.v.) bắt buộc các worker khác phải tuân thủ để nhận và trả dữ liệu.
- Hàm `supervisor_node` quyết định xem với câu hỏi nào, luồng sẽ rẽ sang worker nào tiếp theo, từ đó kích hoạt đúng worker cần thiết (VD: câu liên quan SLA rẽ sang Retrieval, câu có liên quan "hoàn tiền flash sale" rẽ sang Policy Tool).

**Bằng chứng (commit hash, file có comment tên bạn, v.v.):**

graph.py, 4074785e6d62e5c862bd1eac8faad0e173c9a044

---

## 2. Tôi đã ra một quyết định kỹ thuật gì? (150–200 từ)

> Chọn **1 quyết định** bạn trực tiếp đề xuất hoặc implement trong phần mình phụ trách.
> Giải thích:
> - Quyết định là gì?
> - Các lựa chọn thay thế là gì?
> - Tại sao bạn chọn cách này?
> - Bằng chứng từ code/trace cho thấy quyết định này có effect gì?

**Quyết định:** Viết deterministic keyword-based routing theo dạng if/elif cho `supervisor_node` thay vì dùng AI Classifier, đồng thời tích hợp mảng `route_parts` để lưu giữ toàn bộ lý do điều hướng.

**Lý do:**
Việc gọi API qua LLM để phân loại "câu nào vào worker nào" tuy linh hoạt nhưng tốn thêm 1-2 giây latency cho mỗi query và chi phí token vô ích. Dựa trên phân tích test queries, các luồng nghiệp vụ IT helpdesk đều có keyword đặc trưng (như `err-`, `hoàn tiền`, `p1`, `khẩn cấp`). Việc dùng `if/elif` chuỗi từ khóa vừa cắt giảm độ trễ Supervisor xuống gần 0ms, vừa chính xác cao.
Hơn nữa, thay vì ghi đè lý do, tôi dùng mảng `route_parts` để `append()` từng quyết định. Ví dụ nếu cần Tool, tự động `route_parts.append("MCP enabled...")` mà không bị xoá lý do gốc.

**Trade-off đã chấp nhận:**
Logic routing bị "hard-code", dẫn đến file phình to nếu mảng keyword dài. Khi update quy trình mới, engineer phải cập nhật file core thủ công thay vì update prompt. 

**Bằng chứng từ trace/code:**
"""
def supervisor_node(state: AgentState) -> AgentState:
    task_raw = state["task"]
    t = task_raw.lower()

    state["history"].append(f"[supervisor] received task: {task_raw[:80]}")

    route = "retrieval_worker"
    route_parts: list[str] = []
    needs_tool = False
    risk_high = any(
        kw in t for kw in ["khẩn cấp", "emergency", "2am", "2 am", "contractor"]
    )

    if "err-" in t:
        route = "retrieval_worker"
        route_parts.append("task contains ERR-* → retrieval (docs / abstain)")
    elif ("hoàn tiền" in t or "refund" in t) and any(
        x in t for x in ["bao nhiêu ngày", "trong bao nhiêu ngày", "bao lâu", "mấy ngày"]
    ):
        route = "retrieval_worker"
        route_parts.append("factual refund window / days → retrieval (not policy-only)")
    elif _should_route_policy_tool(t):
        route = "policy_tool_worker"
        needs_tool = True
        route_parts.append(_policy_route_reason(t))
    elif any(
        kw in t for kw in ["p1", "escalation", "sla", "ticket", "sự cố", "incident"]
    ):
        route = "retrieval_worker"
        route_parts.append("P1 / SLA / ticket / incident keywords → retrieval")
    else:
        route = "retrieval_worker"
        route_parts.append("default → retrieval_worker")

    if needs_tool:
        route_parts.append(
            "MCP enabled: policy worker uses search_kb / get_ticket_info (not direct Chroma in policy)"
        )

    state["supervisor_route"] = route
    state["route_reason"] = " | ".join(route_parts)
    state["needs_tool"] = needs_tool
    state["risk_high"] = risk_high
    state["history"].append(
        f"[supervisor] route={route} reason={state['route_reason']}"
    )

    return state
    """
```

---

## 3. Tôi đã sửa một lỗi gì? (150–200 từ)

> Mô tả 1 bug thực tế bạn gặp và sửa được trong lab hôm nay.

**Lỗi:** Supervisor phân loại sai luồng (Misroute) đối với câu hỏi "Khách hàng có thể yêu cầu hoàn tiền trong bao nhiêu ngày?".

**Symptom (pipeline làm gì sai?):**
Câu hỏi dạng "hoàn tiền trong bao nhiêu ngày" chạy sai vào `policy_tool_worker` nhưng Tool lại không tìm thấy ngoại lệ (exception) hay điều kiện, trả về answer kém tập trung, latency rất lâu do gọi tool không cần thiết (tốn ~6 giây thay vì 2 giây).

**Root cause (lỗi nằm ở đâu — indexing, routing, contract, worker logic?):**
Lỗi nằm ở hàm routing. Hàm check Policy `_should_route_policy_tool(t)` chỉ bắt chữ `"hoàn tiền"`, do đó bất kể câu hỏi có phải lấy mốc ngày luật chung (factual) hay hỏi có được hoàn không, đều bị tống sang Policy Worker.

**Cách sửa:**
Thêm một luồng `elif` ưu tiên với cụm điều kiện ghép: vừa chứa `"hoàn tiền"` VÀ chứa `"trong bao nhiêu ngày"|"mấy ngày"`, nếu đúng thì bắt buộc rẽ sang `retrieval_worker` với cờ `"factual refund window / days → retrieval (not policy-only)"`. Luồng `elif` này được đặt ngay trước luồng `_should_route_policy_tool`.

**Bằng chứng trước/sau:**
> Trước khi sửa: `Route: policy_tool_worker` (nhận diện nhầm là logic check điều kiện).
> Sau khi sửa: Xem trace của q02 (Khách hàng có thể yêu cầu hoàn tiền trong bao nhiêu ngày?):
> `[supervisor] route=retrieval_worker reason=factual refund window / days → retrieval`
> `Answer đúng hạn và nhanh.`

---

## 4. Tôi tự đánh giá đóng góp của mình (100–150 từ)

> Trả lời trung thực — không phải để khen ngợi bản thân.

**Tôi làm tốt nhất ở điểm nào?**
Tôi thiết lập hệ thống cảnh báo sớm Risk Catcher (`risk_high = any(...)`) và lưu giữ lịch sử mảng điều hướng `route_parts` rất tốt. Chuỗi logs ở `AgentState` được lưu đầy đủ các chặng và lý do vì sao nó tới đó chứ không phải một dòng comment vô tri, giúp việc debug hệ thống dễ tiếp cận.

**Tôi làm chưa tốt hoặc còn yếu ở điểm nào?**
Danh sách từ khóa ở `_should_route_policy_tool` và các mảng trong hàm khá rối và dễ sót nếu khách hàng dùng từ đồng nghĩa hoặc typo.

**Nhóm phụ thuộc vào tôi ở đâu?** _(Phần nào của hệ thống bị block nếu tôi chưa xong?)_
Luồng rẽ nhánh ở file `graph.py` nếu lỗi thì toàn bộ query bị đưa vào ngục (worker sai chức năng) sinh ra hallucinate hoặc ngắt mạch graph.

**Phần tôi phụ thuộc vào thành viên khác:** _(Tôi cần gì từ ai để tiếp tục được?)_
Tôi cần các bạn đảm nhiệm Worker trả ra chuẩn `retrieved_chunks` vì nếu policy return rỗng mà output state thiếu thì Graph sẽ gãy.

---

## 5. Nếu có thêm 2 giờ, tôi sẽ làm gì? (50–100 từ)

> Nêu **đúng 1 cải tiến** với lý do có bằng chứng từ trace hoặc scorecard.

*Tôi sẽ xây dựng cơ chế **Fallback Router Semantic Vector**. Vì trace gq09 ("ERR-403-AUTH") nếu ai gõ nhầm thành "E-403" thì Keyword check sẽ bị bỏ qua và dẫn route default sai. Nếu thêm một step Semantic check nhẹ (dùng cross-encoder nhỉnh 50ms) thì những từ vựng OOV (out-of-vocabulary) sẽ được tự động map về đúng Route đích mà không phải code if-else nữa.*

---

*Lưu file này với tên: `reports/individual/[ten_ban].md`*  
*Ví dụ: `reports/individual/nguyen_van_a.md`*
