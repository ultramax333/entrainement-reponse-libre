from __future__ import annotations

from collections import Counter
from copy import deepcopy
import json

from jsonschema import Draft202012Validator
import pytest

from choice_production import (
    ROOT,
    ChoiceProductionError,
    audit_production,
    audit_production_batch,
    build_production_plan,
)
from drill_contracts import load_json


def sources() -> tuple[dict, list[dict]]:
    request = load_json(ROOT / "data" / "production_request.json")
    existing = load_json(ROOT / "data" / "pilot_candidates.json")["drills"]
    return request, existing


def test_production_request_matches_closed_schema() -> None:
    request, _ = sources()
    schema = json.loads(
        (ROOT / "schemas" / "hep-choice-production-request.schema.json")
        .read_text(encoding="utf-8")
    )
    Draft202012Validator(schema).validate(request)


def test_plan_reserves_106_unique_slots_with_a_final_six_item_batch() -> None:
    request, existing = sources()
    first = build_production_plan(request, existing)
    second = build_production_plan(request, existing)
    assert first == second
    assert first["new_questions"] == 106
    assert first["existing_questions"] == 42
    assert first["projected_bank_size"] == 148
    assert len(first["batches"]) == 11
    assert all(len(batch["slots"]) == 10 for batch in first["batches"][:-1])
    assert len(first["batches"][-1]["slots"]) == 6
    slots = [slot for batch in first["batches"] for slot in batch["slots"]]
    assert len({slot["drill_id"] for slot in slots}) == 106
    assert slots[0]["drill_id"] == "hep-d1-20260813-0043"
    assert slots[-1]["drill_id"] == "hep-d1-20260813-0148"
    counts = Counter(
        (slot["family"], slot["mechanism_id"], slot["detail_id"], slot["tense_id"])
        for slot in slots
    )
    assert sorted(counts.values()) == [6, 10, 10, 10, 10, 20, 20, 20]
    assert sum(slot["constraints"]["target_choice_count"] == 2 for slot in slots) == 6
    assert sum(slot["constraints"]["target_choice_count"] == 4 for slot in slots) == 100


def test_plan_rejects_incomplete_quotas_and_unknown_rule() -> None:
    request, existing = sources()
    incomplete = deepcopy(request)
    incomplete["quotas"][0]["count"] -= 1
    with pytest.raises(ChoiceProductionError, match="somme des quotas"):
        build_production_plan(incomplete, existing)

    unknown = deepcopy(request)
    unknown["quotas"][0]["mechanism_id"] = "mecanisme_absent"
    with pytest.raises(ChoiceProductionError, match="Règle canonique absente"):
        build_production_plan(unknown, existing)


def test_batch_audit_requires_four_choices_and_three_diagnostics(monkeypatch) -> None:
    monkeypatch.setattr("choice_production.load_qcm_signatures", lambda: [])
    candidates_source = load_json(ROOT / "data" / "pilot_candidates.json")
    options_source = load_json(ROOT / "data" / "pilot_choice_options.json")
    corrections_source = load_json(ROOT / "data" / "pilot_choice_corrections.json")
    mechanisms = load_json(ROOT / "data" / "error_mechanisms.json")
    drill = candidates_source["drills"][0]
    batch = {
        "batch_id": "test-batch",
        "slots": [{
            "drill_id": drill["id"],
            "source_batch_id": drill["source_batch_id"],
            "family": drill["family"],
            "mechanism_id": drill["mechanism_id"],
            "detail_id": drill["detail_id"],
            "tense_id": drill["tense_id"],
            "constraints": {"target_choice_count": 4},
        }],
    }
    candidates = {
        "source_batch_id": candidates_source["source_batch_id"],
        "drills": [drill],
    }
    options = {
        "schema_version": options_source["schema_version"],
        "source_batch_id": options_source["source_batch_id"],
        "options": [options_source["options"][0]],
    }
    corrections = {
        "schema_version": corrections_source["schema_version"],
        "source_batch_id": corrections_source["source_batch_id"],
        "corrections": [corrections_source["corrections"][0]],
    }
    audit = audit_production_batch(
        batch, candidates, options, corrections, [], mechanisms
    )
    assert audit["publishable"] is True
    assert audit["summary"]["assembled"] == 1

    reduced = deepcopy(options)
    removed = reduced["options"][0]["choices"].pop()
    reduced_corrections = deepcopy(corrections)
    reduced_corrections["corrections"][0]["diagnostics"].pop(removed, None)
    rejected = audit_production_batch(
        batch, candidates, reduced, reduced_corrections, [], mechanisms
    )
    assert rejected["publishable"] is False
    assert any("CHOICE_COUNT_MISMATCH" in defect for defect in rejected["defects"])


def test_complete_production_materializes_and_passes_exhaustive_audit(monkeypatch) -> None:
    from production_content import materialize

    monkeypatch.setattr("choice_production.load_qcm_signatures", lambda: [])
    plan = load_json(ROOT / "data" / "drill_plan.json")
    candidates, options, corrections = materialize()
    report = audit_production(
        plan,
        candidates,
        options,
        corrections,
        load_json(ROOT / "data" / "pilot_candidates.json")["drills"],
        load_json(ROOT / "data" / "error_mechanisms.json"),
    )
    assert report["publishable"]
    assert report["summary"] == {
        "planned": 106,
        "candidates": 106,
        "options": 106,
        "corrections": 106,
        "batches_passed": 11,
        "batches_total": 11,
        "lint_pass": 106,
    }


def test_ou_ou_supplement_is_balanced_and_uses_only_two_relevant_choices() -> None:
    from production_content import materialize

    candidates, options, corrections = materialize()
    option_by_id = {item["drill_id"]: item for item in options["options"]}
    correction_by_id = {
        item["drill_id"]: item for item in corrections["corrections"]
    }
    drills = [
        drill for drill in candidates["drills"]
        if drill["mechanism_id"] == "ou_ou"
    ]
    assert len(drills) == 6
    assert Counter(drill["display_answer"] for drill in drills) == {"ou": 3, "où": 3}
    for drill in drills:
        choices = option_by_id[drill["id"]]["choices"]
        diagnostics = correction_by_id[drill["id"]]["diagnostics"]
        assert len(choices) == 2
        assert set(choices) == {"ou", "où"}
        assert set(diagnostics) == (set(choices) - {drill["display_answer"]})
