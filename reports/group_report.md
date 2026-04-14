# Báo Cáo Nhóm — Lab Day 09: Multi-Agent Orchestration

**Tên nhóm:** D3-C401  
**Thành viên:**
| Tên | Vai trò | Email |
|-----|---------|-------|
| Nguyễn Quốc Khánh | Supervisor Owner |  |
| Lý Quốc An | Trace Owner |  |
| Nguyễn Quang Minh | MCP Owner |  |
| Lưu Thị Ngọc Quỳnh |  Docs Owner |  |
| Nguyễn Bá Khánh | Graph Owner |  |
| Nguyễn Phương Nam | Retrieval Owner |  |
| Lưu Quang Lực | Policy_tool Owner |  |
| Đinh Văn Thư |  Docs Owner |  |

**Ngày nộp:** 14/04/2026  
**Repo:** `D:/Github Repositories/lab09`  
**Độ dài khuyến nghị:** 600–1000 từ

---

> **Hướng dẫn nộp group report:**
> 
> - File này nộp tại: `reports/group_report.md`
> - Deadline: Được phép commit **sau 18:00** (xem SCORING.md)
> - Tập trung vào **quyết định kỹ thuật cấp nhóm** — không trùng lặp với individual reports
> - Phải có **bằng chứng từ code/trace** — không mô tả chung chung
> - Mỗi mục phải có ít nhất 1 ví dụ cụ thể từ code hoặc trace thực tế của nhóm

---

## 1. Kiến trúc nhóm đã xây dựng (150–200 từ)

> Mô tả ngắn gọn hệ thống nhóm: bao nhiêu workers, routing logic hoạt động thế nào,
> MCP tools nào được tích hợp. Dùng kết quả từ `docs/system_architecture.md`.

**Hệ thống tổng quan:**

Nhóm triển khai kiến trúc Supervisor-Worker với 3 worker chính: `retrieval_worker`, `policy_tool_worker`, `synthesis_worker`, được điều phối từ `graph.py`. Supervisor nhận task, gán `supervisor_route` và `route_reason`, sau đó worker phù hợp xử lý trước khi chuyển sang `synthesis_worker` để tạo câu trả lời cuối cùng.  

Trong 15 trace gần nhất, hệ thống route `retrieval_worker` cho 9/15 câu (60%) và `policy_tool_worker` cho 6/15 câu (40%), cho thấy chiến lược route đang ưu tiên factual retrieval và chỉ bật policy path khi có tín hiệu rule/exception. Khi cần, `policy_tool_worker` gọi MCP tool (`search_kb`, `get_ticket_info`) để bổ sung bằng chứng ngoài ngữ cảnh retrieval mặc định.  

So với single-agent, kiến trúc này tăng khả năng debug vì mỗi bước đều có log (`workers_called`, `mcp_tool_calls`, `worker_io_logs`, `confidence`, `latency_ms`). Nhờ đó nhóm xác định được lỗi nằm ở routing, retrieval hay synthesis thay vì phải đoán toàn pipeline.

**Routing logic cốt lõi:**
> Mô tả logic supervisor dùng để quyết định route (keyword matching, LLM classifier, rule-based, v.v.)

Supervisor dùng rule-based routing (keyword + override) thay vì classifier LLM:
- Nếu task chứa nhóm từ khóa `P1/SLA/ticket/incident` thì route `retrieval_worker`.
- Nếu task chứa `access level`, `store credit`, `flash sale`, `digital/license` thì route `policy_tool_worker` và bật `needs_tool`.
- Có override factual cho một số câu “refund window/days” để tránh over-route sang policy path.

Evidence rõ trong trace:  
- `run_20260414_160621`: route_reason = `factual refund window / days → retrieval (not policy-only)`  
- `run_20260414_160624`: route_reason = `access level / admin access → policy_tool + MCP`

**MCP tools đã tích hợp:**
> Liệt kê tools đã implement và 1 ví dụ trace có gọi MCP tool.

- `search_kb`: Tìm chunk policy/access theo truy vấn ngắn, dùng ở các câu policy-sensitive (ví dụ `run_20260414_160705`).
- `get_ticket_info`: Lấy dữ liệu ticket P1 đang active (ID, kênh notify, escalation state), ví dụ `run_20260414_160658`.
- `check_access_permission`: Đã khai báo trong kiến trúc MCP; dùng cho mở rộng flow cấp quyền ở các sprint tiếp theo.

---

## 2. Quyết định kỹ thuật quan trọng nhất (200–250 từ)

