FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY dkb_runtime ./dkb_runtime
COPY alembic.ini ./
COPY alembic ./alembic
COPY schema ./schema
COPY config ./config
COPY scripts ./scripts

RUN pip install --no-cache-dir -e .

EXPOSE 8000

CMD ["uvicorn", "dkb_runtime.main:app", "--host", "0.0.0.0", "--port", "8000"]
