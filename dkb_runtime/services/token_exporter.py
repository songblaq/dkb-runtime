"""Token-efficient Markdown export for directive packs (LLM-oriented)."""

from __future__ import annotations

import re
from contextlib import suppress
from typing import Any

# Order matches scoring groups; short labels only where it saves tokens vs the raw dimension id.
_GROUP_DIMS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("form", ("skillness", "agentness", "workflowness", "commandness", "pluginness")),
    ("function", ("planning", "review", "coding", "research", "ops", "writing", "content", "orchestration")),
    (
        "execution",
        ("atomicity", "autonomy", "multi_stepness", "tool_dependence", "composability", "reusability"),
    ),
    (
        "governance",
        ("officialness", "legal_clarity", "maintenance_health", "install_verifiability", "trustworthiness"),
    ),
    ("adoption", ("star_signal", "fork_signal", "mention_signal", "install_signal", "freshness")),
    (
        "clarity",
        ("naming_clarity", "description_clarity", "io_clarity", "example_coverage", "overlap_ambiguity_inverse"),
    ),
)

_FORM_SHORT: dict[str, str] = {
    "skillness": "skill",
    "agentness": "agent",
    "workflowness": "workflow",
    "commandness": "cmd",
    "pluginness": "plugin",
}


def _flatten_scores(scores: Any) -> dict[str, float]:
    if not isinstance(scores, dict):
        return {}
    out: dict[str, float] = {}
    for raw_k, val in scores.items():
        k = str(raw_k)
        dim = k.split(".", 1)[1] if "." in k else k
        if isinstance(val, dict):
            s = val.get("score")
            if s is not None:
                with suppress(TypeError, ValueError):
                    out[dim] = float(s)
        elif isinstance(val, (int, float)):
            out[dim] = float(val)
    return out


def _one_line(text: str | None) -> str:
    if not text:
        return ""
    line = text.strip().splitlines()[0] if text.strip() else ""
    return line[:500] if len(line) > 500 else line


def _directive_title(d: dict[str, Any]) -> str:
    return str(d.get("preferred_name") or d.get("name") or d.get("directive_id") or "directive")


def _source_line(d: dict[str, Any]) -> str:
    meta = d.get("canonical_meta")
    if not isinstance(meta, dict):
        return ""
    for key in ("repo", "repository", "url", "source_url", "github", "source_uri", "origin"):
        v = meta.get(key)
        if v:
            return str(v).strip()
    return ""


def _verdict_display(d: dict[str, Any]) -> tuple[str, str, str]:
    v = d.get("verdict")
    if not isinstance(v, dict):
        return "unknown", "unknown", "unknown"
    rec = str(v.get("recommendation", "unknown"))
    rec_display = "recommended" if rec == "preferred" else rec
    trust = str(v.get("trust", "unknown"))
    legal = str(v.get("legal", "unknown"))
    return rec_display, trust, legal


def _scores_section(flat: dict[str, float]) -> list[str]:
    body: list[str] = []
    for group, dims in _GROUP_DIMS:
        parts: list[str] = []
        for dim in dims:
            if dim not in flat:
                continue
            label = _FORM_SHORT.get(dim, dim)
            parts.append(f"{label}={flat[dim]:.2f}")
        if parts:
            gtitle = group.capitalize()
            body.append(f"{gtitle}: " + " ".join(parts))
    if not body:
        return []
    return ["## scores", *body]


def _compact_block(d: dict[str, Any]) -> str:
    title = _directive_title(d)
    desc = _one_line(d.get("normalized_summary") or d.get("summary") or "")
    if not desc:
        meta = d.get("canonical_meta")
        if isinstance(meta, dict):
            for key in ("description", "summary"):
                raw = meta.get(key)
                if raw:
                    desc = _one_line(str(raw))
                    break
    if not desc:
        desc = "(no description)"

    src = _source_line(d)
    flat = _flatten_scores(d.get("scores"))

    lines: list[str] = [f"# {title}", f"desc: {desc}"]
    if src:
        lines.append(f"src: {src}")

    lines.extend(_scores_section(flat))

    rec, trust, legal = _verdict_display(d)
    lines.append(f"## verdict: {rec}")
    lines.append(f"trust: {trust} | legal: {legal}")

    return "\n".join(lines)


def export_compact_markdown(directives: list[dict[str, Any]]) -> str:
    """Compact Markdown for directives, blocks separated by `---` (no pack header)."""
    blocks = [_compact_block(d) for d in directives]
    return "\n\n---\n\n".join(blocks)


def export_batch_markdown(
    directives: list[dict[str, Any]],
    pack_name: str,
    *,
    pack_key: str | None = None,
) -> str:
    """One file: pack header, then each directive in compact form separated by `---`."""
    key = pack_name.strip() or "pack"
    safe = re.sub(r"\s+", " ", key)
    lines_h = [f"# {safe}", f"items: {len(directives)}"]
    if pack_key:
        lines_h.insert(1, f"key: {pack_key}")
    header = "\n".join(lines_h)
    body = export_compact_markdown(directives)
    if not body:
        return header + "\n"
    return header + "\n\n---\n\n" + body
