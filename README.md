![CI](https://github.com/songblaq/dkb-runtime/actions/workflows/ci.yml/badge.svg)

# dkb-runtime

DKB(Directive Knowledge Base) 명세를 구현한 **설치 가능한 Python 패키지**.

## What is this?

`dkb-runtime`은 DKB의 핵심 엔진입니다. 이 패키지를 설치하면 자신의 프로젝트에 DKB 인스턴스를 만들 수 있습니다.

## Part of DKB Ecosystem

| Repository | Role |
|---|---|
| [directive-knowledge-base](../directive-knowledge-base) | 개념, 명세, 웹 문서 |
| **dkb-runtime** (this) | 설치 가능한 구현체 |
| [ai-store-dkb](../ai-store-dkb) | AI 리서치/수집 스토어 |
| [agent-prompt-dkb](../agent-prompt-dkb) | 에이전트 프롬프트 큐레이션 |

## Tech Stack

- Python 3.12+
- FastAPI
- SQLAlchemy 2.0+
- Alembic
- PostgreSQL 16+ with pgvector
- pydantic 2.8+

## Quick Start

```bash
# 1. Clone
git clone <repo-url>
cd dkb-runtime

# 2. Environment
cp .env.example .env
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# 3. Database
docker compose up -d postgres
alembic upgrade head
python scripts/load_seed.py

# 4. Run
uvicorn dkb_runtime.main:app --reload
```

## Project Structure

```
dkb_runtime/          # Python package
  core/               # Configuration
  db/                 # Database session
  models/             # SQLAlchemy ORM models
  schemas/            # Pydantic schemas
  api/routes/         # FastAPI endpoints
  services/           # Business logic (collector, extractor, scoring, etc.)
alembic/              # Database migrations
schema/               # Raw SQL DDL
config/               # Dimension model, verdict policy, pack definitions
scripts/              # CLI utilities
```

## Services

| Service | Purpose |
|---|---|
| collector | Acquires source snapshots (git clone/fetch) |
| extractor | Parses snapshots into raw directives |
| canonicalizer | Deduplicates and normalizes directives |
| scoring | Computes DG dimension scores |
| verdict | Applies policy rules for verdicts |
| pack_engine | Builds curated packs |
| exporter | Exports packs to Claude Code / SKILL.md formats |
| audit | Logs operations for traceability |

## License

MIT
