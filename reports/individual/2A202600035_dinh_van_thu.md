# Báo Cáo Cá Nhân — Lab Day 09: Multi-Agent Orchestration

**Họ và tên:** Đinh Văn Thư  
**Vai trò trong nhóm:** Supervisor Owner / Trace & Docs Owner  
**Ngày nộp:** 2026-04-14  
**Độ dài yêu cầu:** 500–800 từ

---

## 1. Tôi phụ trách phần nào? (100–150 từ)

Trong dự án này, tôi chịu trách nhiệm chính về kiến trúc hệ thống và luồng điều hướng của Supervisor. Cụ thể, tôi đã thiết kế và triển khai file [graph.py], nơi định nghĩa `supervisor_node` và logic `route_decision`. 

Nhiệm vụ của tôi là đảm bảo Supervisor có thể phân tích yêu cầu từ người dùng và điều phối chính xác đến các Worker chuyên biệt (`retrieval_worker` hoặc `policy_tool_worker`). Bên cạnh đó, tôi cũng phụ trách viết tài liệu [system_architecture.md] để mô tả pattern Supervisor-Worker và cách các thành phần tương tác qua `AgentState`. Công việc của tôi đóng vai trò là "bộ não" kết nối nỗ lực của các thành viên khác, đảm bảo dữ liệu từ retrieval được chuyển đến synthesis một cách nhất quán.

---

## 2. Tôi đã ra một quyết định kỹ thuật gì? (150–200 từ)

**Quyết định:** Tôi đã quyết định sử dụng mô hình **Supervisor-Worker** thay vì Single Agent RAG như ở Day 08.

**Lý do:** Khi làm việc với các yêu cầu phức tạp như hỗ trợ IT và xét duyệt hoàn tiền (Refund), một Agent đơn lẻ thường bị "loãng" prompt khi phải vừa đọc tài liệu hướng dẫn, vừa phải tuân thủ các quy tắc chính sách nghiêm ngặt. Bằng cách tách biệt thành các Worker chuyên biệt, tôi có thể tối ưu hóa prompt cho từng worker: `retrieval_worker` chỉ tập trung vào việc trích xuất thông tin, trong khi `policy_tool_worker` tập trung vào việc kiểm tra các điều kiện ngoại lệ (flash sale, activated products) thông qua MCP tools.

**Trade-off đã chấp nhận:** Quyết định này khiến Latency của hệ thống tăng lên đáng kể (trung bình ~11.4s so với ~4.5s ở Day 08) do phải thực hiện nhiều bước trung gian và gọi LLM nhiều lần hơn. Tuy nhiên, tôi chấp nhận đánh đổi tốc độ để lấy độ tin cậy (Reliability) và khả năng gỡ lỗi (Debuggability) cao hơn.

**Bằng chứng từ trace/code:**
Trong `graph.py`, tôi đã triển khai logic routing phân hóa rõ rệt:
```python
    if any(kw in task for kw in policy_keywords):
        route = "policy_tool_worker"
        route_reason = "task contains policy/access keyword"
        needs_tool = True
```
Trace `run_20260414_145748.json` cho thấy khi user hỏi về "Hoàn tiền Flash Sale", Supervisor đã route đúng vào `policy_tool_worker` với lý do rõ ràng, thay vì chỉ tìm kiếm tài liệu chung chung.

---

## 3. Tôi đã sửa một lỗi gì? (150–200 từ)

**Lỗi:** Dimension Mismatch trong ChromaDB (1536 vs 384).

**Symptom:** Khi chạy pipeline, `retrieval_worker` báo lỗi: `Collection expecting embedding with dimension of 1536, got 384`. Hệ thống không thể truy xuất được bất kỳ tài liệu nào.

**Root cause:** Lỗi nằm ở sự không đồng nhất giữa `index.py` và `retrieval.py`. File `index.py` ưu tiên sử dụng OpenAI embeddings (1536 dim) khi phát hiện có API key trong môi trường, trong khi `retrieval.py` lại mặc định sử dụng `SentenceTransformer` (384 dim). Do ChromaDB khởi tạo collection dựa trên những vector đầu tiên được insert, nên nó khóa schema ở mức 1536.

**Cách sửa:** Tôi đã sửa hàm `_get_embedding_fn` trong `workers/retrieval.py` để đồng nhất logic với `index.py`: ưu tiên kiểm tra OpenAI key trước. Sau đó, tôi thực hiện xóa collection cũ và chạy lại toàn bộ index với version `rag_lab_v2` để đảm bảo schema được khởi tạo đúng ngay từ đầu.

**Bằng chứng trước/sau:**
- **Trước:** `⚠️ ChromaDB query failed: Collection expecting embedding with dimension of 1536, got 384`
- **Sau:** Trace `run_20260414_145738.json` ghi nhận retrieval thành công 3 chunks từ `sla-p1-2026.pdf` và trả về kết quả chính xác trong 9909ms.

---

## 4. Tôi tự đánh giá đóng góp của mình (100–150 từ)

**Tôi làm tốt nhất ở điểm nào?**
Tôi làm tốt nhất ở việc giải quyết các blocker kỹ thuật liên quan đến môi trường (encoding, database schema) và viết tài liệu kiến trúc hệ thống rõ ràng, giúp nhóm hiểu rõ luồng đi của dữ liệu.

**Tôi làm chưa tốt hoặc còn yếu ở điểm nào?**
Logic routing của tôi vẫn còn phụ thuộc nhiều vào keyword matching đơn giản, điều này có thể dẫn đến sai sót nếu người dùng đặt câu hỏi không chứa từ khóa định danh.

**Nhóm phụ thuộc vào tôi ở đâu?**
Nếu file `graph.py` của tôi không xong, toàn bộ workers của các bạn khác sẽ không thể kết nối được với nhau và hệ thống không thể chạy end-to-end.

**Phần tôi phụ thuộc vào thành viên khác:**
Tôi phụ thuộc vào Worker Owner để đảm bảo các hàm `run()` trong `retrieval.py` và `policy_tool.py` trả về đúng format `AgentState`.

---

## 5. Nếu có thêm 2 giờ, tôi sẽ làm gì? (50–100 từ)

Tôi sẽ thay thế logic keyword matching trong `supervisor_node` bằng một mô hình LLM Classifier gọn nhẹ để phân loại yêu cầu. Qua quan sát các trace, tôi nhận thấy một số câu hỏi phức tạp pha trộn giữa kỹ thuật và chính sách có thể bị route nhầm nếu trọng số keyword không chuẩn. Việc dùng LLM sẽ giúp routing thông minh và linh hoạt hơn.

---

*Lưu file này với tên: `reports/individual/dinh_van_thu.md`*
