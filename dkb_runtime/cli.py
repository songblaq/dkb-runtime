"""DKB Runtime CLI — operational control for DKB pipeline."""

from __future__ import annotations

import json
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import click


def _package_version() -> str:
    try:
        return version("dkb-runtime")
    except PackageNotFoundError:
        return "0.1.0"


@click.group()
@click.version_option(version=_package_version(), prog_name="dkb")
def cli() -> None:
    """DKB Runtime — Directive Knowledge Base pipeline control."""
    pass


@cli.group()
def source() -> None:
    """Manage sources."""
    pass


@source.command("list")
def source_list() -> None:
    """List all registered sources."""
    from sqlalchemy import select

    from dkb_runtime.db.session import SessionLocal
    from dkb_runtime.models import Source

    db = SessionLocal()
    try:
        sources = db.scalars(select(Source).order_by(Source.canonical_source_name)).all()
        for s in sources:
            label = s.canonical_source_name or s.origin_uri
            click.echo(f"  {s.source_id}  {s.source_kind:<12} {label}")
        click.echo(f"\nTotal: {len(sources)} sources")
    finally:
        db.close()


@source.command("add")
@click.argument("origin_uri")
@click.option("--kind", default="git_repo", help="Source kind (git_repo, local_folder)")
@click.option("--name", default=None, help="Canonical name")
@click.option("--provenance", default="community", help="Provenance hint")
def source_add(origin_uri: str, kind: str, name: str | None, provenance: str) -> None:
    """Register a new source."""
    from dkb_runtime.db.session import SessionLocal
    from dkb_runtime.models import Source

    db = SessionLocal()
    try:
        source = Source(
            source_kind=kind,
            origin_uri=origin_uri,
            canonical_source_name=name or origin_uri.split("/")[-1],
            provenance_hint=provenance,
        )
        db.add(source)
        db.commit()
        click.echo(f"Added source: {source.source_id} ({source.canonical_source_name})")
    finally:
        db.close()


@source.command("import")
@click.argument("sources_json", type=click.Path(exists=True, path_type=Path))
def source_import(sources_json: Path) -> None:
    """Import sources from a JSON config file."""
    from sqlalchemy import select

    from dkb_runtime.db.session import SessionLocal
    from dkb_runtime.models import Source

    db = SessionLocal()
    try:
        config = json.loads(sources_json.read_text(encoding="utf-8"))
        count = 0
        for _category, sources in config.get("categories", {}).items():
            for src in sources:
                uri = src.get("origin_uri") or src.get("url")
                if not uri:
                    continue
                existing = db.scalars(select(Source).where(Source.origin_uri == uri)).first()
                if not existing:
                    new_source = Source(
                        source_kind="git_repo",
                        origin_uri=uri,
                        canonical_source_name=src.get("label", uri.split("/")[-1]),
                        provenance_hint=src.get("provenance_hint", "community"),
                    )
                    db.add(new_source)
                    count += 1
        db.commit()
        click.echo(f"Imported {count} new sources")
    finally:
        db.close()


@cli.group()
def collect() -> None:
    """Collection operations."""
    pass


@collect.command("run")
@click.option("--source-id", default=None, help="Specific source ID to collect")
@click.option("--all", "collect_all", is_flag=True, help="Collect all sources")
def collect_run(source_id: str | None, collect_all: bool) -> None:
    """Run collection for sources."""
    from uuid import UUID

    from sqlalchemy import select

    from dkb_runtime.db.session import SessionLocal
    from dkb_runtime.models import Source
    from dkb_runtime.services.collector import collect_source

    db = SessionLocal()
    try:
        if source_id:
            result = collect_source(db, UUID(source_id))
            rev = result.revision_ref[:8] if result.revision_ref else "N/A"
            click.echo(f"Collected: {result.capture_status} (rev: {rev})")
        elif collect_all:
            sources = db.scalars(select(Source)).all()
            for s in sources:
                click.echo(f"Collecting {s.canonical_source_name}...", nl=False)
                try:
                    result = collect_source(db, s.source_id)
                    click.echo(f" {result.capture_status}")
                except Exception as e:
                    click.echo(f" ERROR: {e}")
        else:
            click.echo("Specify --source-id or --all")
    finally:
        db.close()


@cli.group()
def pipeline() -> None:
    """Pipeline operations."""
    pass


