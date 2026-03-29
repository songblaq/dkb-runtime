.PHONY: setup db-up db-down migrate seed run lint test

setup:
	python -m venv .venv
	. .venv/bin/activate && pip install -e ".[dev]"

db-up:
	docker compose up -d postgres

db-down:
	docker compose down

migrate:
	alembic upgrade head

seed:
	python scripts/load_seed.py

run:
	uvicorn dkb_runtime.main:app --reload

lint:
	ruff check dkb_runtime scripts tests

test:
	pytest -q
