from __future__ import annotations

import json

from jsonschema import Draft202012Validator

from choice_bank import ROOT


def test_error_mechanisms_match_closed_schema_and_are_all_used() -> None:
    schema = json.loads(
        (ROOT / "schemas" / "hep-error-mechanisms.schema.json").read_text(encoding="utf-8")
    )
    catalog = json.loads((ROOT / "data" / "error_mechanisms.json").read_text(encoding="utf-8"))
    corrections = json.loads(
        (ROOT / "data" / "pilot_choice_corrections.json").read_text(encoding="utf-8")
    )
    Draft202012Validator(schema).validate(catalog)
    used = {
        diagnostic["mechanism_id"]
        for row in corrections["corrections"]
        for diagnostic in row["diagnostics"].values()
    }
    assert used == set(catalog["mechanisms"])


def test_every_likely_reasoning_remains_probabilistic() -> None:
    catalog = json.loads((ROOT / "data" / "error_mechanisms.json").read_text(encoding="utf-8"))
    assert all(
        "probablement" in mechanism["likely_reasoning"]
        for mechanism in catalog["mechanisms"].values()
    )
