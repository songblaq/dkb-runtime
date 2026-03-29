"""Exporter service — exports curated packs to various formats."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session


@dataclass
class ExportResult:
    format: str
    output_path: Path
    file_count: int


def export_claude_code(
    db: Session, pack_id: UUID, output_dir: Path
) -> ExportResult:
    """Export a pack as Claude Code plugin structure.

    Output:
    - agents/*.md
    - skills/*.md
    - hooks/ (if applicable)
    - settings.json
    """
    raise NotImplementedError("exporter.export_claude_code")


def export_skill_md(
    db: Session, pack_id: UUID, output_dir: Path
) -> ExportResult:
    """Export a pack as SKILL.md standard format.

    Output:
    - {name}/SKILL.md
    - {name}/resources/ (if applicable)
    """
    raise NotImplementedError("exporter.export_skill_md")


def export_snapshot(
    db: Session, pack_id: UUID, output_dir: Path
) -> ExportResult:
    """Export a pack as a versioned release snapshot."""
    raise NotImplementedError("exporter.export_snapshot")
