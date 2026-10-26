"""Web app: a JSON API plus a single-page front end.

Run locally with `uv run repo-digest-web` and open http://127.0.0.1:8000.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, time, timedelta
from importlib.resources import files

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from openai import APIError, OpenAI
from pydantic import BaseModel, Field

from repo_digest import digest
from repo_digest.config import Settings, load_settings
from repo_digest.digest import CommitRange, DateRange, RefRange
from repo_digest.github import make_client, parse_repo
from repo_digest.notes import ReleaseNotes
from repo_digest.summarise import SummaryError, summarise


class DigestRequest(BaseModel):
    repo: str = Field(max_length=200, examples=["astral-sh/uv"])
    since: date | None = Field(None, description="Start date (inclusive)")
    until: date | None = Field(None, description="End date (inclusive)")
    base: str | None = Field(None, max_length=100, description="Tag, branch or SHA to start after")
    head: str | None = Field(None, max_length=100, description="Tag, branch or SHA to end at")


class TokenUsage(BaseModel):
    input_tokens: int
    output_tokens: int


class DigestResponse(BaseModel):
    repo: str
    range: str
    model: str
    commits_used: int
    truncated: bool
    notes: ReleaseNotes
    markdown: str
    html: str
    usage: TokenUsage


def _midnight(d: date) -> datetime:
    return datetime.combine(d, time(), tzinfo=UTC)


def _to_range(body: DigestRequest) -> CommitRange:
    """Raises ValueError with a user-facing message for invalid combinations."""
    if body.base or body.head:
        if not body.base:
            raise ValueError("Give a starting tag as well as an ending one")
        if body.since or body.until:
            raise ValueError("Use either dates or tags, not both")
        return RefRange(body.base.strip(), (body.head or "HEAD").strip())
    # The form's end date is inclusive, so the range ends at the following midnight.
    until = _midnight(body.until) + timedelta(days=1) if body.until else datetime.now(UTC)
    if body.since is None:
        return digest.last_days(now=until)
    return DateRange(_midnight(body.since), until)


def create_app(settings: Settings | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        s = settings or load_settings()
        app.state.settings = s
        app.state.llm = OpenAI(api_key=s.llm_api_key, base_url=s.llm_base_url)
        with make_client(s.github_token) as gh:
            app.state.github = gh
            yield

    app = FastAPI(title="repo-digest", lifespan=lifespan)
    index_html = (files("repo_digest") / "static" / "index.html").read_text(encoding="utf-8")

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def index() -> str:
        return index_html

    @app.get("/healthz", include_in_schema=False)
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    # Plain `def` (not async): FastAPI runs it in a thread pool, so the blocking HTTP calls
    # to GitHub and the LLM don't stall other requests.
    @app.post("/api/digest")
    def create_digest(body: DigestRequest, request: Request) -> DigestResponse:
        state = request.app.state
        try:
            owner, repo = parse_repo(body.repo)
            rng = _to_range(body)
        except ValueError as e:
            raise HTTPException(400, str(e)) from None

        try:
            commits = digest.fetch_range(state.github, owner, repo, rng)
        except httpx.HTTPStatusError as e:
            status = 404 if e.response.status_code == 404 else 503
            raise HTTPException(status, digest.github_error_message(e, rng)) from None
        except httpx.TransportError:
            raise HTTPException(503, "Couldn't reach GitHub. Please try again.") from None
        if not commits:
            raise HTTPException(404, f"No commits in {owner}/{repo} for {rng.describe()}.")

        model: str = state.settings.llm_model
        try:
            result = summarise(state.llm, f"{owner}/{repo}", commits, model=model)
        except SummaryError:
            raise HTTPException(502, "The model didn't produce usable notes. Try again.") from None
        except APIError:
            raise HTTPException(503, "The language model is unavailable right now.") from None

        return DigestResponse(
            repo=f"{owner}/{repo}",
            range=rng.describe(),
            model=model,
            commits_used=result.commits_used,
            truncated=result.truncated,
            notes=result.notes,
            markdown=result.notes.to_markdown(repo=(owner, repo)),
            html=result.notes.to_html(repo=(owner, repo)),
            usage=TokenUsage(
                input_tokens=result.usage.input_tokens, output_tokens=result.usage.output_tokens
            ),
        )

    return app


app = create_app()


def run() -> None:
    import uvicorn

    uvicorn.run("repo_digest.web:app", host="127.0.0.1", port=8000, reload=False)
