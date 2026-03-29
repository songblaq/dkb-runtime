"""Scoring service — computes DG dimension scores."""

from __future__ import annotations

import json
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from dkb_runtime.core.paths import repo_root
from dkb_runtime.models import CanonicalDirective, DimensionModel, DimensionScore, RawToCanonicalMap

_CONFIG_PATH = repo_root() / "config" / "dimension_model_v0_1.json"


@dataclass
class DimensionScoreResult:
    dimension_key: str
    score: float
    confidence: float
    explanation: str


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def _score_keyword_presence(content: str, keywords: list[str]) -> tuple[float, float, str]:
    content_lower = content.lower()
    matches = [kw for kw in keywords if kw in content_lower]
    denom = max(len(keywords) * 0.3, 1.0)
    score = _clamp01(len(matches) / denom)
    confidence = _clamp01(0.5 + (0.3 * min(len(content) / 1000, 1.0)))
    explanation = f"Found {len(matches)}/{len(keywords)} keywords: {', '.join(matches[:5])}"
    return score, confidence, explanation


def _load_dimension_groups() -> list[tuple[str, list[str]]]:
    data = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
    return [(g["name"], g["dimensions"]) for g in data["groups"]]


def _load_directive_for_scoring(db: Session, directive_id: UUID) -> CanonicalDirective:
    d = db.scalars(
        select(CanonicalDirective)
        .where(CanonicalDirective.directive_id == directive_id)
        .options(
            selectinload(CanonicalDirective.mappings).selectinload(RawToCanonicalMap.raw_directive),
        )
    ).one_or_none()
    if not d:
        raise ValueError(f"Directive not found: {directive_id}")
    return d


def _gather_context(directive: CanonicalDirective) -> tuple[str, str, str]:
    parts = [
        directive.preferred_name or "",
        directive.normalized_summary or "",
        directive.primary_human_label or "",
    ]
    paths: list[str] = []
    types: list[str] = []
    for m in directive.mappings:
        rd = m.raw_directive
        if rd is None:
            continue
        parts.append(rd.body_raw or "")
        parts.append(rd.summary_raw or "")
        if rd.entry_path:
            paths.append(rd.entry_path.lower())
        if rd.declared_type:
            types.append(rd.declared_type.lower())
    text = "\n".join(parts)
    path_blob = " ".join(paths)
    type_blob = " ".join(types)
    return text, path_blob, type_blob


