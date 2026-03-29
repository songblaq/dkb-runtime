"""Extractor service — parses snapshots into raw directives."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from dkb_runtime.models import Evidence, RawDirective, SourceSnapshot
from dkb_runtime.services.audit import log_audit

DETECTION_PATTERNS = [
    ("**/SKILL.md", "skill"),
    ("**/agents/*.md", "agent"),
    ("**/AGENTS.md", "agent"),
    ("**/*.prompt.md", "prompt"),
    ("**/prompts/*.md", "prompt"),
    ("**/workflows/*.md", "workflow"),
]


def _extract_name_from_md(content: str, filepath: Path) -> str:
    match = re.search(r"^#\s+(.+)", content, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return filepath.stem


def _extract_summary(content: str) -> str | None:
    lines = content.split("\n")
    paragraph = []
    in_paragraph = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            if in_paragraph:
                break
            continue
        if stripped == "":
            if in_paragraph:
                break
            continue
        in_paragraph = True
        paragraph.append(stripped)
    return " ".join(paragraph) if paragraph else None


def _extract_evidence(content: str, license_text: str | None) -> list[dict]:
    evidence_items = []

    summary = _extract_summary(content)
    if summary:
        evidence_items.append(
            {
                "evidence_kind": "summary",
                "excerpt": summary[:500],
                "weight_hint": 0.8,
            }
        )

    role_keywords = r"\b(agent|skill|workflow|plugin|command|tool|assistant|helper)\b"
    for match in re.finditer(role_keywords, content, re.IGNORECASE):
        line_start = content.rfind("\n", 0, match.start()) + 1
        line_end = content.find("\n", match.end())
        if line_end < 0:
            line_end = len(content)
        line = content[line_start:line_end].strip()
        if line and len(line) < 500:
            evidence_items.append(
                {
                    "evidence_kind": "role_phrase",
                    "excerpt": line,
                    "weight_hint": 0.6,
                }
            )

    code_blocks = re.findall(r"```[\s\S]*?```", content)
    for block in code_blocks[:3]:
        evidence_items.append(
            {
                "evidence_kind": "usage_example",
                "excerpt": block[:1000],
                "weight_hint": 0.7,
            }
        )

    if re.search(r"\b(mcp|tool_use|function_call|@tool)\b", content, re.IGNORECASE):
        evidence_items.append(
            {
                "evidence_kind": "tool_reference",
                "excerpt": "tool/MCP references detected",
                "weight_hint": 0.55,
            }
        )

    if license_text:
        evidence_items.append(
            {
                "evidence_kind": "license_excerpt",
                "excerpt": license_text[:500],
                "weight_hint": 0.5,
            }
        )

    return evidence_items


@dataclass
class RawDirectiveResult:
    raw_directive_id: UUID
    raw_name: str
    declared_type: str
    evidence_count: int


def extract_directives(db: Session, snapshot_id: UUID) -> list[RawDirectiveResult]:
    snapshot = db.get(SourceSnapshot, snapshot_id)
    if not snapshot:
        raise ValueError(f"Snapshot not found: {snapshot_id}")

    storage_path = Path(snapshot.raw_blob_uri or "")
    if not storage_path.exists():
        raise FileNotFoundError(f"Snapshot storage not found: {storage_path}")

    results: list[RawDirectiveResult] = []
    seen_paths: set[Path] = set()

    for pattern, declared_type in DETECTION_PATTERNS:
        for filepath in sorted(storage_path.glob(pattern)):
            if filepath in seen_paths or not filepath.is_file():
                continue
            seen_paths.add(filepath)

            content = filepath.read_text(errors="replace")
            raw_name = _extract_name_from_md(content, filepath)
            summary_raw = _extract_summary(content)
            entry_path = str(filepath.relative_to(storage_path))

            suffix = filepath.suffix.lower()
            content_format = {
                ".md": "markdown",
                ".yaml": "yaml",
                ".yml": "yaml",
                ".json": "json",
                ".html": "html",
                ".txt": "text",
            }.get(suffix, "markdown")

            raw_directive = RawDirective(
                snapshot_id=snapshot_id,
                raw_name=raw_name,
                entry_path=entry_path,
                declared_type=declared_type,
                content_format=content_format,
                summary_raw=summary_raw,
                body_raw=content[:50000],
            )
            db.add(raw_directive)
            db.flush()

            evidence_items = _extract_evidence(content, snapshot.license_text)
            for ev in evidence_items:
                db.add(
                    Evidence(
                        raw_directive_id=raw_directive.raw_directive_id,
                        evidence_kind=ev["evidence_kind"],
                        excerpt=ev["excerpt"],
                        weight_hint=ev.get("weight_hint", 0.5),
                    )
                )

            results.append(
                RawDirectiveResult(
                    raw_directive_id=raw_directive.raw_directive_id,
                    raw_name=raw_name,
                    declared_type=declared_type,
                    evidence_count=len(evidence_items),
                )
            )

    for readme in sorted(storage_path.glob("**/README.md")):
        if readme in seen_paths or readme == storage_path / "README.md":
            continue
        seen_paths.add(readme)
        content = readme.read_text(errors="replace")
        raw_name = _extract_name_from_md(content, readme)
        summary_raw = _extract_summary(content)

        raw_directive = RawDirective(
            snapshot_id=snapshot_id,
            raw_name=raw_name,
            entry_path=str(readme.relative_to(storage_path)),
            declared_type="readme",
            content_format="markdown",
            summary_raw=summary_raw,
            body_raw=content[:50000],
        )
        db.add(raw_directive)
        db.flush()

        evidence_items = _extract_evidence(content, snapshot.license_text)
        for ev in evidence_items:
            db.add(
                Evidence(
                    raw_directive_id=raw_directive.raw_directive_id,
                    evidence_kind=ev["evidence_kind"],
                    excerpt=ev["excerpt"],
                    weight_hint=ev.get("weight_hint", 0.5),
                )
            )

        results.append(
            RawDirectiveResult(
                raw_directive_id=raw_directive.raw_directive_id,
                raw_name=raw_name,
                declared_type="readme",
                evidence_count=len(evidence_items),
            )
        )

    log_audit(
        db,
        "snapshot",
        snapshot_id,
        "extracted",
        {"directive_count": len(results)},
    )
    db.commit()

    return results
