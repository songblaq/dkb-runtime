"""Pure unit tests for verdict policy helpers (no database)."""

from __future__ import annotations

from dkb_runtime.services.verdict import _apply_rules, _match_rule_condition


def test_match_rule_condition_exact_string() -> None:
    states = {"legal_state": "no_license", "trust_state": "unknown"}
    assert _match_rule_condition(states, {"legal_state": "no_license"}) is True
    assert _match_rule_condition(states, {"legal_state": "clear"}) is False


def test_match_rule_condition_list_allows_any_listed() -> None:
    states = {"trust_state": "verified", "legal_state": "clear", "lifecycle_state": "active"}
    cond = {
        "trust_state": "verified",
        "legal_state": ["clear", "custom"],
        "lifecycle_state": "active",
    }
    assert _match_rule_condition(states, cond) is True
    states_bad = dict(states)
    states_bad["legal_state"] = "no_license"
    assert _match_rule_condition(states_bad, cond) is False


def test_match_rule_condition_empty_condition_is_true() -> None:
    assert _match_rule_condition({"a": "b"}, {}) is True


def test_apply_rules_applies_first_matching_then_sequential() -> None:
    policy = {
        "example_rules": [
            {
                "name": "rule_a",
                "if": {"legal_state": "no_license"},
                "then": {"trust_state": "caution", "recommendation_state": "excluded"},
            },
            {
                "name": "rule_b",
                "if": {"trust_state": "caution"},
                "then": {"recommendation_state": "deprecated"},
            },
        ]
    }
    states = {
        "provenance_state": "unknown",
        "trust_state": "unknown",
        "legal_state": "no_license",
        "lifecycle_state": "active",
        "recommendation_state": "candidate",
    }
    out, trace = _apply_rules(policy, states)
    assert out["trust_state"] == "caution"
    assert out["recommendation_state"] == "deprecated"
    assert trace == ["rule_a", "rule_b"]


def test_apply_rules_defaults_unchanged_when_no_match() -> None:
    policy = {"example_rules": [{"name": "noop", "if": {"legal_state": "clear"}, "then": {"trust_state": "verified"}}]}
    states = {
        "provenance_state": "unknown",
        "trust_state": "unknown",
        "legal_state": "no_license",
        "lifecycle_state": "active",
        "recommendation_state": "candidate",
    }
    out, trace = _apply_rules(policy, states)
    assert out["trust_state"] == "unknown"
    assert trace == []


def test_apply_rules_archived_demote_from_policy_shape() -> None:
    policy = {
        "example_rules": [
            {
                "name": "archived_demote",
                "if": {"lifecycle_state": ["archived", "disappeared"]},
                "then": {"recommendation_state": "deprecated"},
            }
        ]
    }
    states = {
        "provenance_state": "vendor",
        "trust_state": "reviewing",
        "legal_state": "clear",
        "lifecycle_state": "archived",
        "recommendation_state": "preferred",
    }
    out, trace = _apply_rules(policy, states)
    assert out["recommendation_state"] == "deprecated"
    assert "archived_demote" in trace
