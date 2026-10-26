FROM python:3.14-slim

COPY --from=ghcr.io/astral-sh/uv:0.13.5 /uv /bin/uv

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_NO_DEV=1

# Dependencies first, so code changes don't invalidate this layer.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-install-project

COPY src ./src
RUN uv sync --locked

ENV PATH="/app/.venv/bin:$PATH" \
    PORT=8000 \
    # Azure Container Apps (and most hosts) sit behind a proxy that appends the client IP.
    TRUST_PROXY_HEADERS=true

USER nobody
EXPOSE 8000
CMD ["sh", "-c", "exec uvicorn repo_digest.web:app --host 0.0.0.0 --port \"$PORT\""]
