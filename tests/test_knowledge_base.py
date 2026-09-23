from __future__ import annotations

import json
from pathlib import Path

KB_DIR = Path(__file__).resolve().parents[1] / "knowledge_base"


def _load(name: str) -> dict:
    with (KB_DIR / name).open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    assert isinstance(value, dict)
    return value


def test_behavior_tags_are_unique_and_observational() -> None:
    patterns = _load("behavior_patterns.json")["patterns"]
    tags = [tag for pattern in patterns for tag in pattern["tags"]]
    assert len(tags) == len(set(tags)) + 2  # delayed_response and reduced_contact are deliberate overlaps
    prohibited = {
        "npd",
        "bpd",
        "personality",
        "disorder",
        "anxiety",
        "attachment",
        "insecurity",
        "low_priority",
        "envy",
        "control",
        "dominance",
    }
    assert not {tag for tag in tags if any(term in tag.lower() for term in prohibited)}


def test_alternative_rules_use_known_tags_and_no_fake_likelihoods() -> None:
    patterns = _load("behavior_patterns.json")["patterns"]
    allowed_tags = {tag for pattern in patterns for tag in pattern["tags"]}
    rules = _load("alternative_explanations.json")["rules"]
    assert rules
    for rule in rules:
        assert set(rule["behavior_tags"]) <= allowed_tags
        assert len(rule["alternatives"]) >= 2
        assert "primary_mechanism" not in rule
        for alternative in rule["alternatives"]:
            assert "likelihood" not in alternative
            assert alternative["what_to_check"]


def test_mechanisms_have_counterevidence_and_evidence_caveats() -> None:
    mechanisms = _load("psychological_mechanisms.json")["mechanisms"]
    names = [item["name"] for item in mechanisms]
    assert len(names) == len(set(names))
    for mechanism in mechanisms:
        assert mechanism["counterevidence"]
        basis = mechanism["scientific_basis"].lower()
        assert "pointer only" in basis or "hypothesis only" in basis


def test_nonruntime_case_example_uses_known_tags_and_no_embeddings() -> None:
    patterns = _load("behavior_patterns.json")["patterns"]
    allowed_tags = {tag for pattern in patterns for tag in pattern["tags"]}
    cases = _load("cases.json")
    assert cases["runtime_status"] == "not_loaded"
    encoded = json.dumps(cases, ensure_ascii=False).lower()
    assert "embedding_model" not in encoded
    assert '"embedding"' not in encoded
    for case in cases["cases"]:
        assert set(case["behavior_tags"]) <= allowed_tags
