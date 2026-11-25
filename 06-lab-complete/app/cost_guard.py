from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException

from .config import settings
from .redis_client import r

NANODOLLARS_PER_USD = 1_000_000_000
INPUT_PRICE = 150
OUTPUT_PRICE = 600


def check_budget(input_tokens: int) -> tuple[str, int]:
    now = datetime.now(timezone.utc)
    if settings.daily_budget_usd:
        key, ttl, budget = f"day14:cost:{now:%Y-%m-%d}", 172800, settings.daily_budget_usd
    else:
        key, ttl, budget = f"day14:cost:{now:%Y-%m}", 2764800, settings.monthly_budget_usd
    spent = int(r.get(key) or 0)
    minimum = input_tokens * INPUT_PRICE + OUTPUT_PRICE
    if spent + minimum > Decimal(budget) * NANODOLLARS_PER_USD:
        raise HTTPException(402, "LLM budget exhausted")
    return key, ttl


def record_cost(period: tuple[str, int], input_tokens: int, output_tokens: int) -> float:
    key, ttl = period
    cost = input_tokens * INPUT_PRICE + output_tokens * OUTPUT_PRICE
    with r.pipeline() as transaction:
        transaction.incrby(key, cost)
        transaction.expire(key, ttl, nx=True)
        transaction.execute()
    return cost / NANODOLLARS_PER_USD
