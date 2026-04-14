# System Architecture — Lab Day 09

**Nhóm:** C401_D3  
**Ngày:** 14/04/2026  
**Version:** 1.1 (post-improvement: hybrid retrieval + confidence recalibration)

---

## 1. Tổng quan kiến trúc

Hệ thống dùng pattern **Supervisor-Worker** để tách rõ vai trò điều phối, truy xuất bằng chứng, phân tích policy, và tổng hợp câu trả lời.

**Pattern đã chọn:** Supervisor-Worker  
**Lý do chọn pattern này (thay vì single agent):**

- Giảm coupling: mỗi worker có contract I/O riêng, có thể test độc lập.
- Dễ debug khi sai: trace ghi `supervisor_route`, `route_reason`, `workers_called`, `worker_io_logs`.
- Dễ mở rộng capability: thêm MCP tool mới không cần sửa core orchestrator.
- Hỗ trợ multi-hop queries tốt hơn (SLA + Access policy + ticket context).

---

## 2. Sơ đồ Pipeline

**Sơ đồ thực tế của nhóm (ASCII):**

```
User Query
   |
   v
Supervisor (graph.py)
   |- set: supervisor_route, route_reason, needs_tool, risk_high
   |
   +--> retrieval_worker -------------------+
   |       (hybrid retrieval: dense+sparse) |
   |                                         |
   +--> policy_tool_worker ------------------+--> synthesis_worker --> final_answer
   |       (rule-based policy + MCP tools)   |      (grounded LLM + citation + confidence)
   |                                         |
   +--> human_review (placeholder/HITL) -----+

Trace sink: artifacts/traces/*.json
Eval sink:  artifacts/eval_report.json
```

---

## 3. Vai trò từng thành phần

### Supervisor (`graph.py`)

| Thuộc tính         | Mô tả                                                                                                     |
| ------------------ | --------------------------------------------------------------------------------------------------------- |
| **Nhiệm vụ**       | Phân tích task, chọn route, bật cờ `needs_tool` và `risk_high`, điều phối worker sequence                 |
| **Input**          | `task` + state hiện tại                                                                                   |
| **Output**         | `supervisor_route`, `route_reason`, `risk_high`, `needs_tool`                                             |
| **Routing logic**  | Rule-based keyword routing + override cho factual refund query (`bao nhiêu ngày/bao lâu`) để đi retrieval |
| **HITL condition** | Có node `human_review` (placeholder), hiện chưa trigger trong run chuẩn (`hitl_rate = 0/15`)              |

### Retrieval Worker (`workers/retrieval.py`)

| Thuộc tính          | Mô tả                                                                                                             |
| ------------------- | ----------------------------------------------------------------------------------------------------------------- |
| **Nhiệm vụ**        | Truy xuất evidence chunks từ ChromaDB và trả về `retrieved_chunks`, `retrieved_sources`                           |
| **Embedding model** | Dùng `index.get_embedding` (OpenAI `text-embedding-3-small` nếu có API key, fallback sentence-transformers/local) |
| **Top-k**           | Mặc định `retrieval_top_k = 5` từ `AgentState`                                                                    |
| **Stateless?**      | Yes (chỉ đọc input state và ghi output fields theo contract)                                                      |
| **Retrieval mode**  | Hybrid retrieval: dense + sparse (BM25-lite) + RRF fusion                                                         |

### Policy Tool Worker (`workers/policy_tool.py`)

| Thuộc tính                | Mô tả                                                                                               |
| ------------------------- | --------------------------------------------------------------------------------------------------- |
| **Nhiệm vụ**              | Phân tích policy/refund/access rule và ngoại lệ; gọi MCP khi cần                                    |
| **MCP tools gọi**         | `search_kb`, `get_ticket_info` (theo `needs_tool` và task keywords)                                 |
| **Exception cases xử lý** | Flash Sale, digital product/license/subscription, activated product, temporal note trước 01/02/2026 |
| **Output chính**          | `policy_result`, `mcp_tools_used`, `worker_io_logs`                                                 |

### Synthesis Worker (`workers/synthesis.py`)

| Thuộc tính             | Mô tả                                                                                                     |
| ---------------------- | --------------------------------------------------------------------------------------------------------- |
| **LLM model**          | OpenAI `gpt-4o-mini` (fallback Gemini `gemini-1.5-flash`)                                                 |
| **Temperature**        | `0.1`                                                                                                     |
| **Grounding strategy** | Prompt “answer only from context”, context builder theo chunks + policy exceptions, citation `[1]`, `[2]` |
| **Abstain condition**  | Nếu không có context hoặc thiếu evidence thì trả lời “Không đủ thông tin trong tài liệu nội bộ”           |
| **Confidence**         | Heuristic từ score chunks (best/top-k), có penalty cho exception complexity                               |

