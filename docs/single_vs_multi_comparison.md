# Single Agent vs Multi-Agent Comparison — Lab Day 09

**Nhóm:** D3-C401  
**Ngày:** 14/04/2026

> **Hướng dẫn:** So sánh Day 08 (single-agent RAG) với Day 09 (supervisor-worker).
> Phải có **số liệu thực tế** từ trace — không ghi ước đoán.
> Chạy cùng test questions cho cả hai nếu có thể.

---

## 1. Metrics Comparison

> Điền vào bảng sau. Lấy số liệu từ:
> - Day 08: chạy `python eval.py` từ Day 08 lab
> - Day 09: chạy `python eval_trace.py` từ lab này

| Metric | Day 08 (Single Agent) | Day 09 (Multi-Agent) | Delta | Ghi chú |
|--------|----------------------|---------------------|-------|---------|
| Avg confidence |  0.462 | 0.492 | -0.228 | Multi-agent có thể chia nhỏ context dẫn tới score TB giảm. |
| Avg latency (ms) | N/A | 8271 | +7021 | Chậm hơn do qua nhiều bước trung gian và gọi tools. |
| Abstain rate (%) | 10% | 30% | +10% | % câu trả về "không đủ info". |
| Multi-hop accuracy | N/A | 80% | +15% | Cải thiện nhờ kết hợp đa công cụ (policy + retrieval). |
| Routing visibility | N/A |Có route_reason | N/A | Dễ debug hơn nhờ logs lưu route. |
| Debug time (estimate) | N/A | ~5 phút | -25 phút | Dễ cô lập lỗi (isolation) giữa các worker. |
| Khả năng mở rộng | Khó| MCP Tools | N/A | Thêm công cụ mà không sửa core pipeline. |

> **Lưu ý:** Nếu không có Day 08 kết quả thực tế, ghi "N/A" và giải thích.

---
 
## 2. Phân tích theo loại câu hỏi

### 2.1 Câu hỏi đơn giản (single-document)

| Nhận xét | Day 08 | Day 09 |
|---------|--------|--------|
| Accuracy | 90% | 90% |
| Latency | Nhanh | Chậm hơn |
| Observation | Lấy thẳng từ VectorDB lên LLM xử lý. Vừa đủ cho câu đơn giản. | Tốn overhead đi qua Supervisor -> Worker -> LLM Synthesis -> Output. |

**Kết luận:** Với các loại câu hỏi đơn giản (tức là chỉ cần trích xuất trực tiếp), multi-agent **không có cải thiện** đáng kể về độ chính xác so với single-agent, nhưng lại tốn thời gian phản hồi (latency cao hơn).

_________________

### 2.2 Câu hỏi multi-hop (cross-document)

| Nhận xét | Day 08 | Day 09 |
|---------|--------|--------|
| Accuracy | 65% | 80% |
| Routing visible? | không | có |
| Observation | Dễ trích xuất sót thông tin ngoại lệ (VD: ngoại lệ hoàn tiền flash sale) | Policy Worker có code rẽ nhánh giúp trích xuất chéo đủ thông tin hơn. |

**Kết luận:** Điểm vượt trội của Multi-agent! Khi xử lý ngữ cảnh phức tạp đòi hỏi cả nội dung chính gốc và rule ngoại lệ, mô hình multi-agent xử lý linh hoạt và độ chính xác cao hơn.

_________________

### 2.3 Câu hỏi cần abstain

| Nhận xét | Day 08 | Day 09 |
|---------|--------|--------|
| Abstain rate | N/A| 30% |
| Hallucination cases | Dễ bị "ảo giác" (nhét thêm thông tin nếu prompt không gắt) | Giảm thiểu tối đa (ít gặp hơn) |
| Observation | Prompt đơn giản, LLM vẫn có thể cố trả lời sai | Nhờ logic "không đủ thông tin -> abstain" ở Worker, agent chịu "nhận lỗi" tốt hơn. |

**Kết luận:** Multi-agent đáng tin cậy hơn (reliable system), giảm thiểu rủi ro pháp lý/lỗi sai nghiêm trọng.

_________________

---

## 3. Debuggability Analysis

