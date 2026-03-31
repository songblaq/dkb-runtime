"""Prompt templates for LLM-based DG dimension scoring (one template per group)."""

from __future__ import annotations

import json
from typing import Final

DIMENSION_TO_GROUP: Final[dict[str, str]] = {}
for _group, _dims in (
    (
        "form",
        ("skillness", "agentness", "workflowness", "commandness", "pluginness"),
    ),
    (
        "function",
        ("planning", "review", "coding", "research", "ops", "writing", "content", "orchestration"),
    ),
    (
        "execution",
        ("atomicity", "autonomy", "multi_stepness", "tool_dependence", "composability", "reusability"),
    ),
    (
        "governance",
        ("officialness", "legal_clarity", "maintenance_health", "install_verifiability", "trustworthiness"),
    ),
    (
        "adoption",
        ("star_signal", "fork_signal", "mention_signal", "install_signal", "freshness"),
    ),
    (
        "clarity",
        ("naming_clarity", "description_clarity", "io_clarity", "example_coverage", "overlap_ambiguity_inverse"),
    ),
):
    for _d in _dims:
        DIMENSION_TO_GROUP[_d] = _group

DIMENSION_DESCRIPTIONS: Final[dict[str, str]] = {
    "skillness": "How much the directive resembles a single-task skill (focused capability, easy to invoke).",
    "agentness": "Degree of autonomous multi-step / planner-like agent behavior.",
    "workflowness": "Presence of staged pipelines, sequences, or explicit workflow structure.",
    "commandness": "CLI / terminal / command invocation orientation.",
    "pluginness": "Extension, hook, middleware, or integration-style packaging.",
    "planning": "Planning, strategy, roadmap, or design emphasis.",
    "review": "Review, audit, lint, or analysis emphasis.",
    "coding": "Implementation, debugging, or refactoring emphasis.",
    "research": "Search, investigation, or discovery emphasis.",
    "ops": "Deploy, CI/CD, monitoring, or infrastructure emphasis.",
    "writing": "Authoring or drafting prose emphasis.",
    "content": "Generating or producing outputs (non-code artifacts).",
    "orchestration": "Coordinating multiple steps, tools, or agents.",
    "atomicity": "Single focused action vs. many steps (higher = more atomic).",
    "autonomy": "Can run without frequent human checkpoints (higher = more autonomous).",
    "multi_stepness": "Explicit multi-phase or sequential process.",
    "tool_dependence": "Reliance on external tools, APIs, MCP, or services.",
    "composability": "Clear inputs/outputs and ability to chain or reuse.",
    "reusability": "General-purpose or portable vs. project-specific one-off.",
    "officialness": "Signals of vendor/official or well-known upstream provenance.",
    "legal_clarity": "License, terms, copyright, or compliance cues.",
    "maintenance_health": "Changelog, releases, versioning, or ongoing maintenance signals.",
    "install_verifiability": "Install/setup/quickstart or reproducible setup documentation.",
    "trustworthiness": "Overall trust from officialness, legal clarity, and maintenance signals.",
    "star_signal": "Popularity / stars / trending cues (textual proxy only).",
    "fork_signal": "Community activity: forks, contributors, PRs (textual proxy).",
    "mention_signal": "Referenced, cited, or linked from elsewhere.",
    "install_signal": "Download or install counts / registry presence (textual proxy).",
    "freshness": "Recency: dates, 'latest', or update language.",
    "naming_clarity": "Clear, descriptive naming / title.",
    "description_clarity": "Purpose, overview, or summary clarity.",
    "io_clarity": "Inputs, outputs, parameters, or schema documentation.",
    "example_coverage": "Examples, snippets, or fenced code blocks.",
    "overlap_ambiguity_inverse": "Higher when the text is specific; lower when vague or ambiguous.",
}

SCORING_SYSTEM_MESSAGE: Final[str] = (
    "You score software directives (skills, agents, workflows, plugins) for a knowledge base. "
    "Respond with a single JSON object only: keys must be exactly the requested dimension ids, "
    "values must be numbers between 0.0 and 1.0 inclusive. No markdown, no prose outside JSON."
)

