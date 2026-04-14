# Routing Decisions Log — Lab Day 09 (Updated)

**Nhóm:** C401_D3  
**Ngày cập nhật:** 14/04/2026

> Nguồn dữ liệu: kết quả run mới nhất trong `artifacts/traces/` và `artifacts/eval_report.json` (15 câu test chuẩn).
> Hệ thống đã cải thiện bằng hybrid retrieval và cập nhật confidence calibration.

---

## Routing Decision #1 — SLA factual query

**Task đầu vào:**
> SLA xử lý ticket P1 là bao lâu?

**Worker được chọn:** `retrieval_worker`  
**Route reason (từ trace):** `P1 / SLA / ticket / incident keywords → retrieval`  
**MCP tools được gọi:** `[]`  
**Workers called sequence:** `['retrieval_worker', 'synthesis_worker']`

**Kết quả thực tế (trace `run_20260414_160615`):**
- final_answer (ngắn): phản hồi ban đầu 15 phút, xử lý 4 giờ, escalation 10 phút.
- confidence: `0.95`
- Correct routing? **Yes**

**Nhận xét:**

Đây là câu factual SLA, không cần policy reasoning. Route thẳng sang retrieval giúp latency ổn định
và giữ được grounding tốt từ tài liệu `support/sla-p1-2026.pdf`.

---

## Routing Decision #2 — Refund factual override

**Task đầu vào:**
> Khách hàng có thể yêu cầu hoàn tiền trong bao nhiêu ngày?

**Worker được chọn:** `retrieval_worker`  
**Route reason (từ trace):** `factual refund window / days → retrieval (not policy-only)`  
**MCP tools được gọi:** `[]`  
**Workers called sequence:** `['retrieval_worker', 'synthesis_worker']`

**Kết quả thực tế (trace `run_20260414_160621`):**
- final_answer (ngắn): 7 ngày làm việc kể từ xác nhận đơn hàng.
- confidence: `0.95`
- Correct routing? **Yes**

**Nhận xét:**

Đây là rule override quan trọng nhất: dù có từ khóa "hoàn tiền", câu hỏi là factual numeric.
Nếu route sang policy worker sẽ tốn MCP call không cần thiết.

---

## Routing Decision #3 — Access control policy + MCP

**Task đầu vào:**
> Ai phải phê duyệt để cấp quyền Level 3?

**Worker được chọn:** `policy_tool_worker`  
**Route reason (từ trace):**  
`access level / admin access → policy_tool + MCP | MCP enabled: policy worker uses search_kb / get_ticket_info (not direct Chroma in policy)`  
**MCP tools được gọi:** `['search_kb']`  
**Workers called sequence:** `['policy_tool_worker', 'synthesis_worker']`

**Kết quả thực tế (trace `run_20260414_160624`):**
- final_answer (ngắn): cần phê duyệt từ Line Manager + IT Admin + IT Security.
- confidence: `0.15`
- Correct routing? **Yes**

**Nhận xét:**

Routing đúng vì đây là policy query về access level. Điểm cần cải thiện là quality retrieval trong policy flow:
vẫn lẫn 1 chunk HR không liên quan, kéo confidence thấp dù đáp án cuối đúng.

---

## Routing Decision #4 — IT helpdesk default path

**Task đầu vào:**
> Tài khoản bị khóa sau bao nhiêu lần đăng nhập sai?

**Worker được chọn:** `retrieval_worker`  
**Route reason (từ trace):** `default → retrieval_worker`  
**MCP tools được gọi:** `[]`  
**Workers called sequence:** `['retrieval_worker', 'synthesis_worker']`

**Kết quả thực tế (trace `run_20260414_160626`):**
- final_answer (ngắn): khóa sau 5 lần đăng nhập sai liên tiếp.
- confidence: `0.95`
- Correct routing? **Yes**

**Nhận xét:**

Câu FAQ nội bộ đơn giản, route mặc định vào retrieval là hợp lý. Hybrid retrieval đưa chunk đúng domain
(`support/helpdesk-faq.md`) lên top-1 với score cao.

---

## Tổng kết

### Routing Distribution (15 câu test chuẩn)

| Worker | Số câu được route | % tổng |
|--------|-------------------|--------|
| retrieval_worker | 9 | 60% |
| policy_tool_worker | 6 | 40% |
| human_review | 0 | 0% |

### Routing Accuracy

- Câu route đúng theo expected route: **15 / 15**
- Câu route sai: **0**
- Câu trigger HITL: **0**

### Metrics sau cải thiện

- Avg confidence: **0.613**
- Avg latency: **3870 ms**
- MCP usage rate: **6/15 (40%)**

### Lesson Learned về Routing

1. Rule-based supervisor vẫn là lựa chọn tốt cho bài lab vì traceable và debug được nhanh theo từng điều kiện.
2. Cần có override rule cho câu factual có từ khóa policy để tránh over-routing vào policy tool.
3. Hybrid retrieval cải thiện rõ confidence cho phần lớn câu factual, nhưng policy flow vẫn cần lọc source theo domain để giảm nhiễu.

### Route Reason Quality

`route_reason` hiện đã đủ để truy vết đường đi và biết khi nào bật MCP. Đề xuất nâng cấp tiếp:
- Chuẩn hóa theo mã rule (vd: `R_SLA_FACTUAL`, `R_REFUND_FACTUAL_OVERRIDE`, `R_ACCESS_LEVEL_POLICY`).
- Ghi `matched_keywords` và `mcp_required=true/false` dạng machine-readable.
- Ghi thêm `fallback_used` khi phải route bổ sung do worker trước không đủ context.
