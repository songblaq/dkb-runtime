FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY dkb_runtime ./dkb_runtime
COPY alembic.ini ./
COPY alembic ./alembic
COPY schema ./schema
COPY config ./config
COPY scripts ./scripts

RUN pip install --no-cache-dir .

EXPOSE 8000

CMD ["uvicorn", "dkb_runtime.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