PROMPT_FORM: Final[str] = """## Form group
Score how the **directive text** manifests each dimension below on a **0.0–1.0** scale.

### Dimensions (id → meaning)
{dimension_lines}

### Directive text
---
{directive_text}
---

Output JSON only, e.g. {example_json}"""

PROMPT_FUNCTION: Final[str] = """## Function group
Score functional emphasis of the **directive text** for each dimension on **0.0–1.0**.

### Dimensions (id → meaning)
{dimension_lines}

### Directive text
---
{directive_text}
---

Output JSON only, e.g. {example_json}"""

PROMPT_EXECUTION: Final[str] = """## Execution group
Score execution characteristics of the **directive text** on **0.0–1.0** per dimension.

### Dimensions (id → meaning)
{dimension_lines}

### Directive text
---
{directive_text}
---

Output JSON only, e.g. {example_json}"""

PROMPT_GOVERNANCE: Final[str] = """## Governance group
Score governance / trust signals in the **directive text** on **0.0–1.0** per dimension.

### Dimensions (id → meaning)
{dimension_lines}

### Directive text
---
{directive_text}
---

Output JSON only, e.g. {example_json}"""

PROMPT_ADOPTION: Final[str] = """## Adoption group
Score adoption / popularity **proxies** visible in the text (infer cautiously) on **0.0–1.0**.

### Dimensions (id → meaning)
{dimension_lines}

### Directive text
---
{directive_text}
---

Output JSON only, e.g. {example_json}"""

PROMPT_CLARITY: Final[str] = """## Clarity group
Score how clearly the **directive text** communicates structure and intent on **0.0–1.0** per dimension.

### Dimensions (id → meaning)
{dimension_lines}

### Directive text
---
{directive_text}
---

Output JSON only, e.g. {example_json}"""

GROUP_PROMPT_TEMPLATE: Final[dict[str, str]] = {
    "form": PROMPT_FORM,
    "function": PROMPT_FUNCTION,
    "execution": PROMPT_EXECUTION,
    "governance": PROMPT_GOVERNANCE,
    "adoption": PROMPT_ADOPTION,
    "clarity": PROMPT_CLARITY,
}


def infer_group_for_dimensions(dimensions: list[str]) -> str:
    if not dimensions:
        raise ValueError("dimensions must be non-empty")
    groups = {DIMENSION_TO_GROUP.get(d) for d in dimensions}
    if None in groups:
        unknown = [d for d in dimensions if d not in DIMENSION_TO_GROUP]
        raise ValueError(f"Unknown dimension keys: {unknown}")
    if len(groups) != 1:
        raise ValueError(f"dimensions span multiple groups: {dimensions}")
    return groups.pop()


def _dimension_lines(dimensions: list[str]) -> str:
    lines = []
    for d in dimensions:
        desc = DIMENSION_DESCRIPTIONS.get(d, "(no description)")
        lines.append(f"- **{d}**: {desc}")
    return "\n".join(lines)


def _example_json(dimensions: list[str]) -> str:
    return json.dumps({d: 0.0 for d in dimensions}, separators=(",", ":"))


def build_group_scoring_prompt(group: str, directive_text: str, dimensions: list[str]) -> str:
    template = GROUP_PROMPT_TEMPLATE.get(group)
    if not template:
        raise ValueError(f"Unknown group: {group}")
    return template.format(
        dimension_lines=_dimension_lines(dimensions),
        directive_text=directive_text.strip() or "(empty)",
        example_json=_example_json(dimensions),
    )


def build_scoring_messages_for_dimensions(directive_text: str, dimensions: list[str]) -> tuple[str, str]:
    group = infer_group_for_dimensions(dimensions)
    user = build_group_scoring_prompt(group, directive_text, dimensions)
    return SCORING_SYSTEM_MESSAGE, user
