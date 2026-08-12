from __future__ import annotations

from copy import deepcopy
import json

from jsonschema import Draft202012Validator

from choice_bank import ROOT


def documents() -> tuple[dict, dict]:
    schema = json.loads(
        (ROOT / "schemas" / "hep-qcm-review-priorities.schema.json").read_text(encoding="utf-8")
    )
    example = json.loads(
        (ROOT / "data" / "qcm_review_priorities.example.json").read_text(encoding="utf-8")
    )
    return schema, example


def test_qcm_priority_example_matches_closed_schema() -> None:
    schema, example = documents()
    Draft202012Validator(schema).validate(example)


def test_qcm_priority_schema_rejects_answers_and_question_text() -> None:
    schema, example = documents()
    validator = Draft202012Validator(schema)
    leaking = deepcopy(example)
    leaking["selected_answer"] = "une réponse qui ne doit pas sortir du QCM"
    assert list(validator.iter_errors(leaking))

    leaking = deepcopy(example)
    leaking["priorities"][0]["question"] = "texte interdit"
    assert list(validator.iter_errors(leaking))
