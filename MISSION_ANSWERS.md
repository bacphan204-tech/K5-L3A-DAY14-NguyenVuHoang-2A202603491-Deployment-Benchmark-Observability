# Day 14 — Mission Answers

## Part 1 — Localhost vs Production

### 1.1 — Anti-patterns

1. `develop/app.py` lưu API key giả và URL cơ sở dữ liệu có thông tin đăng nhập trong code. Secret thật sẽ bị lưu vào lịch sử Git nếu áp dụng cách này.
2. Endpoint in cả key và nội dung câu hỏi lên stdout. Bất kỳ ai có quyền đọc log đều có thể thấy dữ liệu nhạy cảm.
3. Server bind `localhost`, nên traffic từ bên ngoài container không đến được ứng dụng.
4. Port cố định 8000. Nền tảng cloud thường cấp port qua biến môi trường.
5. `reload=True` khiến Uvicorn theo dõi file và khởi động lại khi code đổi. Đây là hành vi dành cho phát triển.
6. Không có endpoint riêng để kiểm tra liveness và readiness.
7. Không có lifecycle hook của app để dọn tài nguyên khi tắt.

### 1.2 — Chạy thử

```text
POST /ask?question=Hello
HTTP/1.1 200 OK
{"answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé."}
```

### 1.3 — So sánh

| Mục | Develop | Production | Lý do |
|---|---|---|---|
| Config | Key, URL, port cố định | `Settings` đọc từ env, ví dụ `PORT` dùng `os.getenv("PORT", "8000")` | Build lại cùng image trên các môi trường khác nhau mà chỉ đổi biến khi chạy |
| Health | Không có probe riêng | `/health` có status, uptime, version, environment | Giúp xác định process còn chạy |
| Readiness | Không có | `/ready` theo cờ được thiết lập trong lifespan | Giúp load balancer chọn instance sẵn sàng |
| Logging | `print` cả key và nội dung | Dùng logging, ghi event và độ dài dữ liệu | Có thể lọc sự kiện, giảm lộ dữ liệu |
| Shutdown | Không có hook dọn tài nguyên của app | Lifespan có khối shutdown do Uvicorn gọi | Cho phép dọn tài nguyên sau khi server xử lý các request đang chạy |
| Networking | `localhost:8000` | Mặc định `0.0.0.0`; đọc `HOST`, `PORT` | Container nhận được traffic qua port được publish |

Chạy bản production cho kết quả `GET /health` → 200 (`status=ok`), `GET /ready` → 200 (`ready=true`) và `POST /ask` với body JSON → 200.

## Part 2 — Docker

### 2.1 — Dockerfile

1. Image develop dùng `python:3.11`.
2. Thư mục làm việc là `/app`.
3. Copy `requirements.txt` và cài dependency trước để Docker tái sử dụng layer cài đặt khi chỉ thay đổi mã ứng dụng.
4. `ENTRYPOINT` xác định chương trình khởi chạy chính. `CMD` cung cấp lệnh mặc định hoặc đối số mặc định cho entrypoint. Đối số sau tên image trong `docker run` thay CMD, còn entrypoint có thể thay bằng `--entrypoint`.

### 2.2–2.4 — Kết quả build và Compose

Kích thước lấy từ `docker image inspect` (MB thập phân):

| Image | Bytes | MB |
|---|---:|---:|
| my-agent:develop | 1 667 779 864 | 1 667,78 |
| my-agent:advanced | 239 815 563 | 239,82 |

Mức giảm: `(develop − advanced) / develop × 100` = **85,62%**.

Bản develop: `POST /ask?question=What%20is%20Docker%3F` → **200 OK**. Qua Nginx, `GET /health` và `POST /ask` với JSON đều trả **200 OK**. Header `Server: nginx`; health trả `status=ok`, còn /ask trả câu trả lời mock.

```text
Client → Nginx :80 → Agent :8000
                       ├── Redis :6379 (cache / state)
                       └── Qdrant :6333 (vector database)
```

Builder cài dependency và công cụ build. Stage runtime dùng Python slim và chỉ đưa phần cài đặt cần thiết cùng mã ứng dụng vào image cuối.

## Part 3 — Cloud deployment

Đã deploy agent Part 6 và Redis trên Railway. URL public https://agent-production-b68ac0a3.up.railway.app. Kiểm tra CP6 cho kết quả /health 200, /ready 200, /ask thiếu key 401 và /ask có key 200. Xem [DEPLOYMENT.md](DEPLOYMENT.md) để chạy lại.

### Railway và Render

- Railway dùng TOML và tách bước build (`[build]`) với deploy (`[deploy]`). `builder = "DOCKERFILE"` chọn cách build, còn `healthcheckPath` cấu hình probe. Redis và biến môi trường được gắn vào service trong project.
- Render Blueprint dùng YAML và khai báo service theo danh sách. `type: web`, `runtime: docker`, `rootDir` và `healthCheckPath` mô tả web service. `envVars` cho phép tạo key ngẫu nhiên với `generateValue` và nhập URL Redis trên dashboard bằng `sync: false`.

### Cloud Run (3.3)

