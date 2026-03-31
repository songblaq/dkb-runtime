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


@cli.group()
def embed() -> None:
    """Embedding generation and similarity search."""
    pass


@embed.command("generate")
@click.option("--all", "generate_all", is_flag=True, help="Generate embeddings for all canonical directives")
@click.option(
    "--model",
    "model_name",
    default="text-embedding-3-small",
    help="Embedding model name (must match rows used for search)",
)
def embed_generate(generate_all: bool, model_name: str) -> None:
    """Generate and store embeddings."""
    from sqlalchemy import select

    from dkb_runtime.db.session import SessionLocal
    from dkb_runtime.models import CanonicalDirective
    from dkb_runtime.services.embedding import (
        directive_text_for_embedding,
        generate_embedding,
        store_embedding,
    )

    if not generate_all:
        click.echo("Use --all to generate embeddings for every canonical directive")
        return

    db = SessionLocal()
    try:
        directives = db.scalars(select(CanonicalDirective).order_by(CanonicalDirective.preferred_name)).all()
        n = 0
        for d in directives:
            text_in = directive_text_for_embedding(db, d.directive_id)
            if not text_in:
                click.echo(f"  skip (no text): {d.directive_id}")
                continue
            vec = generate_embedding(text_in, model=model_name)
            store_embedding(db, d.directive_id, vec, model_name)
            n += 1
            click.echo(f"  embedded: {d.preferred_name}")
        db.commit()
        click.echo(f"Done: {n} directive(s) embedded with {model_name}")
    finally:
        db.close()


@embed.command("search")
@click.argument("query_text", nargs=-1, required=True)
@click.option("--limit", default=10, help="Max results")
@click.option("--model", "model_name", default="text-embedding-3-small", help="Embedding model filter")
def embed_search(query_text: tuple[str, ...], limit: int, model_name: str) -> None:
    """Search similar directives by query text (embeds query, then pgvector ranking)."""
    from sqlalchemy import select

    from dkb_runtime.db.session import SessionLocal
    from dkb_runtime.models import CanonicalDirective
    from dkb_runtime.services.embedding import find_similar, generate_embedding

    q = " ".join(query_text).strip()
    if not q:
        click.echo("Provide query text")
        return

    db = SessionLocal()
    try:
        vec = generate_embedding(q, model=model_name)
        pairs = find_similar(db, vec, limit=limit, model_name=model_name)
        if not pairs:
            click.echo("No matches (missing embeddings or empty index)")
            return
        ids = [p[0] for p in pairs]
        dist = dict(pairs)
        directives = db.scalars(select(CanonicalDirective).where(CanonicalDirective.directive_id.in_(ids))).all()
        by_id = {d.directive_id: d for d in directives}
        for did in ids:
            if did not in by_id:
                continue
            d = by_id[did]
            click.echo(f"  {dist[did]:.4f}  {d.preferred_name}  ({did})")
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


@cli.group()
def cost() -> None:
    """LLM usage and cost."""
    pass


@cost.command("summary")
@click.option("--days", default=30, type=int, help="Rolling window in days")
def cost_summary(days: int) -> None:
    """Show LLM usage cost summary."""
    from dkb_runtime.db.session import SessionLocal
    from dkb_runtime.services.cost_tracker import get_usage_summary

    db = SessionLocal()
    try:
        s = get_usage_summary(db, days=days)
        click.echo(f"LLM usage (last {s['days']} days)")
        click.echo("=" * 40)
        click.echo(f"  Total USD: {s['total_cost_usd']:.6f}")
        click.echo("  By provider:")
        for p, c in s["by_provider"].items():
            click.echo(f"    {p}: {c:.6f}")
        if not s["by_provider"]:
            click.echo("    (none)")
        click.echo("  By model:")
        for m, c in s["by_model"].items():
            click.echo(f"    {m}: {c:.6f}")
        if not s["by_model"]:
            click.echo("    (none)")
    finally:
        db.close()


@cli.group()
def cache() -> None:
    """Score cache operations."""
    pass


@cache.command("clear")
@click.option("--directive-id", default=None, help="Limit invalidation to one directive UUID")
def cache_clear(directive_id: str | None) -> None:
    """Clear score cache entries."""
    from uuid import UUID

    from dkb_runtime.db.session import SessionLocal
    from dkb_runtime.services.score_cache import invalidate_cache

    db = SessionLocal()
    try:
        did = UUID(directive_id) if directive_id else None
        n = invalidate_cache(db, directive_id=did)
        db.commit()
        click.echo(f"Cleared {n} score cache row(s).")
    finally:
        db.close()


@cache.command("stats")
def cache_stats() -> None:
    """Show score cache hit/miss stats and DB entry counts."""
    from dkb_runtime.db.session import SessionLocal
    from dkb_runtime.services.score_cache import get_cache_stats, score_cache_entry_counts

    db = SessionLocal()
    try:
        st = get_cache_stats()
        counts = score_cache_entry_counts(db)
        click.echo("Score cache stats")
        click.echo("=" * 40)
        click.echo(f"  Process lookups: {st['total_lookups']} (hits={st['hits']}, misses={st['misses']})")
        click.echo(f"  Hit rate:        {st['hit_rate']:.4f}")
        click.echo(f"  DB entries:      {counts['entries_total']} total, {counts['entries_active']} active (unexpired)")
    finally:
        db.close()


if __name__ == "__main__":
    cli()
