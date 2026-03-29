from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from dkb_runtime.core.config import get_settings
from dkb_runtime.core.paths import repo_root
from dkb_runtime.models import DimensionModel
from dkb_runtime.models.base import Base


@pytest.fixture(scope="session")
def engine():
    settings = get_settings()
    eng = create_engine(settings.database_url, future=True)
    try:
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as e:
        pytest.skip(f"PostgreSQL not reachable ({type(e).__name__}): {e}")
    with eng.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    with eng.connect() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS dkb"))
        conn.commit()
    Base.metadata.create_all(bind=eng)
    yield eng
    Base.metadata.drop_all(bind=eng)


@pytest.fixture
def db(engine):
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        with engine.begin() as conn:
            for table in reversed(Base.metadata.sorted_tables):
                if getattr(table, "schema", None) == "dkb":
                    conn.execute(table.delete())


@pytest.fixture
def dimension_model(db) -> DimensionModel:
    cfg = json.loads(
        (repo_root() / "config" / "dimension_model_v0_1.json").read_text(encoding="utf-8")
    )
    m = DimensionModel(
        model_key="test-dg-v0-1",
        version="0.1.0",
        description="test model",
        config=cfg,
        is_active=True,
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).resolve().parent / "fixtures"
