#!/usr/bin/env python3
"""Compare token counts for directive serialization formats (cl100k_base)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import tiktoken
import yaml

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dkb_runtime.services.scoring_prompts import DIMENSION_TO_GROUP  # noqa: E402
from dkb_runtime.services.token_exporter import export_compact_markdown  # noqa: E402

# Deterministic sample: one score per DG dimension (34 total)
_SAMPLE_SCORES: dict[str, float] = {}
_seed = 0.11
for dim in sorted(DIMENSION_TO_GROUP.keys()):
    _SAMPLE_SCORES[dim] = round(min(0.99, _seed), 2)
    _seed += 0.023

SAMPLE_DIRECTIVE: dict = {
    "preferred_name": "code-review-skill",
    "normalized_summary": "Structured PR review: correctness, tests, security, and rollback.",
    "canonical_meta": {
        "repo": "github.com/org/example-repo",
    },
    "scores": {k: {"score": v, "confidence": 0.85} for k, v in _SAMPLE_SCORES.items()},
    "verdict": {
        "trust": "verified",
        "legal": "clear",
        "lifecycle": "active",
        "recommendation": "preferred",
    },
}


def _catalog_style_scores() -> dict:
    """Scores as stored in agent catalog (group.dimension → payload)."""
    out: dict = {}
    for dim, val in _SAMPLE_SCORES.items():
        grp = DIMENSION_TO_GROUP[dim]
        out[f"{grp}.{dim}"] = {"score": val, "confidence": 0.85}
    return out


def _directive_json_dict() -> dict:
    d = {**SAMPLE_DIRECTIVE, "scores": _catalog_style_scores()}
    return d


def _serialize_json(d: dict) -> str:
    return json.dumps(d, indent=2, ensure_ascii=False)


def _serialize_yaml(d: dict) -> str:
    return yaml.safe_dump(d, default_flow_style=False, allow_unicode=True, sort_keys=False)


def _serialize_markdown_verbose(d: dict) -> str:
    lines = [
        f"# {d['preferred_name']}",
        "",
        "## Summary",
        d.get("normalized_summary") or "",
        "",
        "## Source",
        (d.get("canonical_meta") or {}).get("repo", ""),
        "",
        "## Scores",
    ]
    scores = d.get("scores") or {}
    by_group: dict[str, list[tuple[str, float]]] = {}
    for raw_k, payload in scores.items():
        if isinstance(payload, dict):
            sk = str(raw_k)
            dim = sk.split(".", 1)[1] if "." in sk else sk
            grp = DIMENSION_TO_GROUP.get(dim, "unknown")
            by_group.setdefault(grp, []).append((dim, float(payload.get("score", 0.0))))
    for grp in sorted(by_group.keys()):
        lines.append(f"### {grp.capitalize()}")
        for dim, sc in sorted(by_group[grp]):
            lines.append(f"- **{dim}**: {sc:.2f}")
        lines.append("")
    v = d.get("verdict") or {}
    lines.append("## Verdict")
    lines.append(f"- recommendation: {v.get('recommendation', '')}")
    lines.append(f"- trust: {v.get('trust', '')}")
    lines.append(f"- legal: {v.get('legal', '')}")
    return "\n".join(lines).rstrip() + "\n"


def _serialize_compact_markdown(d: dict) -> str:
    cat = {**d, "scores": _catalog_style_scores()}
    return export_compact_markdown([cat])


def _count_tokens(text: str, enc: tiktoken.Encoding) -> int:
    return len(enc.encode(text))


def main() -> None:
    enc = tiktoken.get_encoding("cl100k_base")
    d = _directive_json_dict()

    formats = {
        "json": _serialize_json(d),
        "yaml": _serialize_yaml(d),
        "markdown": _serialize_markdown_verbose(d),
        "compact_markdown": _serialize_compact_markdown(d),
    }

    rows = []
    baseline = _count_tokens(formats["json"], enc)
    for name, blob in formats.items():
        n = _count_tokens(blob, enc)
        pct = round(100.0 * (1.0 - n / baseline), 1) if baseline else 0.0
        rows.append({"format": name, "tokens": n, "vs_json_pct": pct, "chars": len(blob)})

    results_dir = ROOT / "experiments" / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    out_path = results_dir / "token_comparison.json"
    payload = {
        "encoding": "cl100k_base",
        "baseline_format": "json",
        "baseline_tokens": baseline,
        "rows": rows,
    }
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print("Token comparison (cl100k_base), sample directive with 34 dimensions:\n")
    print(f"{'format':<18} {'tokens':>8} {'vs JSON':>10} {'chars':>8}")
    print("-" * 48)
    for r in rows:
        print(f"{r['format']:<18} {r['tokens']:>8} {r['vs_json_pct']:>9}% {r['chars']:>8}")
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
