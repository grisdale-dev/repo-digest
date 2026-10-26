# repo-digest

Turn a GitHub repository's history into readable release notes: features, fixes and breaking changes, written by an LLM (DeepSeek by default; any OpenAI-compatible provider works).

**Try it: https://repo-digest.greenmeadow-8bea4d3b.newzealandnorth.azurecontainerapps.io**

> 🚧 Work in progress. This is my first Python project and part of my [move into AI engineering](https://github.com/grisdale-dev). The commit history shows the learning as it happened.

## Plan

- [x] **1. GitHub client:** parse repo input, fetch commits for a date range (`src/repo_digest/github.py`)
- [x] **2. Summariser:** commits → structured release notes with an LLM + Pydantic, plus validation and retries
- [x] **3. CLI:** `repo-digest owner/repo --since 2026-09-01` prints Markdown
- [x] **4. Web API + page:** FastAPI endpoint and a simple front end
- [x] **5. Guardrails:** per-visitor rate limit, result cache, daily token budget
- [x] **6. Deploy:** live public URL
- [x] **7. Evaluate:** compare against real human-written release notes, see [evals/](evals/README.md)
- [ ] **8. Publish:** PyPI package and write-up

## Usage

Needs an API key for an OpenAI-compatible LLM provider (DeepSeek by default) in `.env`. See `.env.example`.

```sh
uv run repo-digest astral-sh/uv                          # last 30 days
uv run repo-digest astral-sh/uv --since 2026-10-01       # from a date until now
uv run repo-digest astral-sh/uv --from 0.9.0 --to 0.9.1  # between two tags
uv run repo-digest astral-sh/uv --from 0.9.0 -o NOTES.md # tag to latest, written to a file
```

Release notes go to stdout as Markdown. Progress and token usage go to stderr, so piping and redirecting work.

### Web app

```sh
uv run repo-digest-web   # then open http://127.0.0.1:8000
```

The page posts to `POST /api/digest` (`{"repo": "owner/repo", "base": "v1.0", "head": "v1.1"}` or `"since"`/`"until"` dates). Interactive API docs are at `/docs`. All model-written text is HTML-escaped on the server before it reaches the page.

The public demo is protected by three in-memory guards (configured in `.env`, see `.env.example`):

| Guard | Default | What happens |
|---|---|---|
| Cache | 1 hour | Identical requests are served from cache: free, instant, not rate limited |
| Rate limit | 10 per visitor per hour | `429` with `Retry-After` |
| Daily token budget | 500k tokens (UTC day) | `503` until midnight UTC; failed attempts count too |

State resets on restart. That's acceptable because the LLM account is prepaid, so the most the demo can ever spend is the balance.

## Development

Requires [uv](https://docs.astral.sh/uv/).

```sh
uv sync                 # install dependencies into .venv
cp .env.example .env    # then fill in your keys (never commit .env)
uv run pytest           # tests
uv run ruff check       # lint
uv run ruff format      # format
uv run mypy src tests   # type-check (strict)
```

## Evaluation

Against the maintainers' own release notes for 7 real releases, repo-digest covers **70%** of the
changes they list, and **97%** of its entries accurately describe their commits (judged by an
LLM, averaged over 3 runs). The harness, method and what it found are in
[evals/README.md](evals/README.md).

## Deployment

Runs on **Azure Container Apps** (New Zealand North): one replica at most (the guards are in-memory), scales to zero when idle, logs off. The image is built and smoke-tested by GitHub Actions and published to GitHub Container Registry, so no Azure Container Registry is needed.

Deploy a new version (after the "Container image" workflow has published it):

```sh
az containerapp update --subscription "Azure for Students" -n repo-digest -g rg-repo-digest --image ghcr.io/grisdale-dev/repo-digest:<commit-sha>
```

Secrets are set on the container app (`az containerapp secret set`) and referenced from env vars, never baked into the image.