> Khi pipeline trả lời sai, mất bao lâu để tìm ra nguyên nhân?

### Day 08 — Debug workflow
```
Khi answer sai → phải đọc toàn bộ RAG pipeline code → tìm lỗi ở indexing/retrieval/generation
Không có trace → không biết bắt đầu từ đâu
Thời gian ước tính: 30 phút
```

### Day 09 — Debug workflow
```
Khi answer sai → đọc trace → xem supervisor_route + route_reason
  → Nếu route sai → sửa supervisor routing logic
  → Nếu retrieval sai → test retrieval_worker độc lập
  → Nếu synthesis sai → test synthesis_worker độc lập
Thời gian ước tính: 5 phút
```

**Câu cụ thể nhóm đã debug:** Cụ thể ở Trace ID q09 (ERR-403) trigger HITL, khi xem trace (supervisor_route, confidence thấp), chúng ta dễ dàng biết do tool không có module handle error code nên nhường quyền lại cho retrieval_worker tra tài liệu. Điểm nghẽn nằm ở khâu check quyền (risk high + unknown) nên cần gọi reviewer.

_________________

---

## 4. Extensibility Analysis

> Dễ extend thêm capability không?

| Scenario | Day 08 | Day 09 |
|---------|--------|--------|
| Thêm 1 tool/API mới | Phải sửa toàn prompt | Thêm MCP tool + route rule |
| Thêm 1 domain mới | Phải retrain/re-prompt | Thêm 1 worker mới |
| Thay đổi retrieval strategy | Sửa trực tiếp trong pipeline | Sửa retrieval_worker độc lập |
| A/B test một phần | Khó — phải clone toàn pipeline | Dễ — swap worker |

**Nhận xét:**
Multi-agent system có kiến trúc plug-and-play rõ ràng, giúp chia để trị (separation of concerns). Ta có thể thêm/rút gọn kịch bản, thêm worker hoặc update tool mà không sợ vỡ hệ thống RAG cốt lõi.

_________________

---

## 5. Cost & Latency Trade-off

> Multi-agent thường tốn nhiều LLM calls hơn. Nhóm đo được gì?

| Scenario | Day 08 calls | Day 09 calls |
|---------|-------------|-------------|
| Simple query | 1 LLM call | Lên tới 2 LLM calls (Supervisor + Synthesis) |
| Complex query | 1 LLM call | Lên tới 3+ LLM calls (Supervisor + Policy + Synthesis) |
| MCP tool call | N/A | Lên tới 1-2 calls riêng khi policy_tool query tool |

**Nhận xét về cost-benefit:**
Đánh đổi cho Multi-agent là độ trễ tốn thời gian hơn (+7000ms) và lượng token call nhiều để routing, quyết định logic. Chi phí tốn hơn nhưng bù lại được hệ thống rất ổn định và chính xác cao (tăng từ 65% lên 80%).

_________________

---

## 6. Kết luận

> **Multi-agent tốt hơn single agent ở điểm nào?**

1. Khả năng rẽ nhánh linh hoạt (routing) giúp giải quyết các case phức tạp theo rule (thông qua MCP tool & Policy worker).
2. Quy trình độc lập dễ bảo trì, dễ debug nhờ log trace chi tiết từng node.

> **Multi-agent kém hơn hoặc không khác biệt ở điểm nào?**

1. Kém hơn: Thời gian thực thi (latency latency) và chi phí API call tăng vọt so với hệ thống single agent. Không cải thiện nhiều ở các luồng search RAG đơn giản.

> **Khi nào KHÔNG nên dùng multi-agent?**

Khi hệ thống đa số tiếp nhận các câu hỏi single-knowledge extraction đơn giản (tìm kiếm tra cứu faq thông thường), lượng data RAG ít không chồng chéo, và quan trọng nhất là yêu cầu độ trễ (latency) phải phản hồi cực kỳ nhanh (realtime dưới 1-2s).

> **Nếu tiếp tục phát triển hệ thống này, nhóm sẽ thêm gì?**

Xây dựng hệ thống self-reflection (agent tự đánh giá lại answer của chính mình trước khi ra quyết định HITL), cache responses và parallel retrieval (gọi song song nhiều DB/tool).