> Chọn **1 quyết định thiết kế** mà nhóm thảo luận và đánh đổi nhiều nhất.
> Phải có: (a) vấn đề gặp phải, (b) các phương án cân nhắc, (c) lý do chọn phương án đã chọn.

**Quyết định:** Chọn supervisor rule-based + factual override thay vì route thuần keyword hoặc classifier LLM.

**Bối cảnh vấn đề:**

Bài toán của nhóm có nhiều câu “lai” giữa factual và policy (đặc biệt refund/access). Nếu route thuần keyword, các câu có từ “hoàn tiền” dễ bị đẩy sang policy worker dù chỉ cần lấy một fact số ngày. Ngược lại, nếu route quá thiên retrieval thì các câu cần exception hoặc multi-hop policy sẽ thiếu bước MCP và trả lời thiếu điều kiện.

**Các phương án đã cân nhắc:**

| Phương án | Ưu điểm | Nhược điểm |
|-----------|---------|-----------|
| Keyword rule thuần | Dễ làm, trace rõ | Dễ over-route policy, tốn MCP call không cần thiết |
| LLM classifier | Linh hoạt ngữ nghĩa | Tăng latency/cost, khó giải thích route_reason khi sai |
| Hybrid rule + override (đã chọn) | Cân bằng giữa tốc độ, traceability, và độ chính xác | Cần bảo trì rule list thủ công |

**Phương án đã chọn và lý do:**

Nhóm chọn hybrid rule + override vì phù hợp giới hạn thời gian lab và yêu cầu trace minh bạch. Kết quả routing đạt 15/15 đúng kỳ vọng trong bộ test chuẩn; đồng thời giữ được latency trung bình 3870ms dù có 40% câu phải đi qua policy + MCP. Quyết định này cũng giúp nhóm xử lý tốt các case cross-domain như câu cần đồng thời SLA + access escalation (`run_20260414_160705`) mà vẫn giữ log rõ đường đi.

**Bằng chứng từ trace/code:**
> Dẫn chứng cụ thể (VD: route_reason trong trace, đoạn code, v.v.)

```
run_20260414_160621
route_reason: "factual refund window / days → retrieval (not policy-only)"
workers_called: ["retrieval_worker", "synthesis_worker"]

run_20260414_160705
route_reason: "access level / admin access → policy_tool + MCP"
mcp_tools_used: ["search_kb", "get_ticket_info"]
workers_called: ["policy_tool_worker", "synthesis_worker"]
```

---

## 3. Kết quả grading questions (150–200 từ)

> Sau khi chạy pipeline với grading_questions.json (public lúc 17:00):
> - Nhóm đạt bao nhiêu điểm raw?
> - Câu nào pipeline xử lý tốt nhất?
> - Câu nào pipeline fail hoặc gặp khó khăn?

**Tổng điểm raw ước tính:** 84 / 96

**Câu pipeline xử lý tốt nhất:**
- ID: `gq01` — Lý do tốt: trace `run_20260414_160642` trả đúng người nhận thông báo, kênh notify và thời điểm escalation (22:57) với confidence cao.

**Câu pipeline fail hoặc partial:**
- ID: `gq02` — Fail ở đâu: câu ngày 31/01 → 07/02 (`run_20260414_160646`) suy luận temporal còn cứng, chưa xử lý chắc phần “policy version trước 01/02”.  
  Root cause: policy worker dùng rule-based check + bằng chứng policy v4 nhưng thiếu đối chiếu đầy đủ với ngữ cảnh versioning.

**Câu gq07 (abstain):** Nhóm xử lý thế nào?

Nhóm xử lý đúng hướng abstain. Ở trace tương đương `run_20260414_160638` (mã lỗi không có trong docs), hệ thống trả lời “Không đủ thông tin trong tài liệu nội bộ...”, confidence 0.30, không bịa quy định. Điều này giảm rủi ro hallucination và phù hợp tiêu chí gq07.

**Câu gq09 (multi-hop khó nhất):** Trace ghi được 2 workers không? Kết quả thế nào?

Có ghi nhận đủ 2 workers cho case multi-hop khó nhất: `policy_tool_worker` + `synthesis_worker` (`run_20260414_160705`), đồng thời có 2 MCP calls (`search_kb`, `get_ticket_info`). Kết quả đã nêu được cả quy trình notify theo SLA P1 và cấp quyền tạm thời. Điểm cần cải thiện là confidence còn thấp (0.25) do evidence retrieval policy vẫn nhiễu nhẹ.

