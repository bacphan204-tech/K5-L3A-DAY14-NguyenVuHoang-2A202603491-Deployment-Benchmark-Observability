# Benchmark & Observability Report — Day 14

**Họ tên** · Nguyễn Vũ Hoàng

**Ngày chạy** · 25/11/2026

**Môi trường** · Windows x64, Ubuntu WSL2, Python 3.11.18, Docker Desktop 4.100.1.

## 1. SLO

| SLI | Mục tiêu | Lý do |
|---|---|---|
| p95 latency /ask | ≤ 500 ms (local) | Giữ độ trễ của phần lớn request dưới nửa giây |
| Error rate /ask | ≤ 2% (local) | Giới hạn tỷ lệ request lỗi |
| Accuracy | ≥ 85% trong CI, 100% ở lần xác minh cuối | Bảo vệ chất lượng khi merge và xác minh đủ các câu của lab |

Stack Prometheus dùng ngưỡng cảnh báo riêng là 5% error và 1 giây p95 trong khoảng thời gian rule yêu cầu.

## 2. Benchmark hiệu năng

### 2.1 Concurrency

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Errors | SLO |
|---:|---:|---:|---:|---:|---:|---|
| 1 | 4.19 | 191.6 | 223.9 | 1682.3 | 0.00% | PASS |
| 10 | 19.01 | 212.5 | 1757.5 | 4604.6 | 0.00% | FAIL |
| 50 | 27.72 | 1280.6 | 3649.8 | 4572.4 | 0.00% | FAIL |
| 100 | 47.18 | 939.6 | 2749.1 | 2950.4 | 0.00% | FAIL |

Mỗi lượt dùng v2 với 300 request, slow rate 0.03 và error rate mô phỏng 0. RPS không tăng tuyến tính. Concurrency cao chồng lấp thời gian chờ nhưng đồng thời làm tăng áp lực xử lý. Các lượt chạy trùng lúc Docker tải/build image, nên kết quả có nhiễu tài nguyên máy.

### 2.2 Tail latency

| MOCK_SLOW_RATE | Avg (ms) | p95 (ms) | p99 (ms) |
|---:|---:|---:|---:|
| 0 | 281.7 | 411.4 | 496.2 |
| 0.03 | 249.1 | 269.1 | 1691.1 |
| 0.1 | 325.4 | 1679.4 | 1717.1 |

Mỗi lượt dùng 300 request và concurrency 20. Ở 3% slow, p99 tăng lên hơn 1,6 giây trong khi p95 dưới 500 ms. Ở 10%, p95 cũng vượt 1,6 giây vì nhóm request chậm chiếm trên 5%. Avg ở lượt 0% cao hơn lượt 3%, phù hợp với nhiễu tài nguyên và lấy mẫu ngẫu nhiên. Percentile cho thấy nhóm người dùng bị chậm mà số trung bình có thể che khuất.

## 3. Benchmark chất lượng

| Report | Accuracy | Avg tokens / câu | Tổng cost USD | Cost / câu đúng USD | p95 (ms) | Gate |
|---|---:|---:|---:|---:|---:|---|
| eval_v1 | 1/23 (4.3%) | 57.4 | 0.000408 | 0.00040815 | 186.7 | FAIL |
| eval_v2 | 21/23 (91.3%) | 109 | 0.000760 | 0.00003619 | 1560.6 | PASS |
| eval_v2_fixed | 23/23 (100.0%) | 113.3 | 0.000787 | 0.00003423 | 225.4 | PASS |

| ID | Keyword bị thiếu | Cách sửa |
|---|---|---|
| security-02 | token, hết hạn, chữ ký | Thêm mô tả JWT và cách kiểm chứng token, so với API key |
| scaling-03 | CPU, memory, custom metrics | Thêm tài liệu HPA và ví dụ custom metrics |

Retrieval v2 dùng thêm token và tăng chi phí tổng, nhưng cho chi phí trên một câu đúng thấp hơn. v2 sau sửa có 0 regression so với v2 ban đầu. Độ trễ của từng lượt còn phụ thuộc request chậm lấy mẫu ngẫu nhiên. Eval dùng MOCK_ERROR_RATE=0 và giữ nguyên golden dataset.

Workflow Day 14 quality gate chạy eval ở mỗi pull request. Exit code 1 làm job thất bại khi accuracy dưới 85%. Có thể bật required status check cho job eval để GitHub chặn merge khi bị fail.

### Exercise 7.1

Counter `http_requests_total{method="POST",route="/ask",status="200"}` đạt 23 sau eval. Gauge `agent_in_flight_requests` trở về 0. Histogram mới `agent_question_length_chars` có count 23. URL thô làm label sẽ tạo series riêng cho từng đường dẫn lạ, tốn tài nguyên scrape, truy vấn và lưu trữ.

## 4. Observability stack

### 4.1 Grafana

[Dashboard Grafana khi đang có tải](screenshots/grafana-dashboard.png) cho thấy 3 instance, 59,3 req/s, p95 639,46 ms và 1,07% error tại thời điểm chụp.

