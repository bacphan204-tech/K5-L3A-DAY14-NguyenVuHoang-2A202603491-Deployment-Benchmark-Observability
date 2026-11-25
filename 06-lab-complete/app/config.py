import os
from dataclasses import dataclass, field

@dataclass(frozen=True)
class Settings:
    port: int = field(default_factory=lambda: int(os.getenv("PORT", "8000")))
    environment: str = field(default_factory=lambda: os.getenv("ENVIRONMENT", "development"))
    agent_api_key: str = field(default_factory=lambda: os.getenv("AGENT_API_KEY", ""))
    redis_url: str = field(default_factory=lambda: os.getenv("REDIS_URL", "redis://localhost:6379/0"))
    rate_limit_per_minute: int = field(default_factory=lambda: int(os.getenv("RATE_LIMIT_PER_MINUTE", "10")))
    daily_budget_usd: str = field(default_factory=lambda: os.getenv("DAILY_BUDGET_USD", ""))
    monthly_budget_usd: str = field(default_factory=lambda: os.getenv("MONTHLY_BUDGET_USD", "10"))

settings = Settings()
