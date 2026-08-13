from __future__ import annotations

from copy import deepcopy

import pytest

from choice_bank import ROOT, ChoiceBankError, build_choice_bank
from drill_contracts import load_json


def sources() -> tuple[dict, dict, dict, dict]:
    return (
        load_json(ROOT / "data" / "pilot_candidates.json"),
        load_json(ROOT / "data" / "pilot_choice_options.json"),
        load_json(ROOT / "data" / "pilot_choice_corrections.json"),
        load_json(ROOT / "data" / "error_mechanisms.json"),
    )


def test_choice_bank_contains_resolved_questions() -> None:
    candidates, options, corrections, mechanisms = sources()
    bank = build_choice_bank(candidates, options, corrections, mechanisms)
    assert len(bank["questions"]) == 42
    assert all(2 <= len(question["choices"]) <= 4 for question in bank["questions"])
    assert all(question["choices"].count(question["answer"]) == 1 for question in bank["questions"])
    assert all("___" not in question["prompt"] for question in bank["questions"])
    assert all(question["rule_label"] for question in bank["questions"])
    assert sum(question["mechanism_id"] == "nom_peuple_adjectif_langue" for question in bank["questions"]) == 2
    assert all("application_note" not in question for question in bank["questions"])
    assert all(set(question["correction"]["why"]) == set(question["choices"]) for question in bank["questions"])
    assert all(
        set(question["correction"]["diagnostics"])
        == {choice for choice in question["choices"] if choice != question["answer"]}
        for question in bank["questions"]
    )
    assert all(
        all(marker in question["correction"]["explanation"] for marker in ("Règle :", "Méthode :", "Dans cette phrase :", "Donc :"))
        for question in bank["questions"]
    )


def test_choice_bank_rejects_missing_or_ambiguous_choices() -> None:
    candidates, options, corrections, mechanisms = sources()
    missing = deepcopy(options)
    missing["options"].pop()
    with pytest.raises(ChoiceBankError, match="Choix incomplets"):
        build_choice_bank(candidates, missing, corrections, mechanisms)

    ambiguous = deepcopy(options)
    ambiguous["options"][0]["choices"] = ["impartialité", "impartialité"]
    with pytest.raises(ChoiceBankError, match="dupliqués"):
        build_choice_bank(candidates, ambiguous, corrections, mechanisms)


def test_choice_bank_rejects_missing_distractor_diagnostic() -> None:
    candidates, options, corrections, mechanisms = sources()
    incomplete = deepcopy(corrections)
    incomplete["corrections"][0]["diagnostics"].pop("impartialitée")
    with pytest.raises(ChoiceBankError, match="diagnostic est requis"):
        build_choice_bank(candidates, options, incomplete, mechanisms)


def test_choice_bank_rejects_vague_distractor_diagnostic() -> None:
    candidates, options, corrections, mechanisms = sources()
    vague = deepcopy(corrections)
    first_diagnostic = next(iter(vague["corrections"][0]["diagnostics"]))
    vague["corrections"][0]["diagnostics"][first_diagnostic]["reasoning_break"] = "C’est une forme incorrecte dans cette phrase."
    with pytest.raises(ChoiceBankError, match="diagnostic trop vague"):
        build_choice_bank(candidates, options, vague, mechanisms)


def test_choice_bank_rejects_unknown_error_mechanism() -> None:
    candidates, options, corrections, mechanisms = sources()
    unknown = deepcopy(corrections)
    first_diagnostic = next(iter(unknown["corrections"][0]["diagnostics"].values()))
    first_diagnostic["mechanism_id"] = "mecanisme_inconnu"
    with pytest.raises(ChoiceBankError, match="diagnostics invalides"):
        build_choice_bank(candidates, options, unknown, mechanisms)