def _score_dimension(
    group: str,
    key: str,
    content: str,
    path_blob: str,
    type_blob: str,
) -> tuple[float, float, str]:
    c = content.lower()

    # --- form ---
    if key == "skillness":
        s = 0.2
        conf = 0.4
        if "skill.md" in path_blob or "/skills/" in path_blob:
            s += 0.4
        if "skill" in type_blob:
            s += 0.3
        sk, cf, ex = _score_keyword_presence(c, ["skill", "capability", "single task", "invoke"])
        s = _clamp01(s + sk * 0.3)
        conf = _clamp01(max(conf, cf))
        return s, conf, f"skillness: paths/types/keywords — {ex}"
    if key == "agentness":
        s = 0.2
        if "agents/" in path_blob or "agents\\" in path_blob:
            s += 0.35
        if "agent" in type_blob:
            s += 0.35
        sk, cf, ex = _score_keyword_presence(
            c, ["agent", "multi-step", "orchestrate", "delegate", "planner"]
        )
        return _clamp01(s + sk * 0.25), cf, f"agentness: {ex}"
    if key == "workflowness":
        s = 0.15
        if "workflow" in path_blob:
            s += 0.45
        if "workflow" in type_blob:
            s += 0.3
        sk, cf, ex = _score_keyword_presence(
            c, ["pipeline", "stage", "step 1", "workflow", "sequence"]
        )
        return _clamp01(s + sk * 0.3), cf, f"workflowness: {ex}"
    if key == "commandness":
        sk, cf, ex = _score_keyword_presence(
            c, ["cli", "command", "run ", "invoke", "terminal", "bash", "sh "]
        )
        return sk, cf, f"commandness: {ex}"
    if key == "pluginness":
        sk, cf, ex = _score_keyword_presence(
            c, ["hook", "plugin", "extension", "middleware", "settings.json", "integrate"]
        )
        return sk, cf, f"pluginness: {ex}"

    # --- function ---
    function_kw: dict[str, list[str]] = {
        "planning": ["plan", "strategy", "roadmap", "design", "outline"],
        "review": ["review", "audit", "check", "lint", "analyze", "critique"],
        "coding": ["code", "implement", "develop", "debug", "refactor", "patch"],
        "research": ["search", "investigate", "explore", "find", "discover"],
        "ops": ["deploy", "ci/cd", "ci cd", "monitor", "infrastructure", "kubernetes"],
        "writing": ["write", "document", "draft", "compose", "author"],
        "content": ["generate", "create", "produce", "render", "output"],
        "orchestration": ["orchestrate", "coordinate", "delegate", "pipeline", "multi-agent"],
    }
    if key in function_kw:
        return _score_keyword_presence(c, function_kw[key])

    # --- execution ---
    if key == "atomicity":
        multi = _score_keyword_presence(c, ["step 1", "phase", "then ", "next ", "finally"])[0]
        return _clamp01(1.0 - multi * 0.9), 0.55, "atomicity: inverse of multi-step cues"
    if key == "autonomy":
        human = _score_keyword_presence(c, ["you must", "confirm", "ask user", "human approval"])[0]
        return _clamp01(1.0 - human * 0.85), 0.5, "autonomy: lower when human-in-loop cues"
    if key == "multi_stepness":
        sk, cf, ex = _score_keyword_presence(c, ["step", "phase", "stage", "workflow", "sequence"])
        return sk, cf, f"multi_stepness: {ex}"
    if key == "tool_dependence":
        sk, cf, ex = _score_keyword_presence(
            c, ["mcp", "api", "http", "tool", "external", "service", "database"]
        )
        return sk, cf, f"tool_dependence: {ex}"
    if key == "composability":
        sk, cf, ex = _score_keyword_presence(
            c, ["input", "output", "interface", "compose", "chain", "reuse"]
        )
        return sk, cf, f"composability: {ex}"
    if key == "reusability":
        spec = _score_keyword_presence(
            c, ["this repo", "our team", "internal only", "project-specific"]
        )[0]
        return _clamp01(1.0 - spec * 0.7), 0.5, "reusability: lower when project-specific cues"

    # --- governance ---
    if key == "officialness":
        sk, cf, ex = _score_keyword_presence(
            c,
            ["anthropic", "openai", "microsoft", "google", "github", "official", "vendor"],
        )
        return sk, cf, f"officialness: {ex}"
    if key == "legal_clarity":
        sk, cf, ex = _score_keyword_presence(
            c, ["license", "mit", "apache", "bsd", "copyright", "terms"]
        )
        return sk, cf, f"legal_clarity: {ex}"
    if key == "maintenance_health":
        sk, cf, ex = _score_keyword_presence(
            c, ["changelog", "updated", "release", "version", "commit"]
        )
        return sk, cf, f"maintenance_health: {ex}"
    if key == "install_verifiability":
        sk, cf, ex = _score_keyword_presence(
            c, ["install", "npm ", "pip ", "docker", "setup", "quickstart"]
        )
        return sk, cf, f"install_verifiability: {ex}"
    if key == "trustworthiness":
        o, oc, _ = _score_dimension(group, "officialness", content, path_blob, type_blob)
        leg, lc, _ = _score_dimension(group, "legal_clarity", content, path_blob, type_blob)
        m, mc, _ = _score_dimension(group, "maintenance_health", content, path_blob, type_blob)
        s = _clamp01((o + leg + m) / 3)
        conf = _clamp01((oc + lc + mc) / 3)
        return s, conf, "trustworthiness: blend officialness, legal_clarity, maintenance_health"

    # --- adoption (weak signals without metadata) ---
    if key == "star_signal":
        sk, cf, ex = _score_keyword_presence(c, ["star", "popular", "trending", "github.com"])
        return sk * 0.5, cf * 0.6, f"star_signal (text proxy): {ex}"
    if key == "fork_signal":
        sk, cf, ex = _score_keyword_presence(c, ["fork", "contributor", "pull request", "pr "])
        return sk * 0.5, cf * 0.55, f"fork_signal (text proxy): {ex}"
    if key == "mention_signal":
        sk, cf, ex = _score_keyword_presence(c, ["referenced", "cited", "mentioned", "see also"])
        return sk, cf, f"mention_signal: {ex}"
    if key == "install_signal":
        sk, cf, ex = _score_keyword_presence(
            c, ["download", "install count", "pypi", "npm downloads"]
        )
        return sk * 0.6, cf * 0.55, f"install_signal (text proxy): {ex}"
    if key == "freshness":
        sk, cf, ex = _score_keyword_presence(
            c, ["2024", "2025", "2026", "recent", "latest", "updated"]
        )
        return sk, cf, f"freshness: {ex}"

    # --- clarity ---
    if key == "naming_clarity":
        name = (content.split("\n")[0] if content else "").strip()
        ln = len(name)
        s = _clamp01(min(ln / 40, 1.0)) if ln > 2 else 0.2
        return s, 0.55, "naming_clarity: length/clarity of primary label"
    if key == "description_clarity":
        sk, cf, ex = _score_keyword_presence(c, ["description", "summary", "overview", "purpose"])
        summary_len = min(len(content) / 800, 1.0)
        return (
            _clamp01(sk * 0.5 + summary_len * 0.5),
            _clamp01(0.45 + summary_len * 0.3),
            ex or "description_clarity",
        )
    if key == "io_clarity":
        sk, cf, ex = _score_keyword_presence(
            c, ["input", "output", "parameter", "argument", "returns", "schema"]
        )
        return sk, cf, f"io_clarity: {ex}"
    if key == "example_coverage":
        n = min(content.count("```"), 5) / 5.0
        return _clamp01(n), 0.6, f"example_coverage: {content.count('```')} fenced blocks"
    if key == "overlap_ambiguity_inverse":
        amb = _score_keyword_presence(c, ["unclear", "ambiguous", "maybe", "or something"])[0]
        return _clamp01(1.0 - amb), 0.45, "overlap_ambiguity_inverse: inverse ambiguity cues"

    return 0.5, 0.3, f"fallback for {group}.{key}"


