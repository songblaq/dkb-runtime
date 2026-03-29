#!/usr/bin/env bash
set -euo pipefail

cp -n .env.example .env || true
docker compose up -d postgres
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
python scripts/load_seed.py
echo "Bootstrap complete. Run: uvicorn dkb_runtime.main:app --reload"
