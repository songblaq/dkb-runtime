"""Pure unit tests for markdown extraction helpers (no database)."""

from __future__ import annotations

from pathlib import Path

from dkb_runtime.services.extractor import (
    _extract_evidence,
    _extract_name_from_md,
    _extract_summary,
)


def test_extract_name_from_md_heading(fixtures_dir: Path) -> None:
    md = fixtures_dir / "sample_skill" / "SKILL.md"
    content = md.read_text(encoding="utf-8")
    name = _extract_name_from_md(content, md)
    assert name == "Sample Fixture Skill"


def test_extract_name_from_md_falls_back_to_stem() -> None:
    content = "No heading here\njust text."
    assert _extract_name_from_md(content, Path("/repo/agents/helper.md")) == "helper"


def test_extract_summary_skips_headers_until_paragraph() -> None:
    content = """# Title

First paragraph line one.
Second line same paragraph.

Next paragraph."""
    summary = _extract_summary(content)
    assert summary is not None
    assert "First paragraph" in summary
    assert "Second line" in summary
    assert "Next paragraph" not in summary


def test_extract_summary_only_headers_returns_none() -> None:
    assert _extract_summary("# Only\n## Headers") is None


def test_extract_evidence_includes_summary_code_and_license() -> None:
    content = """# Tool

This is a **tool** for agents.

```python
print("hi")
```

Uses MCP for function_call.
"""
    items = _extract_evidence(content, "MIT License text here " * 5)
    kinds = {e["evidence_kind"] for e in items}
    assert "summary" in kinds
    assert "usage_example" in kinds
    assert "tool_reference" in kinds
    assert "license_excerpt" in kinds


def test_extract_evidence_no_license_omits_license_kind() -> None:
    content = "# X\n\nPlain **agent** line.\n"
    items = _extract_evidence(content, None)
    assert all(e["evidence_kind"] != "license_excerpt" for e in items)
