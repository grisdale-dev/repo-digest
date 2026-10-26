"""Settings from environment variables (and a local .env file in development)."""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-flash"


@dataclass(frozen=True)
class Settings:
    llm_api_key: str
    llm_base_url: str
    llm_model: str
    github_token: str | None
    daily_token_limit: int
    rate_limit_requests: int = 10  # per visitor, per window
    rate_limit_window_seconds: int = 3600
    cache_ttl_seconds: int = 3600
    trust_proxy_headers: bool = False  # True only behind a proxy that sets X-Forwarded-For


def _env_int(name: str, default: int) -> int:
    return int(os.environ.get(name) or default)


def _env_bool(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes")


def load_settings() -> Settings:
    load_dotenv()
    api_key = os.environ.get("LLM_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("LLM_API_KEY is not set. Copy .env.example to .env and fill it in.")
    return Settings(
        llm_api_key=api_key,
        llm_base_url=os.environ.get("LLM_BASE_URL") or DEFAULT_BASE_URL,
        llm_model=os.environ.get("LLM_MODEL") or DEFAULT_MODEL,
        github_token=os.environ.get("GITHUB_TOKEN") or None,
        daily_token_limit=_env_int("DAILY_TOKEN_LIMIT", 500_000),
        rate_limit_requests=_env_int("RATE_LIMIT_REQUESTS", 10),
        rate_limit_window_seconds=_env_int("RATE_LIMIT_WINDOW_SECONDS", 3600),
        cache_ttl_seconds=_env_int("CACHE_TTL_SECONDS", 3600),
        trust_proxy_headers=_env_bool("TRUST_PROXY_HEADERS"),
    )
