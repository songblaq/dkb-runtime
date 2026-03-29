from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select

from dkb_runtime.db.session import SessionLocal
from dkb_runtime.models import DimensionModel, Pack

ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "config"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def upsert_dimension_model(session) -> None:
    payload = load_json(CONFIG_DIR / "dimension_model_v0_1.json")
    existing = session.scalar(
        select(DimensionModel).where(DimensionModel.model_key == payload["model_key"])
    )
    if existing:
        existing.version = payload["version"]
        existing.description = payload.get("description")
        existing.config = payload
        existing.is_active = True
    else:
        session.add(
            DimensionModel(
                model_key=payload["model_key"],
                version=payload["version"],
                description=payload.get("description"),
                config=payload,
                is_active=True,
            )
        )


def upsert_packs(session) -> None:
    payload = load_json(CONFIG_DIR / "pack_examples_v0_1.json")
    for pack in payload.get("packs", []):
        existing = session.scalar(select(Pack).where(Pack.pack_key == pack["pack_key"]))
        values = dict(
            pack_name=pack["pack_name"],
            pack_goal=pack["goal"],
            pack_type=pack["pack_type"],
            selection_policy=pack.get("selection_policy", {}),
            status="draft",
        )
        if existing:
            for key, value in values.items():
                setattr(existing, key, value)
        else:
            session.add(Pack(pack_key=pack["pack_key"], **values))


def main() -> None:
    with SessionLocal() as session:
        upsert_dimension_model(session)
        upsert_packs(session)
        session.commit()
    print("Seed loaded successfully.")


if __name__ == "__main__":
    main()
