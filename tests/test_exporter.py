from __future__ import annotations

import json

from dkb_runtime.models import CanonicalDirective, DimensionScore, Pack, PackItem
from dkb_runtime.services.exporter import export_claude_code, export_skill_md, export_snapshot


def _pack_with_item(db, dimension_model) -> Pack:
    c = CanonicalDirective(
        preferred_name="My Agent", normalized_summary="Does agent things with tools"
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    for key, val in (("skillness", 0.2), ("agentness", 0.95)):
        db.add(
            DimensionScore(
                directive_id=c.directive_id,
                dimension_model_id=dimension_model.dimension_model_id,
                dimension_group="form",
                dimension_key=key,
                score=val,
                confidence=0.7,
                explanation="t",
            )
        )
    pack = Pack(
        pack_key="epack",
        pack_name="E",
        pack_goal="g",
        pack_type="custom",
        selection_policy={},
        status="active",
    )
    db.add(pack)
    db.flush()
    db.add(
        PackItem(
            pack_id=pack.pack_id,
            directive_id=c.directive_id,
            inclusion_reason="test",
            priority_weight=1.0,
        )
    )
    db.commit()
    db.refresh(pack)
    return pack


def test_export_claude_code_creates_agents_and_settings(db, dimension_model, tmp_path):
    pack = _pack_with_item(db, dimension_model)
    out = tmp_path / "cc"
    result = export_claude_code(db, pack.pack_id, out)
    db.commit()
    assert result.format == "claude-code"
    assert (out / "settings.json").exists()
    agents = list((out / "agents").glob("*.md"))
    skills = list((out / "skills").glob("*.md"))
    assert agents or skills
    data = json.loads((out / "settings.json").read_text(encoding="utf-8"))
    assert data["pack_key"] == "epack"


def test_export_skill_md_writes_skill_files(db, dimension_model, tmp_path):
    pack = _pack_with_item(db, dimension_model)
    out = tmp_path / "sk"
    result = export_skill_md(db, pack.pack_id, out)
    db.commit()
    assert result.file_count >= 1
    md_files = list(out.rglob("SKILL.md"))
    assert md_files
    assert "My Agent" in md_files[0].read_text(encoding="utf-8")


def test_export_snapshot_valid_json(db, dimension_model, tmp_path):
    pack = _pack_with_item(db, dimension_model)
    result = export_snapshot(db, pack.pack_id, tmp_path)
    db.commit()
    assert result.output_path.exists()
    payload = json.loads(result.output_path.read_text(encoding="utf-8"))
    assert payload["pack"]["pack_key"] == "epack"
    assert len(payload["items"]) == 1
