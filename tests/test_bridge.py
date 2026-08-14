from __future__ import annotations

import json
from copy import deepcopy

import pytest

from bridge_priorities import (
    BridgeConfig,
    BridgeError,
    aggregate_mastery,
    build_bridge,
    drill_need,
    import_sessions,
    load_manual_review_rules,
    load_store,
)


KEY = ("pronoms_relatifs", "possession_dont", None, None)
EVIDENCE = {
    "family_primary_counts": {"pronoms_relatifs": 16, "orthographe_lexicale": 25},
    "rules": [{
        "family": KEY[0], "mechanism_id": KEY[1], "detail_id": None, "tense_id": None,
        "exam_occurrences": 3, "weight_eligible": True,
    }],
}


def mastery(*, attempts=2, errors=2, sessions=2) -> dict:
    return {
        "family": KEY[0], "mechanism_id": KEY[1], "detail_id": None, "tense_id": None,
        "attempts": attempts, "correct": attempts - errors, "errors": errors,
        "sessions": sessions, "error_sessions": min(errors, sessions),
        "current_correct_streak": 0, "last_exposure": None, "last_error": None,
    }


def qcm(*, factor=1.4) -> dict:
    return {
        "family": KEY[0], "mechanism_id": KEY[1], "detail_id": None, "tense_id": None,
        "error_factor": factor,
    }


def feedback(session_id: str, correct: bool, minute: int) -> dict:
    return {
        "schema_version": "hep-drill-feedback/1.0",
        "session_id": session_id,
        "started_at": f"2026-08-09T10:{minute:02d}:00Z",
        "completed_at": f"2026-08-09T10:{minute:02d}:59Z",
        "bank_release": "drills-fixtures",
        "attempts": [{
            "drill_id": "hep-d1-20260809-0001", "family": KEY[0], "mechanism_id": KEY[1],
            "detail_id": None, "tense_id": None, "correct": correct,
            "answered_at": f"2026-08-09T10:{minute:02d}:30Z",
        }],
    }


def row(rows: list[dict]) -> dict:
    return next(item for item in rows if tuple(item.get(name) for name in ("family", "mechanism_id", "detail_id", "tense_id")) == KEY)


def test_no_data_produces_no_priority() -> None:
    assert build_bridge([], [], EVIDENCE) == []


def test_qcm_priority_alone_is_eligible() -> None:
    result = row(build_bridge([], [qcm()], EVIDENCE))
    assert result["eligible"] and result["qcm_active"]
    assert result["personal_factor"] == pytest.approx(1.4)


def test_drill_failures_alone_activate_after_two_sessions() -> None:
    result = row(build_bridge([mastery()], [], EVIDENCE))
    assert result["drill_active"] and result["eligible"]
    assert result["failure_rate"] == pytest.approx(0.5)
    assert result["confidence"] == pytest.approx(1 / 3)
    assert result["drill_factor"] == pytest.approx(1.25)


def test_concordant_signals_use_max_without_double_counting() -> None:
    result = row(build_bridge([mastery()], [qcm(factor=1.4)], EVIDENCE))
    assert result["personal_factor"] == pytest.approx(1.4)
    assert result["personal_factor"] != pytest.approx(1.4 * 1.25)


def test_insufficient_success_does_not_reduce_qcm() -> None:
    result = row(build_bridge([mastery(attempts=5, errors=0, sessions=2)], [qcm()], EVIDENCE))
    assert result["recovery_factor"] == pytest.approx(1.0)
    assert result["adjusted_qcm_factor"] == pytest.approx(1.4)


def test_reliable_success_reduces_but_does_not_erase_qcm() -> None:
    result = row(build_bridge([mastery(attempts=6, errors=0, sessions=2)], [qcm()], EVIDENCE))
    assert result["failure_rate"] == pytest.approx(0.1)
    assert result["recovery_factor"] == pytest.approx(0.64)
    assert result["adjusted_qcm_factor"] == pytest.approx(1.256)


def test_sufficient_stock_zeroes_generation_weight() -> None:
    result = row(build_bridge([], [qcm()], EVIDENCE, unseen_stock={KEY: 5}))
    assert result["stock_gap"] == 0
    assert result["generation_weight"] == 0


def test_empty_stock_and_recent_spacing_apply_documented_bounds() -> None:
    result = row(build_bridge([], [qcm()], EVIDENCE, unseen_stock={KEY: 0}, distance_since_seen={KEY: 0}))
    assert result["stock_gap"] == 1
    assert result["spacing_factor"] == pytest.approx(0.72)


def test_repeated_import_is_idempotent_and_collision_is_rejected(tmp_path) -> None:
    store = tmp_path / "observations.json"
    session = feedback("hep-ds1-session0001", False, 0)
    assert import_sessions([session], store)["imported"] == 1
    assert import_sessions([session], store)["duplicates"] == 1
    assert len(load_store(store)["sessions"]) == 1
    changed = deepcopy(session)
    changed["attempts"][0]["correct"] = True
    with pytest.raises(BridgeError, match="Collision"):
        import_sessions([changed], store)


def test_aggregation_keeps_successes_errors_sessions_and_streak() -> None:
    sessions = [
        feedback("hep-ds1-session0001", False, 0),
        feedback("hep-ds1-session0002", True, 2),
    ]
    result = row(aggregate_mastery(sessions))
    assert result["attempts"] == 2 and result["correct"] == 1 and result["errors"] == 1
    assert result["sessions"] == 2 and result["error_sessions"] == 1
    assert result["current_correct_streak"] == 1


def test_inactive_or_reviewed_qcm_path_does_not_enter_without_signal() -> None:
    assert build_bridge([], [], EVIDENCE) == []


def test_unknown_unproven_path_is_only_eligible_on_explicit_request() -> None:
    unknown = ("famille_inconnue", "mecanisme_inconnu", None, None)
    result = build_bridge([], [], EVIDENCE, requested_paths=[unknown])[0]
    assert result["eligible"] and result["requested"]
    assert not result["exam_proven"]
    assert result["exam_factor"] == pytest.approx(0.30)


def test_manual_review_list_loads_ou_ou_and_rejects_unknown_rule(tmp_path) -> None:
    path = tmp_path / "manual.json"
    document = {
        "schema_version": "hep-manual-review-rules/1.0",
        "rules": [{
            "family": "homophones_grammaticaux",
            "mechanism_id": "ou_ou",
            "detail_id": "core",
            "tense_id": None,
            "reason": "Demande explicite.",
        }],
    }
    path.write_text(json.dumps(document), encoding="utf-8")
    assert load_manual_review_rules(path) == [
        ("homophones_grammaticaux", "ou_ou", "core", None)
    ]

    document["rules"][0]["mechanism_id"] = "regle_absente"
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(BridgeError, match="absente de la pédagogie"):
        load_manual_review_rules(path)
