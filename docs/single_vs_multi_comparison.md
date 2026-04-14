# Single Agent vs Multi-Agent Comparison — Lab Day 09

**Nhóm:** D3-C401  
**Ngày:** 14/04/2026

> Nguồn số liệu Day 09 lấy từ `artifacts/eval_report.json` (15 test questions).
> Day 08 trong repo hiện tại chưa có file metrics chuẩn để tính delta định lượng, nên các ô đó ghi `N/A`.

---

## 1. Metrics Comparison

| Metric | Day 08 (Single Agent) | Day 09 (Multi-Agent) | Delta | Ghi chú |
|--------|----------------------|---------------------|-------|---------|
| Avg confidence | N/A | **0.613** | N/A | Day 09 tính từ trace sau khi cải thiện hybrid retrieval |
| Avg latency (ms) | N/A | **3870** | N/A | Tổng end-to-end, gồm routing + worker + synthesis |
| Routing distribution | N/A | retrieval `9/15 (60%)`, policy `6/15 (40%)` | N/A | Routing cân bằng theo loại câu hỏi |
| MCP usage rate | N/A | **6/15 (40%)** | N/A | Chỉ bật MCP ở policy/access/refund phức tạp |
| HITL rate | N/A | **0/15 (0%)** | N/A | Chưa có case cần human review trong bộ test |
| Routing visibility | Không có route metadata rõ ràng | Có `supervisor_route` + `route_reason` | Improved | Dễ truy vết nguyên nhân sai |
| Debuggability | Thấp | Cao | Improved | Có `worker_io_logs`, `mcp_tool_calls`, `history` |

---
 
## 2. Phân tích theo loại câu hỏi

### 2.1 Câu hỏi đơn giản (single-document factual)

| Nhận xét | Day 08 | Day 09 |
|---------|--------|--------|
| Accuracy | N/A | Cao (ví dụ q01/q04 có answer đúng fact) |
| Latency | N/A | Trung bình thấp hơn policy path |
| Observation | N/A | Route chủ yếu vào `retrieval_worker`, không cần MCP |

**Ví dụ thực tế:**  
`run_20260414_160615` (SLA P1) route retrieval, confidence `0.95`, answer đúng các mốc 15 phút/4 giờ.

**Kết luận:**  
Day 09 xử lý tốt câu đơn giản; overhead routing có nhưng chấp nhận được khi đổi lại trace rõ ràng.

### 2.2 Câu hỏi multi-hop / policy-sensitive (cross-domain)

| Nhận xét | Day 08 | Day 09 |
|---------|--------|--------|
| Accuracy | N/A | Khá, phụ thuộc quality evidence |
| Routing visible? | Không | Có |
| Observation | N/A | `policy_tool_worker` + MCP giúp bám policy/access rule tốt hơn |

**Ví dụ thực tế:**  
`run_20260414_160624` (approval Level 3) route policy + MCP `search_kb`, trả đúng 3 approvers.

**Kết luận:**  
Day 09 mạnh ở luồng nhiều ràng buộc chính sách vì có worker chuyên trách và khả năng gọi tool ngoài.

### 2.3 Câu hỏi cần abstain / thiếu bằng chứng

| Nhận xét | Day 08 | Day 09 |
|---------|--------|--------|
| Abstain behavior | N/A | Có cơ chế abstain trong synthesis prompt |
| Hallucination risk | N/A | Giảm, nhờ rule “answer only from context” |
| Observation | N/A | Nếu context yếu, confidence giảm và câu trả lời thận trọng hơn |

**Kết luận:**  
Day 09 an toàn hơn về mặt vận hành vì ưu tiên grounded answer thay vì cố đoán.

---

## 3. Debuggability Analysis

### Day 08 — Debug workflow
```
Khi answer sai -> phải đọc xuyên suốt pipeline
Khó biết lỗi nằm ở retrieval, prompt hay logic quyết định
```

### Day 09 — Debug workflow
```
Khi answer sai -> mở trace JSON:
  1) check supervisor_route + route_reason
  2) check retrieved_chunks / retrieved_sources
  3) check mcp_tool_calls (nếu có)
  4) check synthesis confidence + answer
```

**Case debug thực tế:**  
Ở `run_20260414_160624`, route đúng nhưng có 1 chunk HR lẫn vào access query. Nhóm xác định bottleneck nằm ở quality retrieval/MCP search candidate, không phải routing.

---

## 4. Extensibility Analysis

| Scenario | Day 08 | Day 09 |
|---------|--------|--------|
| Thêm tool/API mới | Phải sửa pipeline/prompt lớn | Thêm MCP tool + cập nhật route rule |
| Thêm domain mới | Khó tách module | Thêm worker/domain policy mới |
| Đổi retrieval strategy | Thay trực tiếp lõi RAG | Chỉ sửa `retrieval_worker` (vd hybrid retrieval) |
| A/B test thành phần | Khó | Dễ (swap từng worker độc lập) |

**Nhận xét:**  
Day 09 có kiến trúc module hóa tốt hơn: worker nào cần cải thiện thì thay worker đó, không phá toàn hệ thống.

---

## 5. Cost & Latency Trade-off

| Scenario | Day 08 calls | Day 09 calls |
|---------|-------------|-------------|
| Simple query | N/A | ~1 LLM synthesis + retrieval |
| Policy query | N/A | + MCP calls (`search_kb`, đôi khi `get_ticket_info`) + synthesis |
| Complex query | N/A | Nhiều bước hơn do orchestration |

**Nhận xét về cost-benefit:**  
Day 09 đánh đổi thêm orchestration overhead để lấy khả năng debug, routing visibility, và mở rộng toolchain. Với bài toán internal helpdesk có policy/exception, trade-off này hợp lý.

---

## 6. Kết luận

**Multi-agent tốt hơn single agent ở điểm nào?**

1. Có điều phối theo ngữ cảnh (`supervisor_route`) thay vì một luồng cố định.
2. Debug nhanh nhờ trace chi tiết theo từng bước/worker.
3. Dễ mở rộng capability qua MCP mà không sửa core graph.

**Multi-agent kém hơn hoặc không khác biệt ở điểm nào?**

1. Overhead latency/cost cao hơn trong các case đơn giản.
2. Cần quản lý thêm contract giữa workers và quality của mỗi node.

**Khi nào không nên dùng multi-agent?**

Khi bài toán chủ yếu là lookup đơn giản, ít policy branch, và yêu cầu latency cực thấp.

**Nếu tiếp tục phát triển hệ thống này, nhóm sẽ thêm gì?**

1. Confidence calibration theo benchmark labels (thay heuristic).
2. Domain filtering trong retrieval để giảm chunk nhiễu.
3. HITL thật với interrupt/approval thay vì placeholder.
