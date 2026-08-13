from __future__ import annotations

from copy import deepcopy
import json

from jsonschema import Draft202012Validator

from choice_bank import ROOT


def documents() -> tuple[dict, dict]:
    schema = json.loads(
        (ROOT / "schemas" / "hep-choice-corrections.schema.json").read_text(encoding="utf-8")
    )
    corrections = json.loads(
        (ROOT / "data" / "pilot_choice_corrections.json").read_text(encoding="utf-8")
    )
    return schema, corrections


def test_choice_corrections_match_closed_schema() -> None:
    schema, corrections = documents()
    Draft202012Validator(schema).validate(corrections)
    assert len(corrections["corrections"]) == 42
    assert sum(len(row["diagnostics"]) for row in corrections["corrections"]) == 122


def test_choice_correction_schema_rejects_generated_rule_duplication() -> None:
    schema, corrections = documents()
    invalid = deepcopy(corrections)
    invalid["corrections"][0]["rule"] = "Texte qui doit rester dans la pédagogie canonique."
    assert list(Draft202012Validator(schema).iter_errors(invalid))
