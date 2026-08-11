from __future__ import annotations

import json

import pytest

from pipeline_drills import (
    CANONICAL_DRILL_BANK,
    PipelineDrillError,
    lint_drills,
    plan_slots,
    publish_canonical_bank,
    publish_test_bank,
)
from test_contracts import drill


def bridge_row(**overrides) -> dict:
    value = {
        "family": "accord_participe_passe",
        "mechanism_id": "avoir_cvd_avant",
        "detail_id": "core",
        "tense_id": "passe_compose",
        "eligible": True,
        "generation_weight": 0.9,
        "unseen_available": 2,
        "exam_factor": 0.8,
        "personal_factor": 1.2,
        "stock_gap": 0.6,
        "spacing_factor": 1.0,
    }
    value.update(overrides)
    return value


def test_planner_is_deterministic_and_respects_stock_gap() -> None:
    bridge = {"generated_at": "2026-08-09T00:00:00Z", "priorities": [bridge_row()]}
    first = plan_slots(bridge, limit=20)
    second = plan_slots(bridge, limit=20)
    assert first == second
    assert len(first["slots"]) == 3
    assert all(slot["case_sensitive"] for slot in first["slots"])
    assert all(slot["constraints"]["hide_rule_before_answer"] for slot in first["slots"])


def test_lint_recomposes_and_detects_drill_duplicates() -> None:
    first = drill()
    second = drill()
    second["id"] = "hep-d1-20260809-0002"
    report = lint_drills([first, second])
    assert report["reports"][0]["status"] == "PASS"
    assert report["reports"][0]["reconstructed_sentences"] == [
        "Les lettres qu’elle a envoyées sont arrivées."
    ]
    assert "DUPLICATE_DRILL:hep-d1-20260809-0001" in report["reports"][1]["defects"]


def test_lint_compares_qcm_statement_signatures() -> None:
    value = drill()
    report = lint_drills([value], [{
        "id": "qcm-1",
        "statement_signature": "les lettres qu elle a sont arrivees",
    }])
    assert "DUPLICATE_QCM:qcm-1" in report["reports"][0]["defects"]


def test_publication_is_atomic_on_test_copy_and_refuses_canonical_target(tmp_path) -> None:
    target = tmp_path / "drills.js"
    result = publish_test_bank([drill()], target)
    assert result["drills"] == 1 and target.is_file()
    assert "Artefact de test géné" in target.read_text(encoding="utf-8")
    with pytest.raises(PipelineDrillError, match="validation utilisateur"):
        publish_test_bank([drill()], CANONICAL_DRILL_BANK)


def test_canonical_publication_requires_explicit_confirmation() -> None:
    with pytest.raises(PipelineDrillError, match="confirm-pilot"):
        publish_canonical_bank([drill()])
