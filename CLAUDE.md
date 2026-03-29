# DKB Runtime

## What is this?
Implementation engine for the DKB (Directive Knowledge Base) specification.
Installable Python package providing FastAPI server, SQLAlchemy models, and processing pipeline.

## Tech Stack
- Python 3.12+
- FastAPI 0.115+
- SQLAlchemy 2.0+ (sync Session)
- Alembic (migrations)
- PostgreSQL 16+ with pgvector extension
- Pydantic 2.8+
- Hatchling (build)

## Setup
```bash
pip install -e ".[dev]"       # Install with dev deps
cp .env.example .env          # Configure environment
make db-up                    # Start PostgreSQL (Docker)
make migrate                  # Apply schema
make seed                     # Load dimension model + pack definitions
make run                      # Start FastAPI server on :8000
```

## Project Structure
```
dkb_runtime/
  core/config.py              # Pydantic Settings
  db/session.py               # SQLAlchemy sync Session + pgvector
  models/                     # ORM models (source, directive, scoring, verdict)
  schemas/                    # Pydantic request/response schemas
  api/
    app.py                    # FastAPI application
    deps.py                   # Dependency injection (DbSession)
    routes/                   # Endpoint handlers
  services/                   # Business logic (8 services)
config/                       # JSON configs (dimension model, verdict policy, pack examples)
schema/                       # Raw SQL DDL
alembic/                      # Database migrations
tests/                        # pytest tests
```

## Service Pipeline (8 services, in order)
1. `audit.py` — Log operations for traceability
2. `collector.py` — Clone/fetch sources, create snapshots
3. `extractor.py` — Parse snapshots into raw directives + evidence
4. `canonicalizer.py` — Deduplicate, normalize into canonical directives
5. `scoring.py` — Compute DG dimension scores (34 dimensions)
6. `verdict.py` — Apply policy rules (5-axis verdict)
7. `pack_engine.py` — Build curated packs
8. `exporter.py` — Export packs to Claude Code, SKILL.md, snapshot formats

## Important Notes
- DB session is SYNC (not async) — see `db/session.py`
- Services use sync `sqlalchemy.orm.Session` — aligned with `db/session.py`
- All services raise `NotImplementedError` — implementation needed
- Schema is in `dkb` PostgreSQL schema namespace
- Config files define the dimension model and verdict policy

## Testing
```bash
make lint     # ruff check
make test     # pytest (requires PostgreSQL)
```

## Ecosystem
Part of 4-repo DKB ecosystem. This is the core engine used by ai-store-dkb and agent-prompt-dkb.
