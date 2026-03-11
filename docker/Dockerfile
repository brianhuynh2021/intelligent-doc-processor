FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy and install dependencies
COPY requirements.txt .
COPY requirements-dev.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt -r requirements-dev.txt

COPY ./app ./app

COPY ./infra ./infra

COPY ./alembic ./alembic
COPY ./alembic.ini .

COPY scripts/ /app/scripts/
COPY docker/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
