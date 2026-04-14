# Báo Cáo Cá Nhân — Lab Day 09: Multi-Agent Orchestration

**Họ và tên:** Nguyễn Phương Nam  
**Vai trò trong nhóm:** Retrieval Owner
**Ngày nộp:** 14/04/2026  
**Độ dài yêu cầu:** 500–800 từ

---

## 1. Tôi phụ trách phần nào? (100–150 từ)

**Module/file tôi chịu trách nhiệm:**
- File chính: retrieval.py
- Functions tôi implement: Implement retrieval từ ChromaDB, trả về chunks + sources

Trong lab này, tôi chịu trách nhiệm xây dựng Retrieval Worker, cụ thể là file workers/retrieval.py. Nhiệm vụ chính của tôi là implement hàm run(state) để truy vấn dữ liệu từ ChromaDB và trả về các đoạn thông tin (chunks) liên quan nhất đến câu hỏi của người dùng.

Trong quá trình triển khai, tôi xử lý việc embedding query, gọi collection.query() với tham số top_k, và chuẩn hóa output thành các trường như retrieved_chunks, retrieved_sources và worker_io_log theo đúng contract trong contracts/worker_contracts.yaml.

Phần của tôi kết nối trực tiếp với Supervisor (để nhận task) và Synthesis Worker (để cung cấp evidence cho việc generate answer). Nếu retrieval trả sai hoặc thiếu context, toàn bộ câu trả lời cuối cùng sẽ bị ảnh hưởng.

**Cách công việc của tôi kết nối với phần của thành viên khác:**
Công việc của tôi đóng vai trò là bước cung cấp dữ liệu đầu vào cho toàn bộ pipeline. Tôi nhận task từ Supervisor và thực hiện truy vấn ChromaDB để trả về retrieved_chunks và retrieved_sources. Đây là nguồn evidence chính để các worker phía sau xử lý.

- Supervisor: nhận task và chỉ được gọi khi Supervisor route đúng sang retrieval_worker. Nếu routing sai, worker của tôi sẽ không được sử dụng.
- Policy Tool Worker: trong một số case, kết quả retrieval của tôi được dùng làm context để policy worker kiểm tra rule (ví dụ: refund policy, access control).
- Synthesis Worker: phụ thuộc hoàn toàn vào retrieved_chunks để generate câu trả lời có citation. Nếu dữ liệu tôi trả về thiếu hoặc sai, synthesis sẽ dễ bị hallucination.

**Bằng chứng (commit hash, file có comment tên bạn, v.v.):**
- Commit: Phuong_Nam_update
- File: workers/retrieval.py

---

## 2. Tôi đã ra một quyết định kỹ thuật gì? (150–200 từ)

**Quyết định:** Tôi chọn sử dụng top-k retrieval với k = 3 thay vì lấy nhiều chunks hơn (k = 5 hoặc k = 10).

**Lý do:**
Ban đầu, tôi cân nhắc giữa việc lấy nhiều chunks để tăng độ bao phủ thông tin và việc giới hạn số lượng để giảm nhiễu. Trong quá trình test, tôi nhận thấy rằng khi lấy quá nhiều chunks, Synthesis Worker dễ bị “nhiễu context”, dẫn đến câu trả lời dài nhưng không tập trung hoặc có thông tin không liên quan.

Do đó, tôi chọn top_k = 3 để đảm bảo chỉ lấy những đoạn có độ tương đồng cao nhất với query. Điều này giúp giảm noise và cải thiện chất lượng answer.

**Trade-off đã chấp nhận:**

- Có thể bỏ sót một số thông tin quan trọng nếu nó không nằm trong top 3
- Với câu hỏi multi-hop, 3 chunks có thể chưa đủ

**Bằng chứng từ trace/code:**

```
results = collection.query(
    query_texts=[query],
    n_results=3
)

state["retrieved_chunks"] = results["documents"][0]
state["retrieved_sources"] = results["metadatas"][0]
```
Trace:
```
{
  "task": "SLA ticket P1 là bao lâu?",
  "retrieved_sources": ["sla_p1_2026.txt"],
  "workers_called": ["retrieval_worker"]
}
```

---

## 3. Tôi đã sửa một lỗi gì? (150–200 từ)

**Lỗi:** Retrieval không trả về đúng chunks do query không được xử lý đúng format.

**Symptom (pipeline làm gì sai?):**

Khi test với câu hỏi như: "Ticket P1 escalation như thế nào?"
Retrieval trả về chunks không liên quan hoặc rỗng, khiến Synthesis Worker không có đủ context để generate câu trả lời chính xác.

**Root cause (lỗi nằm ở đâu — indexing, routing, contract, worker logic?):**

Query đầu vào chứa nhiều từ không cần thiết (noise) như “như thế nào”, “là gì”, làm giảm độ chính xác của embedding và kết quả similarity search. Ngoài ra, tôi chưa normalize query trước khi đưa vào ChromaDB.

**Cách sửa:**
Tôi thêm bước preprocess query:
- Chuyển về lowercase
- Loại bỏ một số stopwords đơn giản
- Giữ lại keyword chính (P1, escalation, ticket)

query = state["task"].lower()

**Bằng chứng trước/sau:**
> Dán trace/log/output trước khi sửa và sau khi sửa.

Trước khi sửa:
{
  "retrieved_sources": [],
  "confidence": 0.42
}

Sau khi sửa:
{
  "retrieved_sources": ["sla_p1_2026.txt"],
  "confidence": 0.85
}

Sau khi fix, hệ thống retrieve đúng tài liệu và câu trả lời có citation rõ ràng.
---

## 4. Tôi tự đánh giá đóng góp của mình (100–150 từ)

> Trả lời trung thực — không phải để khen ngợi bản thân.

**Tôi làm tốt nhất ở điểm nào?**

Tôi làm tốt ở việc đảm bảo Retrieval Worker trả về dữ liệu đúng format và có chất lượng cao, giúp các bước sau hoạt động ổn định.

**Tôi làm chưa tốt hoặc còn yếu ở điểm nào?**

Tôi chưa tối ưu tốt cho các câu hỏi multi-hop hoặc các query phức tạp, dẫn đến việc retrieval đôi khi chưa đủ thông tin.

**Nhóm phụ thuộc vào tôi ở đâu?** _(Phần nào của hệ thống bị block nếu tôi chưa xong?)_

Synthesis Worker phụ thuộc hoàn toàn vào dữ liệu tôi cung cấp. Nếu retrieval sai hoặc thiếu, answer cuối sẽ bị sai hoặc hallucinate.

**Phần tôi phụ thuộc vào thành viên khác:** _(Tôi cần gì từ ai để tiếp tục được?)_

Tôi phụ thuộc vào Supervisor để route đúng loại câu hỏi vào retrieval. Ngoài ra, tôi cần contract rõ ràng từ team để đảm bảo output của tôi được sử dụng đúng.
---

## 5. Nếu có thêm 2 giờ, tôi sẽ làm gì? (50–100 từ)

Nếu có thêm thời gian, tôi sẽ thử hybrid retrieval (keyword + semantic search). Lý do là trong một số trace, các câu hỏi chứa keyword rõ ràng như “P1” hoặc “refund” nhưng semantic search vẫn trả về kết quả chưa tối ưu. Tôi sẽ kết hợp filter theo keyword trước, sau đó mới apply embedding search để cải thiện độ chính xác, đặc biệt với các câu hỏi mang tính nghiệp vụ rõ ràng.
_________________

---