@pipeline.command("run")
@click.option("--snapshot-id", default=None, help="Specific snapshot to process")
@click.option("--all", "process_all", is_flag=True, help="Process all captured snapshots")
def pipeline_run(snapshot_id: str | None, process_all: bool) -> None:
    """Run the full pipeline: extract -> canonicalize -> score -> verdict."""
    from uuid import UUID

    from sqlalchemy import select

    from dkb_runtime.db.session import SessionLocal
    from dkb_runtime.models import DimensionModel, SourceSnapshot
    from dkb_runtime.services.canonicalizer import canonicalize
    from dkb_runtime.services.extractor import extract_directives
    from dkb_runtime.services.scoring import score_directive
    from dkb_runtime.services.verdict import evaluate_directive

    db = SessionLocal()
    try:
        if snapshot_id:
            snap = db.get(SourceSnapshot, UUID(snapshot_id))
            if not snap:
                click.echo(f"Snapshot not found: {snapshot_id}")
                return
            snapshots = [snap]
        elif process_all:
            snapshots = db.scalars(select(SourceSnapshot).where(SourceSnapshot.capture_status == "captured")).all()
        else:
            click.echo("Specify --snapshot-id or --all")
            return

        click.echo(f"Processing {len(snapshots)} snapshots...")

        all_raw_ids = []
        for snap in snapshots:
            results = extract_directives(db, snap.snapshot_id)
            all_raw_ids.extend([r.raw_directive_id for r in results])
            click.echo(f"  Extracted {len(results)} directives from {snap.snapshot_id}")

        canonical_results = canonicalize(db, all_raw_ids)
        click.echo(f"  Canonicalized: {len(canonical_results)} directives")

        dim_model = db.scalars(select(DimensionModel).where(DimensionModel.is_active.is_(True))).first()
        if not dim_model:
            click.echo("ERROR: No active dimension model. Run 'dkb seed' first.")
            return

        for cr in canonical_results:
            score_directive(db, cr.directive_id, dim_model.dimension_model_id)
            evaluate_directive(db, cr.directive_id)

        db.commit()
        click.echo(f"Pipeline complete: {len(canonical_results)} directives scored and evaluated")
    finally:
        db.close()


@cli.group()
def pack() -> None:
    """Pack operations."""
    pass


@pack.command("list")
def pack_list() -> None:
    """List all packs."""
    from sqlalchemy import select

    from dkb_runtime.db.session import SessionLocal
    from dkb_runtime.models import Pack

    db = SessionLocal()
    try:
        packs = db.scalars(select(Pack).order_by(Pack.pack_key)).all()
        for p in packs:
            click.echo(f"  {p.pack_id}  {p.pack_key:<20} {p.status:<10} {p.pack_name}")
        click.echo(f"\nTotal: {len(packs)} packs")
    finally:
        db.close()


@pack.command("build")
@click.argument("pack_key")
def pack_build(pack_key: str) -> None:
    """Build a pack by key."""
    from sqlalchemy import select

    from dkb_runtime.db.session import SessionLocal
    from dkb_runtime.models import Pack
    from dkb_runtime.services.pack_engine import build_pack

    db = SessionLocal()
    try:
        p = db.scalars(select(Pack).where(Pack.pack_key == pack_key)).first()
        if not p:
            click.echo(f"Pack not found: {pack_key}")
            return
        result = build_pack(db, p.pack_id)
        click.echo(f"Built: {result.item_count} items, status: {result.status}")
    finally:
        db.close()


@pack.command("export")
@click.argument("pack_key")
@click.option("--format", "fmt", type=click.Choice(["claude-code", "skill-md", "snapshot"]), default="claude-code")
@click.option("--output", "-o", default="dist", help="Output directory")
def pack_export(pack_key: str, fmt: str, output: str) -> None:
    """Export a pack."""
    from sqlalchemy import select

    from dkb_runtime.db.session import SessionLocal
    from dkb_runtime.models import Pack
    from dkb_runtime.services.exporter import export_claude_code, export_skill_md, export_snapshot

    db = SessionLocal()
    try:
        p = db.scalars(select(Pack).where(Pack.pack_key == pack_key)).first()
        if not p:
            click.echo(f"Pack not found: {pack_key}")
            return
        out = Path(output) / fmt / pack_key
        exporters = {
            "claude-code": export_claude_code,
            "skill-md": export_skill_md,
            "snapshot": export_snapshot,
        }
        result = exporters[fmt](db, p.pack_id, out)
        click.echo(f"Exported {result.file_count} files to {result.output_path}")
    finally:
        db.close()


@cli.command()
def serve() -> None:
    """Start the DKB API server."""
    import uvicorn

    uvicorn.run("dkb_runtime.api.app:app", host="0.0.0.0", port=8000, reload=True)


@cli.command()
def status() -> None:
    """Show pipeline status summary."""
    from sqlalchemy import func, select

    from dkb_runtime.db.session import SessionLocal
    from dkb_runtime.models import CanonicalDirective, Pack, RawDirective, Source, SourceSnapshot, Verdict

    db = SessionLocal()
    try:
        sources = db.scalar(select(func.count()).select_from(Source)) or 0
        snapshots = db.scalar(select(func.count()).select_from(SourceSnapshot)) or 0
        raw = db.scalar(select(func.count()).select_from(RawDirective)) or 0
        canonical = db.scalar(select(func.count()).select_from(CanonicalDirective)) or 0
        verdicts = db.scalar(select(func.count()).select_from(Verdict)) or 0
        packs = db.scalar(select(func.count()).select_from(Pack)) or 0
        click.echo("DKB Pipeline Status")
        click.echo("=" * 40)
        click.echo(f"  Sources:              {sources}")
        click.echo(f"  Snapshots:            {snapshots}")
        click.echo(f"  Raw Directives:       {raw}")
        click.echo(f"  Canonical Directives: {canonical}")
        click.echo(f"  Verdicts:             {verdicts}")
        click.echo(f"  Packs:                {packs}")
    finally:
        db.close()


if __name__ == "__main__":
    cli()
