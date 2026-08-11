from __future__ import annotations

import json
from copy import deepcopy

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from drill_contracts import (
    DrillContractError,
    SCHEMA_DIR,
    normalize_answer,
    validate_drill,
    validate_feedback,
)


def drill() -> dict:
    # Fixture reprise du contrat DATA_AND_WEIGHTING.md; ce n'est pas une banque.
    return {
        "schema_version": "hep-drill/1.0",
        "id": "hep-d1-20260809-0001",
        "source_batch_id": "hep-db1-20260809-0001",
        "family": "accord_participe_passe",
        "mechanism_id": "avoir_cvd_avant",
        "detail_id": "core",
        "tense_id": "passe_compose",
        "prompt": "Les lettres qu’elle a ___ sont arrivées.",
        "accepted_answers": ["envoyées"],
        "display_answer": "envoyées",
        "application_note": "Le COD « qu’ » reprend « les lettres » et précède le participe.",
        "pedagogy_dict_version": "hep-pedagogy-dict/2.0",
    }


def feedback() -> dict:
    return {
        "schema_version": "hep-drill-feedback/1.0",
        "session_id": "hep-ds1-abcdefghijkl",
        "started_at": "2026-08-09T10:00:00Z",
        "completed_at": "2026-08-09T10:01:00Z",
        "bank_release": "drills-fixtures",
        "attempts": [{
            "drill_id": "hep-d1-20260809-0001",
            "family": "accord_participe_passe",
            "mechanism_id": "avoir_cvd_avant",
            "detail_id": "core",
            "tense_id": "passe_compose",
            "correct": False,
            "answered_at": "2026-08-09T10:00:30Z",
        }],
    }


def validator(name: str) -> Draft202012Validator:
    schema = json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def test_schemas_accept_contract_examples() -> None:
    assert not list(validator("hep-drill.schema.json").iter_errors(drill()))
    assert not list(validator("hep-drill-feedback.schema.json").iter_errors(feedback()))


def test_schemas_reject_additional_properties() -> None:
    value = drill()
    value["rule_text"] = "copie interdite"
    errors = list(validator("hep-drill.schema.json").iter_errors(value))
    assert any(error.validator == "additionalProperties" for error in errors)


def test_normalization_preserves_accents_and_equates_apostrophes_spaces() -> None:
    assert normalize_answer("  l’été   passé ") == "l'été passé"
    assert normalize_answer("é") != normalize_answer("e")
    assert normalize_answer("É", case_sensitive=False) == normalize_answer("é", case_sensitive=False)
    assert normalize_answer("É") != normalize_answer("é")


def test_validate_drill_requires_one_blank_and_unique_answers() -> None:
    value = drill()
    value["prompt"] = "Les lettres sont arrivées."
    with pytest.raises(DrillContractError, match="exactement un blanc"):
        validate_drill(value)
    value = drill()
    value["accepted_answers"] = ["l’une", "l'une"]
    value["display_answer"] = "l'une"
    with pytest.raises(DrillContractError, match="dupliquées"):
        validate_drill(value)


def test_validate_drill_resolves_canonical_pedagogy() -> None:
    assert validate_drill(drill())["mechanism_id"] == "avoir_cvd_avant"
    value = drill()
    value["mechanism_id"] = "mecanisme_invente"
    with pytest.raises(DrillContractError, match="PEDAGOGY_MECHANISM_UNKNOWN"):
        validate_drill(value)


def test_feedback_rejects_raw_answer_and_invalid_timeline() -> None:
    value = feedback()
    value["attempts"][0]["raw_answer"] = "sensible"
    with pytest.raises(DrillContractError, match="supplémentaires"):
        validate_feedback(value)
    value = feedback()
    value["attempts"][0]["answered_at"] = "2026-08-09T10:02:00Z"
    with pytest.raises(DrillContractError, match="hors de la séance"):
        validate_feedback(value)


def test_feedback_rejects_unknown_path_and_timezone_free_dates() -> None:
    value = feedback()
    value["attempts"][0]["mechanism_id"] = "mecanisme_invente"
    with pytest.raises(DrillContractError, match="PEDAGOGY_MECHANISM_UNKNOWN"):
        validate_feedback(value)
    value = feedback()
    value["started_at"] = "2026-08-09T10:00:00"
    with pytest.raises(DrillContractError, match="date ISO 8601 invalide"):
        validate_feedback(value)
