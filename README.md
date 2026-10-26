# repo-digest

Turn a GitHub repository's history into readable release notes: features, fixes and breaking changes, written by Claude.

> 🚧 Work in progress. This is my first Python project and part of my [move into AI engineering](https://github.com/grisdale-dev). The commit history shows the learning as it happened.

## Plan

- [x] **1. GitHub client:** parse repo input, fetch commits for a date range (`src/repo_digest/github.py`)
- [ ] **2. Summariser:** commits → structured release notes with Claude + Pydantic, plus validation and retries
- [ ] **3. CLI:** `repo-digest owner/repo --since 2026-09-01` prints Markdown
- [ ] **4. Web API + page:** FastAPI endpoint and a simple front end
- [ ] **5. Guardrails:** per-visitor rate limit, result cache, daily token budget
- [ ] **6. Deploy:** live public URL
- [ ] **7. Evaluate:** compare against real human-written release notes for a few projects
- [ ] **8. Publish:** PyPI package and write-up

## Development

Requires [uv](https://docs.astral.sh/uv/).

```sh
uv sync                 # install dependencies into .venv
cp .env.example .env    # then fill in your keys (never commit .env)
uv run pytest           # tests
uv run ruff check       # lint
uv run ruff format      # format
uv run mypy src         # type-check (strict)
```
