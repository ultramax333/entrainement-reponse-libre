from __future__ import annotations

from copy import deepcopy

import pytest

from choice_bank import ROOT, ChoiceBankError, build_choice_bank
from drill_contracts import load_json


def sources() -> tuple[dict, dict]:
    return load_json(ROOT / "data" / "pilot_candidates.json"), load_json(
        ROOT / "data" / "pilot_choice_options.json"
    )


def test_choice_bank_contains_twenty_resolved_questions() -> None:
    candidates, options = sources()
    bank = build_choice_bank(candidates, options)
    assert len(bank["questions"]) == 20
    assert all(2 <= len(question["choices"]) <= 4 for question in bank["questions"])
    assert all(question["choices"].count(question["answer"]) == 1 for question in bank["questions"])
    assert all("___" not in question["prompt"] for question in bank["questions"])


def test_choice_bank_rejects_missing_or_ambiguous_choices() -> None:
    candidates, options = sources()
    missing = deepcopy(options)
    missing["options"].pop()
    with pytest.raises(ChoiceBankError, match="Choix incomplets"):
        build_choice_bank(candidates, missing)

    ambiguous = deepcopy(options)
    ambiguous["options"][0]["choices"] = ["impartialité", "impartialité"]
    with pytest.raises(ChoiceBankError, match="dupliqués"):
        build_choice_bank(candidates, ambiguous)
