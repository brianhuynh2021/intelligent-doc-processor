FROM python:3.11-slim

# System dependencies: OCR (tesseract + Vietnamese), PDF rasterization (poppler),
# and libpq for psycopg2.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    poppler-utils \
    tesseract-ocr \
    tesseract-ocr-vie \
    && rm -rf /var/lib/apt/lists/*

# uv binary (pinned) from the official image
COPY --from=ghcr.io/astral-sh/uv:0.11.21 /uv /uvx /bin/

WORKDIR /app

# uv runs against the base image's Python; install into /app/.venv and put it
# on PATH so alembic/python/uvicorn resolve directly (entrypoint stays simple).
ENV UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

# Layer 1: dependencies only (cached unless pyproject.toml/uv.lock change).
# --frozen: fail if the lock is out of date (no implicit re-resolve in prod).
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Layer 2: application code
COPY ./app ./app
COPY ./infra ./infra
COPY ./alembic ./alembic
COPY ./alembic.ini ./
COPY scripts/ ./scripts/

COPY docker/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
# Production default (no --reload). docker-compose can override for local dev.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
