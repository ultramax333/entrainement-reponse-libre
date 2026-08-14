"""Mémoire drill séparée et bridge de besoins HEP déterministe."""

from __future__ import annotations

import hashlib
import json
import math
import os
import sys
import tempfile
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from drill_contracts import DrillContractError, path_key, validate_feedback


ROOT = Path(__file__).resolve().parent
ANALYSE_DIR = ROOT.parent / "analyse_gpt"
DEFAULT_STORE = ROOT / "data" / "drill_observations.json"
DEFAULT_QCM_PRIORITIES = ANALYSE_DIR / "error_priorities_HEP.txt"
DEFAULT_EXAM_EVIDENCE = ANALYSE_DIR / "exam_rule_evidence_HEP.json"
DEFAULT_WEIGHTING = ANALYSE_DIR / "error_weighting_HEP.yaml"
DEFAULT_MANUAL_RULES = ROOT / "data" / "manual_review_rules.json"


class BridgeError(ValueError):
    pass


@dataclass(frozen=True)
class BridgeConfig:
    alpha: float = 1.0
    beta: float = 3.0
    exposure_scale: int = 6
    session_target: int = 2
    min_attempts: int = 2
    min_errors: int = 2
    min_sessions: int = 2
    min_confidence: float = 0.25
    reliable_attempts: int = 6
    error_gain: float = 1.5
    stock_target: int = 5
    spacing_window: int = 48
    spacing_floor: float = 0.72
    exam_importance_floor: float = 0.55
    unproven_exam_factor: float = 0.30


def load_bridge_config(path: Path = DEFAULT_WEIGHTING) -> BridgeConfig:
    """Lit les constantes communes sans maintenir une deuxième configuration."""
    try:
        import yaml
        value = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, ImportError, ValueError) as exc:
        raise BridgeError(f"Impossible de lire la pondération HEP: {exc}") from exc
    return BridgeConfig(
        alpha=float(value["smoothing"]["alpha"]),
        beta=float(value["smoothing"]["beta"]),
        exposure_scale=int(value["confidence"]["exposure_scale"]),
        session_target=int(value["confidence"]["session_target"]),
        min_attempts=int(value["activation"]["min_attempts"]),
        min_errors=int(value["activation"]["min_errors"]),
        min_sessions=int(value["activation"]["min_sessions"]),
        min_confidence=float(value["activation"]["min_confidence"]),
        error_gain=float(value["weighting"]["error_gain"]),
        spacing_window=int(value["spacing"]["recovery_questions"]),
        spacing_floor=float(value["spacing"]["minimum_factor"]),
        exam_importance_floor=float(value["weighting"]["exam_importance_floor"]),
        unproven_exam_factor=float(value["weighting"]["unproven_exam_factor_floor"]),
    )


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def source_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _empty_store() -> dict[str, Any]:
    return {"schema_version": "hep-drill-observations/1.0", "sessions": []}


def load_store(path: Path = DEFAULT_STORE) -> dict[str, Any]:
    if not path.exists():
        return _empty_store()
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BridgeError(f"Impossible de lire {path}: {exc}") from exc
    if value.get("schema_version") != "hep-drill-observations/1.0" or not isinstance(value.get("sessions"), list):
        raise BridgeError("Journal drill absent ou de version inconnue.")
    return value


def load_manual_review_rules(
    path: Path = DEFAULT_MANUAL_RULES,
) -> list[tuple[str, str, str | None, str | None]]:
    """Charge les demandes volontaires sans les transformer en fausses erreurs."""
    if not path.exists():
        return []
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BridgeError(f"Impossible de lire {path}: {exc}") from exc
    if set(value) != {"schema_version", "rules"}:
        raise BridgeError("La liste manuelle ne respecte pas le contrat fermé.")
    if value.get("schema_version") != "hep-manual-review-rules/1.0":
        raise BridgeError("Version de liste manuelle inconnue.")
    rows = value.get("rules")
    if not isinstance(rows, list) or len(rows) > 100:
        raise BridgeError("La liste manuelle est absente ou trop longue.")
    required = {"family", "mechanism_id", "detail_id", "tense_id", "reason"}
    paths = []
    if str(ANALYSE_DIR) not in sys.path:
        sys.path.insert(0, str(ANALYSE_DIR))
    try:
        from pedagogy_HEP import correction_template, load_pedagogy
        pedagogy = load_pedagogy()
    except Exception as exc:
        raise BridgeError(f"Chargement de la pédagogie HEP impossible: {exc}") from exc
    for row in rows:
        if not isinstance(row, dict) or set(row) != required:
            raise BridgeError("Une règle manuelle ne respecte pas le contrat fermé.")
        if not all(isinstance(row[key], str) and row[key].strip() for key in ("family", "mechanism_id", "reason")):
            raise BridgeError("Une règle manuelle contient un identifiant vide.")
        if any(row[key] is not None and not isinstance(row[key], str) for key in ("detail_id", "tense_id")):
            raise BridgeError("Le détail ou le temps d’une règle manuelle est invalide.")
        path_value = path_key(row)
        if correction_template(*path_value, document=pedagogy) is None:
            raise BridgeError(
                "Règle manuelle absente de la pédagogie HEP: "
                + "/".join(str(item) for item in path_value)
            )
        paths.append(path_value)
    if len(paths) != len(set(paths)):
        raise BridgeError("La liste manuelle contient un chemin en double.")
    return paths


def atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


def import_sessions(sessions: Iterable[dict[str, Any]], path: Path = DEFAULT_STORE) -> dict[str, Any]:
    """Ajoute des séances validées; un même session_id est idempotent."""
    store = load_store(path)
    by_id = {str(item["session_id"]): item for item in store["sessions"]}
    imported = duplicate = 0
    for raw in sessions:
        try:
            session = validate_feedback(raw)
        except DrillContractError as exc:
            raise BridgeError(str(exc)) from exc
        session_id = str(session["session_id"])
        previous = by_id.get(session_id)
        if previous is not None:
            if canonical_bytes(previous) != canonical_bytes(session):
                raise BridgeError(f"Collision de session_id avec contenu différent: {session_id}")
            duplicate += 1
            continue
        by_id[session_id] = session
        imported += 1
    ordered = sorted(by_id.values(), key=lambda item: (item["completed_at"], item["session_id"]))
    result = {"schema_version": "hep-drill-observations/1.0", "sessions": ordered}
    if imported:
        atomic_write_json(path, result)
    return {"imported": imported, "duplicates": duplicate, "total_sessions": len(ordered)}


def aggregate_mastery(sessions: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: dict[tuple[str, str, str | None, str | None], dict[str, Any]] = {}
    ordered = sorted(sessions, key=lambda item: (item["completed_at"], item["session_id"]))
    for session in ordered:
        touched: set[tuple[str, str, str | None, str | None]] = set()
        errored: set[tuple[str, str, str | None, str | None]] = set()
        for attempt in session["attempts"]:
            key = path_key(attempt)
            row = rows.setdefault(key, {
                "family": key[0], "mechanism_id": key[1], "detail_id": key[2], "tense_id": key[3],
                "attempts": 0, "correct": 0, "errors": 0, "sessions": 0,
                "error_sessions": 0, "current_correct_streak": 0,
                "last_exposure": None, "last_error": None,
            })
            row["attempts"] += 1
            row["last_exposure"] = attempt["answered_at"]
            touched.add(key)
            if attempt["correct"]:
                row["correct"] += 1
                row["current_correct_streak"] += 1
            else:
                row["errors"] += 1
                row["current_correct_streak"] = 0
                row["last_error"] = attempt["answered_at"]
                errored.add(key)
        for key in touched:
            rows[key]["sessions"] += 1
        for key in errored:
            rows[key]["error_sessions"] += 1
    return sorted(rows.values(), key=lambda row: path_key(row))


def drill_need(row: Mapping[str, Any], config: BridgeConfig) -> dict[str, Any]:
    attempts = int(row.get("attempts") or 0)
    errors = int(row.get("errors") or 0)
    sessions = int(row.get("sessions") or 0)
    failure_rate = (errors + config.alpha) / (attempts + config.alpha + config.beta)
    confidence = min(1.0, attempts / config.exposure_scale) * min(1.0, sessions / config.session_target)
    need = failure_rate * confidence
    active = (
        attempts >= config.min_attempts
        and errors >= config.min_errors
        and sessions >= config.min_sessions
        and confidence >= config.min_confidence
    )
    reliable = attempts >= config.reliable_attempts and sessions >= config.session_target
    reliable_success = (1.0 - failure_rate) * confidence if reliable else 0.0
    return {
        "failure_rate": failure_rate,
        "confidence": confidence,
        "drill_failure_need": need,
        "active": active,
        "reliable_success": reliable_success,
    }


def parse_qcm_priorities(path: Path = DEFAULT_QCM_PRIORITIES) -> list[dict[str, Any]]:
    """Réutilise le parseur canonique du pipeline QCM en lecture seule."""
    if str(ANALYSE_DIR) not in sys.path:
        sys.path.insert(0, str(ANALYSE_DIR))
    try:
        from pipeline_HEP import parse_error_priorities
        return list(parse_error_priorities(path)["priorities"])
    except Exception as exc:
        raise BridgeError(f"Lecture des priorités QCM impossible: {exc}") from exc


def _qcm_factor(key: tuple[str, str, str | None, str | None], rows: Iterable[dict[str, Any]]) -> tuple[float, bool]:
    exact: list[float] = []
    generic: list[float] = []
    for row in rows:
        row_key = path_key(row)
        if row_key[:2] != key[:2]:
            continue
        factor = float(row.get("error_factor") or row.get("qcm_factor") or 1.0)
        if row_key == key:
            exact.append(factor)
        elif row_key[2:] == (None, None):
            generic.append(factor)
    values = exact or generic
    return (max(values), True) if values else (1.0, False)


def _exam_index(document: dict[str, Any]) -> tuple[dict[str, int], set[tuple[str, str, str | None, str | None]]]:
    family_counts = {str(k): int(v) for k, v in (document.get("family_primary_counts") or {}).items()}
    proven = {
        path_key(row) for row in document.get("rules", [])
        if int(row.get("exam_occurrences") or 0) > 0 and row.get("weight_eligible", True)
    }
    return family_counts, proven


def _exam_factor(key: tuple[str, str, str | None, str | None], document: dict[str, Any], config: BridgeConfig) -> tuple[float, bool]:
    family_counts, proven = _exam_index(document)
    direct = key in proven or (
        key[2:] == (None, None) and any(candidate[:2] == key[:2] for candidate in proven)
    )
    if not direct:
        return config.unproven_exam_factor, False
    maximum = max(family_counts.values(), default=1)
    count = family_counts.get(key[0], 0)
    normalized = math.sqrt(count / maximum) if count else 0.0
    return config.exam_importance_floor + (1.0 - config.exam_importance_floor) * normalized, True


def _mapping_value(values: Mapping[Any, Any], key: tuple[str, str, str | None, str | None], default: float) -> float:
    if key in values:
        return float(values[key])
    serialized = "|".join(part or "UNK" for part in key)
    return float(values.get(serialized, default))


def build_bridge(
    mastery_rows: Iterable[dict[str, Any]],
    qcm_rows: Iterable[dict[str, Any]],
    exam_evidence: dict[str, Any],
    *,
    unseen_stock: Mapping[Any, int] | None = None,
    distance_since_seen: Mapping[Any, int] | None = None,
    requested_paths: Iterable[tuple[str, str, str | None, str | None]] = (),
    config: BridgeConfig = BridgeConfig(),
) -> list[dict[str, Any]]:
    mastery = {path_key(row): row for row in mastery_rows}
    qcm = list(qcm_rows)
    requested = set(requested_paths)
    keys = set(mastery) | {path_key(row) for row in qcm} | requested
    stocks = unseen_stock or {}
    distances = distance_since_seen or {}
    results: list[dict[str, Any]] = []
    for key in keys:
        row = mastery.get(key, {"attempts": 0, "errors": 0, "sessions": 0})
        need = drill_need(row, config)
        qcm_factor, qcm_active = _qcm_factor(key, qcm)
        recovery_factor = max(0.60, 1.0 - 0.40 * need["reliable_success"])
        adjusted_qcm_factor = 1.0 + (qcm_factor - 1.0) * recovery_factor
        drill_factor = 1.0 + config.error_gain * need["drill_failure_need"]
        personal_factor = max(adjusted_qcm_factor, drill_factor)
        stock = _mapping_value(stocks, key, 0)
        stock_gap = min(1.0, max(0.0, (config.stock_target - stock) / config.stock_target))
        distance = _mapping_value(distances, key, config.spacing_window)
        spacing_factor = config.spacing_floor + (1.0 - config.spacing_floor) * min(
            1.0, max(0.0, distance) / config.spacing_window
        )
        exam_factor, exam_proven = _exam_factor(key, exam_evidence, config)
        eligible = qcm_active or need["active"] or key in requested
        generation_weight = exam_factor * personal_factor * stock_gap * spacing_factor if eligible else 0.0
        results.append({
            "family": key[0], "mechanism_id": key[1], "detail_id": key[2], "tense_id": key[3],
            "eligible": eligible, "requested": key in requested,
            "exam_proven": exam_proven, "exam_factor": exam_factor,
            "qcm_active": qcm_active, "qcm_factor": qcm_factor,
            "recovery_factor": recovery_factor, "adjusted_qcm_factor": adjusted_qcm_factor,
            "drill_active": need["active"], "failure_rate": need["failure_rate"],
            "confidence": need["confidence"], "drill_failure_need": need["drill_failure_need"],
            "drill_factor": drill_factor, "personal_factor": personal_factor,
            "unseen_available": int(stock), "stock_gap": stock_gap,
            "distance_since_seen": int(distance), "spacing_factor": spacing_factor,
            "generation_weight": generation_weight,
        })
    return sorted(results, key=lambda row: (-row["generation_weight"], path_key(row)))


def bridge_audit(
    mastery_rows: list[dict[str, Any]], bridge_rows: list[dict[str, Any]],
    *, sources: Mapping[str, Path] | None = None, config: BridgeConfig = BridgeConfig(),
) -> dict[str, Any]:
    source_meta = {
        label: {"path": str(path), "sha256": source_sha256(path)}
        for label, path in (sources or {}).items() if path.exists()
    }
    return {
        "schema_version": "hep-drill-bridge-audit/1.0",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "formula": "exam_factor * max(adjusted_qcm_factor, drill_factor) * stock_gap * spacing_factor",
        "config": asdict(config), "sources": source_meta,
        "mastery": mastery_rows, "priorities": bridge_rows,
    }
