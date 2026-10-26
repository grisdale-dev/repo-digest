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
        daily_token_limit=int(os.environ.get("DAILY_TOKEN_LIMIT") or 500_000),
    )