def score_directive(db: Session, directive_id: UUID, model_id: UUID) -> list[DimensionScoreResult]:
    model = db.get(DimensionModel, model_id)
    if not model:
        raise ValueError(f"Dimension model not found: {model_id}")

    directive = _load_directive_for_scoring(db, directive_id)
    content, path_blob, type_blob = _gather_context(directive)
    groups = _load_dimension_groups()

    db.execute(
        delete(DimensionScore).where(
            DimensionScore.directive_id == directive_id,
            DimensionScore.dimension_model_id == model_id,
        )
    )

    results: list[DimensionScoreResult] = []
    for group_name, dims in groups:
        for dim_key in dims:
            score, confidence, explanation = _score_dimension(
                group_name, dim_key, content, path_blob, type_blob
            )
            row = DimensionScore(
                directive_id=directive_id,
                dimension_model_id=model_id,
                dimension_group=group_name,
                dimension_key=dim_key,
                score=_clamp01(score),
                confidence=_clamp01(confidence),
                explanation=explanation,
                features={"rule_based": True, "version": "0.1"},
            )
            db.add(row)
            results.append(
                DimensionScoreResult(
                    dimension_key=dim_key,
                    score=_clamp01(score),
                    confidence=_clamp01(confidence),
                    explanation=explanation,
                )
            )
    db.flush()
    return results
