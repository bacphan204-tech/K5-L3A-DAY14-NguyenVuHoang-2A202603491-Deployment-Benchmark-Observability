import json
import logging
from contextlib import asynccontextmanager
from time import perf_counter
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from redis import RedisError

from utils.mock_llm import ask as llm_ask

from .auth import verify_api_key
from .config import settings
from .cost_guard import check_budget, record_cost
from .rate_limiter import check_rate_limit
from .redis_client import r, redis_healthy

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(json.dumps({"event": "startup", "environment": settings.environment}))
    try:
        yield
    finally:
        r.close()
        logger.info(json.dumps({"event": "graceful_shutdown"}))


app = FastAPI(title="Production AI Agent", lifespan=lifespan)


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    user_id: str | None = None


@app.middleware("http")
async def log_request(request: Request, call_next):
    start = perf_counter()
    response = await call_next(request)
    logger.info(json.dumps({
        "event": "request", "method": request.method,
        "route": getattr(request.scope.get("route"), "path", "unmatched"),
        "status": response.status_code, "ms": round((perf_counter() - start) * 1000, 2),
    }))
    return response


@app.exception_handler(RedisError)
async def redis_unavailable(request: Request, exc: RedisError):
    logger.warning(json.dumps({"event": "redis_unavailable", "error": type(exc).__name__}))
    return JSONResponse({"detail": "Redis unavailable"}, status_code=503)


@app.get("/health")
def health():
    return {"status": "ok", "environment": settings.environment}


@app.get("/ready")
def ready():
    if not redis_healthy():
        raise HTTPException(503, "Redis unavailable")
    return {"status": "ready"}


@app.post("/ask")
def ask(body: AskRequest, api_key: Annotated[str, Depends(verify_api_key)]):
    question = body.question.strip()
    if not question:
        raise HTTPException(422, "Question must contain text")
    check_rate_limit(api_key)
    input_tokens = max(1, (len(question) + 3) // 4)
    period = check_budget(input_tokens)
    answer = llm_ask(question)
    output_tokens = max(1, (len(answer) + 3) // 4)
    cost = record_cost(period, input_tokens, output_tokens)
    return {"question": question, "answer": answer, "estimated_cost_usd": cost}
