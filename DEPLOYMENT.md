# Deployment Information

## Public URL

https://agent-production-b68ac0a3.up.railway.app

## Platform

Railway. Deploy Dockerfile từ thư mục `06-lab-complete/` và gắn Redis cùng project. Render Blueprint trong cùng thư mục là cấu hình thay thế.

## Environment variables

- `AGENT_API_KEY` — đặt bằng secret của service.
- `REDIS_URL` — tham chiếu tới URL nội bộ của Redis.
- `ENVIRONMENT` — `production`.
- `PORT` — giá trị Railway cấp hoặc 8000 khi chạy local.
- `RATE_LIMIT_PER_MINUTE`, `MONTHLY_BUDGET_USD` — có giá trị mặc định, điều chỉnh qua env nếu cần.

## Kết quả kiểm tra URL public

- GET /health → 200
- GET /ready → 200
- POST /ask thiếu key → 401
- POST /ask có key → 200

## Lệnh tái kiểm tra

Kiểm tra trước deploy với agent + Redis trong Docker Compose local cho mã 200, 200, 401, 200. Input chỉ có khoảng trắng trả 422.

Đặt `BASE` và `AGENT_API_KEY` trong terminal riêng. Bốn lệnh in mã HTTP theo thứ tự 200, 200, 401, 200.

```bash
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/health"
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/ready"
curl -sS -o /dev/null -w '%{http_code}\n' -H 'Content-Type: application/json' -d '{"question":"Hello"}' "$BASE/ask"
curl -sS -o /dev/null -w '%{http_code}\n' -H 'Content-Type: application/json' -H "X-API-Key: $AGENT_API_KEY" -d '{"question":"Hello"}' "$BASE/ask"
```
