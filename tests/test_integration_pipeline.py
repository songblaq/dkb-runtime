from __future__ import annotations

import shutil
from uuid import uuid4

from dkb_runtime.models import Pack, Source
from dkb_runtime.services.canonicalizer import canonicalize
from dkb_runtime.services.collector import collect_source
from dkb_runtime.services.exporter import export_snapshot
from dkb_runtime.services.extractor import extract_directives
from dkb_runtime.services.pack_engine import build_pack
from dkb_runtime.services.scoring import score_directive
from dkb_runtime.services.verdict import evaluate_directive


def test_end_to_end_local_collect_extract_canonicalize_score_verdict_pack_export(
    db, tmp_path, fixtures_dir, dimension_model
):
    tree = tmp_path / "repo"
    shutil.copytree(fixtures_dir / "sample_repo", tree)
    (tree / "SKILL.md").write_text("# Integration Skill\n\n```bash\necho ok\n```\n", encoding="utf-8")
    src = Source(source_kind="local_folder", origin_uri=str(tree))
    db.add(src)
    db.commit()
    db.refresh(src)

    snap_result = collect_source(db, src.source_id)
    assert snap_result.capture_status == "captured"

    extracted = extract_directives(db, snap_result.snapshot_id)
    assert extracted

    raw_ids = [r.raw_directive_id for r in extracted]
    canon_results = canonicalize(db, raw_ids)
    db.commit()
    assert canon_results

    directive_id = canon_results[0].directive_id
    score_directive(db, directive_id, dimension_model.dimension_model_id)
    db.commit()

    evaluate_directive(db, directive_id)
    db.commit()

    pack = Pack(
        pack_key=f"int-{uuid4().hex[:8]}",
        pack_name="Integration",
        pack_goal="test",
        pack_type="custom",
        selection_policy={
            "trust_states": ["reviewing", "verified"],
            "legal_states": ["clear", "custom", "no_license"],
            "max_items": 20,
        },
        status="draft",
    )
    db.add(pack)
    db.commit()
    db.refresh(pack)

    build_pack(db, pack.pack_id)
    db.commit()

    out_dir = tmp_path / "export"
    out_dir.mkdir()
    export_snapshot(db, pack.pack_id, out_dir)
    db.commit()

    assert list(out_dir.glob("*.json"))
