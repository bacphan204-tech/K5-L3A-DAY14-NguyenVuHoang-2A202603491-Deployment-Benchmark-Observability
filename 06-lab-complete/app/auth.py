from secrets import compare_digest
from typing import Annotated

from fastapi import Header, HTTPException

from .config import settings


def verify_api_key(key: Annotated[str | None, Header(alias="X-API-Key")] = None) -> str:
    if not key or not settings.agent_api_key or not compare_digest(
        key.encode(), settings.agent_api_key.encode()
    ):
        raise HTTPException(401, "Missing or invalid API key")
    return key
