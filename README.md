# repo-digest

Turn a GitHub repository's history into readable release notes: features, fixes and breaking changes, written by an LLM (DeepSeek by default; any OpenAI-compatible provider works).

> 🚧 Work in progress. This is my first Python project and part of my [move into AI engineering](https://github.com/grisdale-dev). The commit history shows the learning as it happened.

## Plan

- [x] **1. GitHub client:** parse repo input, fetch commits for a date range (`src/repo_digest/github.py`)
- [x] **2. Summariser:** commits → structured release notes with an LLM + Pydantic, plus validation and retries
- [x] **3. CLI:** `repo-digest owner/repo --since 2026-09-01` prints Markdown
- [x] **4. Web API + page:** FastAPI endpoint and a simple front end
- [ ] **5. Guardrails:** per-visitor rate limit, result cache, daily token budget
- [ ] **6. Deploy:** live public URL
- [ ] **7. Evaluate:** compare against real human-written release notes for a few projects
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
