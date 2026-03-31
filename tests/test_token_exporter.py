from __future__ import annotations

from dkb_runtime.services.token_exporter import export_batch_markdown, export_compact_markdown


def test_export_compact_markdown_single_block():
    d = {
        "preferred_name": "My Skill",
        "normalized_summary": "Does one thing well.\nSecond line ignored for desc.",
        "canonical_meta": {"repo": "github.com/a/b"},
        "scores": {
            "form.skillness": {"score": 0.81},
            "function.coding": {"score": 0.75},
        },
        "verdict": {"recommendation": "preferred", "trust": "verified", "legal": "clear"},
    }
    out = export_compact_markdown([d])
    assert "# My Skill" in out
    assert "desc: Does one thing well." in out
    assert "src: github.com/a/b" in out
    assert "skill=0.81" in out
    assert "coding=0.75" in out
    assert "## verdict: recommended" in out
    assert "trust: verified | legal: clear" in out
    assert "---" not in out


def test_export_compact_markdown_multiple_separated():
    a = {"preferred_name": "A", "normalized_summary": "sa", "scores": {}, "verdict": {}}
    b = {"preferred_name": "B", "normalized_summary": "sb", "scores": {}, "verdict": {}}
    out = export_compact_markdown([a, b])
    assert out.count("---") == 1
    assert "# A" in out and "# B" in out


def test_export_batch_markdown_header_and_pack_key():
    d = {"preferred_name": "X", "normalized_summary": "sx", "scores": {}, "verdict": {}}
    out = export_batch_markdown([d], "My Pack", pack_key="my-pack")
    assert "# My Pack" in out
    assert "key: my-pack" in out
    assert "items: 1" in out
    assert "# X" in out