Cloud Build chạy bước `test` trong image Python trước khi đóng gói.

Docker build tạo image với tag cho lần build.

Image được push tới registry được cấu hình tại `gcr.io/$PROJECT_ID/ai-agent`.

Bước `deploy` dùng gcloud để cập nhật Cloud Run. `service.yaml` mô tả thiết lập runtime của service, bao gồm tài nguyên, scaling, env và probe.

## Part 4 — API security

### 4.1–4.3 — Kết quả curl

Thiếu key ở bản develop:

```text
HTTP/1.1 401 Unauthorized
{"detail":"Missing API key. Include header: X-API-Key: <your-key>"}
```

Đúng key demo:

```text
HTTP/1.1 200 OK
{"question":"Hello","answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé."}
```

Đăng nhập tài khoản demo `student` qua `POST /auth/token`, gửi JWT bằng Bearer header. Mười request đầu trả 200. Request thứ 11:

```text
HTTP/1.1 429 Too Many Requests
x-ratelimit-limit: 10
x-ratelimit-remaining: 0
retry-after: 59
{"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":59}}
```

### 4.4 — Cost guard

Kiểm tra chi phí tích lũy và phần chi phí tối thiểu trước khi gọi model. Sau khi nhận câu trả lời, cộng số tiền dựa trên token vào bộ đếm theo kỳ. Trả 402 khi không còn ngân sách để gọi. Rate limit kiểm soát tần suất, còn cost guard kiểm soát chi phí vì các request có thể tiêu thụ số token khác nhau.

## Part 5 — Scaling và reliability

- `GET /health` và `GET /ready` đều trả 200 khi agent sẵn sàng. Liveness dùng để xác định process còn sống, readiness dùng để xác định có nên gửi traffic vào instance.
- Gửi `SIGTERM` khoảng 0,5 giây sau khi bắt đầu `POST /ask`. Log ghi `Shutting down`, request vẫn trả `200 OK`, sau đó `Graceful shutdown initiated` và `Shutdown complete`.
- Mỗi worker có RAM riêng. Khi Nginx định tuyến một session qua nhiều agent, Redis giữ history chung để mỗi agent đều truy xuất được.
- Stack 3 agent đều healthy. Script gửi 5 request cùng session qua 3 instance và đọc lại đủ 10 message. Dùng cổng host 18005 bằng Compose override tạm để tránh đụng stack observability đang dùng 8080; không thay đổi code mẫu.

## Part 6 — Checklist Deliverable

```text
📋 Checklist Deliverable
   ✅ Dockerfile (multi-stage, < 500 MB)
   ✅ docker-compose.yml (agent + redis)
   ✅ .dockerignore
   ✅ Health check endpoint (GET /health)
   ✅ Readiness endpoint (GET /ready)
   ✅ API Key authentication
   ✅ Rate limiting
   ✅ Cost guard
   ✅ Config from environment variables
   ✅ Structured logging
   ✅ Graceful shutdown
   ✅ Public URL ready (Railway / Render config)
Result: 12/12 tiêu chí đạt · 43/43 checks passed
🎉 PASS 12/12 — PRODUCTION READY! Deploy nào!
```

Script đo image 238 MB. Container dừng trong 1,5 giây với exit code 0. Tiêu chí 12 kiểm tra cấu hình deploy của repo.

## AI log

| Tôi hỏi Codex về | Codex hỗ trợ | Tôi thực hiện và kiểm tra |
|---|---|---|
| Yêu cầu từng checkpoint và cách chạy lab trên Windows | Đối chiếu tài liệu K5 với repo, giải thích Docker, API security, scaling và tổng hợp các câu trả lời từ kết quả chạy | Tôi cài WSL2, Docker Desktop và lần lượt chạy các bài kiểm tra CP0–CP4. Tôi đối chiếu mã HTTP, kích thước image và kết quả giữ lịch sử phiên qua ba instance. |
| Hoàn thiện và kiểm tra agent Part 6 | Codex triển khai cấu hình, API key, rate limit, cost guard, Redis, log và shutdown, rồi chạy script chấm | Tôi chạy script CP5 trong WSL, đăng nhập Docker Hub để xử lý lỗi 429 và chạy lại. Codex cũng xác nhận một lượt chạy đầy đủ đạt 12/12. Tôi giữ nguyên script chấm. |
| Deploy và kiểm tra URL public | Codex chuẩn bị cấu hình và hướng dẫn tạo service, Redis, đổi API key và test HTTP | Tôi deploy lên Railway, đổi API key, chạy bốn bài test và nhận 200, 200, 401, 200. Tôi chụp ba ảnh CP6, Codex lưu ảnh và cập nhật URL trong repo. |
| Chạy benchmark và observability | Codex bổ sung histogram và kiến thức HPA/JWT, cấu hình quality gate, chạy load test, eval, Locust và thu thập ảnh Grafana, Jaeger, Prometheus | Tôi xác nhận đã kiểm tra các kết quả và bằng chứng CP7–CP8. Số liệu trong báo cáo lấy từ lượt chạy thực tế và các JSON/CSV kèm theo. Golden dataset được giữ nguyên. |