- Truy vấn Prometheus cùng giai đoạn với cửa sổ 1 phút cho avg **262,42 ms**, p95 **642,32 ms**. Khoảng cách này cho thấy một nhóm request bị chậm. Giá trị trên panel thay đổi theo thời điểm scrape.
- RPS từng instance là **19,60**, **19,89**, **19,11**. Ba instance nhận traffic gần đều sau khi ổn định.
- Input đạt **4 482,3 token/s**, output **2 341,3 token/s**. v2 thêm context truy xuất vào prompt, làm input thường dài hơn output.
- `/metrics` qua Nginx trả **404**. Prometheus scrape trực tiếp từ agent qua mạng Compose.

### 4.2 Alert rules và fault injection

`promtool test rules /p/alert_rules_test.yml` trả **SUCCESS**. Rule chờ điều kiện đúng đủ thời gian `for` mới chuyển từ pending sang firing.

[Prometheus Alerts](screenshots/prometheus-alert-firing.png) ghi lại hai alert cùng firing. Áp dụng hai thay đổi trong một lượt với Locust 30 users, ramp-up 5 users/giây. Thời gian tính từ lúc chạy Compose để đổi cấu hình tới lần truy vấn đầu tiên thấy trạng thái firing.

| Thí nghiệm | Alert thấy firing | Thời gian | Panel phản ánh |
|---|---|---:|---|
| A · `MOCK_ERROR_RATE=0.2` | `AgentHighErrorRate` | 105 giây | Error rate và LLM calls theo kết quả |
| B · `MOCK_SLOW_RATE=0.3` | `AgentHighLatencyP95` | 153 giây | Latency p95 và LLM latency p95 |

Ảnh còn có rule cost firing trong cửa sổ quan sát. Lượt này dùng model mặc định, nên kết quả đó không được tính là thí nghiệm đổi model. Đã khôi phục cấu hình agent sau khi chụp.

Nếu chuyển sang v1, accuracy có thể giảm trong khi lỗi HTTP và latency vẫn dưới ngưỡng. Dùng golden dataset trong CI và eval định kỳ trên phiên bản đang phục vụ để phát hiện. Lỗi 504 phát sinh tại Nginx cũng có thể nằm ngoài số liệu agent vì proxy tự trả lỗi.

### 4.3 Jaeger và log tương ứng

- [Trace chậm](screenshots/jaeger-slow-trace.png), ID `74e50d562a7a5ed195b9f8722a2ffa5a`.
- Request mất **1 923,63 ms**. Span `chat mock-llm-small` mất **1 711,77 ms**, chiếm **89,0%**. Retrieval mất **93,28 ms**.
- Dòng log JSON có cùng `trace_id`:

```json
{"ts":"2026-11-25T09:26:09.539636+00:00","level":"INFO","service":"observable-agent","instance":"b67f5644739a","event":"llm_call","trace_id":"74e50d562a7a5ed195b9f8722a2ffa5a","span_id":"96e4234542872746","request_id":"3fe0a9760357","model":"mock-llm-small","agent_version":"v2","input_tokens":68,"output_tokens":30,"cost_usd":0.000028,"llm_ms":1689.5}
```

[Trace lỗi](screenshots/jaeger-error-trace.png), ID `0873321e89904d55082cafb89d52eccb`. Root request trả 503. Span `chat mock-llm-small` có event `exception` với `error.type=upstream_unavailable`.

```json
{"ts":"2026-11-25T09:28:06.475273+00:00","level":"INFO","service":"observable-agent","instance":"dd5fefa79f57","event":"llm_error","trace_id":"0873321e89904d55082cafb89d52eccb","span_id":"c0b42dd01dd29eb0","request_id":"415aedf40b81","error":"Upstream LLM error: 503 Service Unavailable (mock)"}
```

## 5. Benchmark scaling

| Instances | RPS /ask | p50 (ms) | p95 (ms) | p99 (ms) | Failures / requests |
|---:|---:|---:|---:|---:|---:|
| 1 | 52.72 | 230 | 1600 | 3500 | 64 / 6262 |
| 3 | 58.08 | 200 | 840 | 1700 | 68 / 6881 |

Locust headless dùng 100 users, ramp-up 10 users/giây và 120 giây mỗi lượt. Dùng --no-deps khi chạy Locust để Compose giữ đúng số agent đã đặt. Bảng lấy dòng /ask từ CSV. RPS thay đổi từ 52.72 thành 58.08; p95 từ 1600 ms thành 840 ms.

Nhiều replica chia tải xử lý của agent và có thể giảm xếp hàng. Delay của mock LLM trong từng request vẫn còn khi tăng replica. So sánh thêm panel LLM latency với HTTP latency để phân biệt thời gian ở model và thời gian xử lý ngoài model. Đây là kết quả của một lần chạy trên máy lab, có ảnh hưởng của scheduler và tải nền.

## 6. Kết luận

1. Concurrency cao không bảo đảm RPS tăng theo tỷ lệ. p95 có thể vượt SLO dù đa số request thành công.
2. Accuracy và chi phí trên mỗi câu đúng giúp chọn phiên bản agent.
3. Metrics báo động theo thời gian, trace và log định vị nguyên nhân của từng request, còn eval bắt được hồi quy chất lượng.

Nếu chạy production thật, thêm synthetic check bên ngoài Nginx để đo lỗi người dùng thấy và eval định kỳ để phát hiện chất lượng giảm sau deploy.