---

## 4. So sánh Day 08 vs Day 09 — Điều nhóm quan sát được (150–200 từ)

> Dựa vào `docs/single_vs_multi_comparison.md` — trích kết quả thực tế.

**Metric thay đổi rõ nhất (có số liệu):**

Hai metric rõ nhất:
- `routing distribution`: retrieval `9/15 (60%)`, policy `6/15 (40%)`.
- `MCP usage rate`: `6/15 (40%)`, chỉ bật khi câu policy/access phức tạp.

Ngoài ra, Day 09 có `avg_confidence = 0.613`, `avg_latency = 3870ms`, `hitl_rate = 0/15`.

**Điều nhóm bất ngờ nhất khi chuyển từ single sang multi-agent:**

Điều bất ngờ nhất là độ dễ debug tăng mạnh dù hệ thống nhiều bước hơn. Khi một câu sai, nhóm chỉ cần mở trace để xem lần lượt `supervisor_route` → `retrieved_chunks`/`mcp_tool_calls` → `synthesis confidence`, xác định được nút nghẽn cụ thể. Trước đó với single-agent, lỗi thường “dính chùm” trong một prompt dài và khó tách nguyên nhân.

**Trường hợp multi-agent KHÔNG giúp ích hoặc làm chậm hệ thống:**

Với câu factual rất ngắn (ví dụ tài khoản khóa sau bao nhiêu lần), multi-agent chưa tạo khác biệt lớn về chất lượng nhưng vẫn có orchestration overhead. Ngoài ra policy path đôi lúc kéo chunk không liên quan (ví dụ lẫn HR chunk ở `run_20260414_160624`) làm confidence giảm dù đáp án cuối đúng.

---

## 5. Phân công và đánh giá nhóm (100–150 từ)

> Đánh giá trung thực về quá trình làm việc nhóm.

**Phân công thực tế:**

| Thành viên | Phần đã làm | Sprint |
|------------|-------------|--------|
| Supervisor Owner | Thiết kế route rules, `route_reason`, integration flow trong `graph.py` | Sprint 1 |
| Worker Owner | Tách/chuẩn hóa I/O giữa retrieval và synthesis worker | Sprint 2 |
| MCP Owner | Implement `search_kb`, `get_ticket_info`, nối policy worker với MCP | Sprint 3 |
| Trace & Docs Owner | Chạy eval, tổng hợp trace, viết tài liệu đối chiếu Day 08/09 | Sprint 4 |

**Điều nhóm làm tốt:**

Nhóm làm tốt ở điểm phối hợp theo module: mỗi sprint có owner rõ, giao diện giữa các phần được kiểm soát bằng state fields (`workers_called`, `mcp_tools_used`, `confidence`). Việc thống nhất format trace từ đầu giúp review nhanh và sửa lỗi có hệ thống.

**Điều nhóm làm chưa tốt hoặc gặp vấn đề về phối hợp:**

Điểm chưa tốt là cuối sprint 3 có lệch kỳ vọng giữa policy semantics và retrieval quality: policy worker trả đúng logic nhưng confidence thấp do nguồn nhiễu. Ngoài ra, phần chấm raw cho grading chưa tự động hóa hoàn toàn (thiếu file `grading_run.jsonl` trong trạng thái hiện tại), khiến báo cáo phải dùng ước tính.

**Nếu làm lại, nhóm sẽ thay đổi gì trong cách tổ chức?**

Nếu làm lại, nhóm sẽ thêm một bước “trace quality gate” trước khi freeze: script kiểm tra tự động đủ fields bắt buộc (`route_reason`, `workers_called`, `mcp_tools_used`) và đối chiếu nhanh các câu trọng điểm gq07/gq09 để tránh lỗi tài liệu hóa sau chạy.

---

## 6. Nếu có thêm 1 ngày, nhóm sẽ làm gì? (50–100 từ)

> 1–2 cải tiến cụ thể với lý do có bằng chứng từ trace/scorecard.

Nhóm sẽ ưu tiên 2 cải tiến: (1) lọc domain trong policy retrieval để giảm chunk nhiễu (evidence: `run_20260414_160624` có chunk HR không liên quan), (2) calibration lại confidence theo rule nhất quán giữa retrieval-path và policy-path để confidence phản ánh chất lượng thật tốt hơn (hiện nhiều câu đúng nhưng confidence thấp ở policy flow).

---

*File này lưu tại: `reports/group_report.md`*  
*Commit sau 18:00 được phép theo SCORING.md*