### MCP Server (`mcp_server.py`)

| Tool                      | Input                                            | Output                                                           |
| ------------------------- | ------------------------------------------------ | ---------------------------------------------------------------- |
| `search_kb`               | `query`, `top_k`                                 | `chunks`, `sources`, `total_found`                               |
| `get_ticket_info`         | `ticket_id`                                      | ticket detail (priority/status/assignee/sla_deadline/...)        |
| `check_access_permission` | `access_level`, `requester_role`, `is_emergency` | `can_grant`, `required_approvers`, `emergency_override`, `notes` |
| `create_ticket`           | `priority`, `title`, `description`               | mock `ticket_id`, `url`, `created_at`                            |

---

## 4. Shared State Schema

| Field               | Type    | Mô tả                          | Ai đọc/ghi                          |
| ------------------- | ------- | ------------------------------ | ----------------------------------- |
| `task`              | `str`   | Câu hỏi đầu vào                | supervisor đọc                      |
| `supervisor_route`  | `str`   | Worker được chọn               | supervisor ghi                      |
| `route_reason`      | `str`   | Lý do route cụ thể             | supervisor ghi                      |
| `risk_high`         | `bool`  | Cờ rủi ro cao                  | supervisor ghi                      |
| `needs_tool`        | `bool`  | Có cần gọi MCP hay không       | supervisor ghi                      |
| `retrieved_chunks`  | `list`  | Evidence chunks                | retrieval/policy ghi, synthesis đọc |
| `retrieved_sources` | `list`  | Nguồn đã retrieve              | retrieval ghi                       |
| `policy_result`     | `dict`  | Kết quả policy analysis        | policy worker ghi                   |
| `mcp_tools_used`    | `list`  | Danh sách tool calls + payload | policy worker ghi                   |
| `workers_called`    | `list`  | Thứ tự workers đã chạy         | tất cả nodes ghi                    |
| `worker_io_logs`    | `list`  | Input/output log theo worker   | workers ghi                         |
| `final_answer`      | `str`   | Câu trả lời cuối               | synthesis ghi                       |
| `sources`           | `list`  | Nguồn dùng để tổng hợp         | synthesis ghi                       |
| `confidence`        | `float` | Độ tin cậy câu trả lời         | synthesis ghi                       |
| `latency_ms`        | `int`   | Tổng latency mỗi run           | graph ghi                           |
| `hitl_triggered`    | `bool`  | Có vào nhánh HITL hay không    | human_review ghi                    |
| `history`           | `list`  | Log step-by-step               | supervisor/workers/graph ghi        |
| `run_id`            | `str`   | ID trace                       | graph khởi tạo                      |

---

## 5. Lý do chọn Supervisor-Worker so với Single Agent (Day 08)

| Tiêu chí            | Single Agent (Day 08)                          | Supervisor-Worker (Day 09)                |
| ------------------- | ---------------------------------------------- | ----------------------------------------- |
| Debug khi sai       | Khó, lỗi retrieval/policy/synthesis trộn chung | Dễ, có trace theo node + worker IO logs   |
| Thêm capability mới | Phải sửa prompt/flow lớn                       | Thêm tool/worker riêng, ít ảnh hưởng core |
| Routing visibility  | Không có route rõ ràng                         | Có `supervisor_route` + `route_reason`    |
| Tái sử dụng         | Khó tái dùng thành phần                        | Worker/module độc lập, tái dùng được      |
| Khả năng mở rộng    | Dễ thành “monolith prompt”                     | Mở rộng theo graph edges và contracts     |

**Quan sát từ run thực tế (15 câu):**

- Routing distribution: `retrieval_worker 9/15 (60%)`, `policy_tool_worker 6/15 (40%)`
- MCP usage rate: `6/15 (40%)`
- Avg latency: `3870 ms`
- Avg confidence: `0.613`

---

## 6. Giới hạn và điểm cần cải tiến

1. **Policy analysis còn rule-based:** chưa có policy reasoner mạnh cho các trường hợp multi-document conflict.
2. **Nhiễu source trong retrieval:** một số câu vẫn kéo theo chunk khác domain (vd HR trong access query), ảnh hưởng confidence.
3. **HITL chưa vận hành thật:** `human_review` mới là placeholder, chưa có workflow approval/interrupt thực sự.
4. **Calibration confidence chưa supervised:** đang heuristic; cần benchmark theo expected-answer scoring để ổn định ngưỡng auto-answer.
