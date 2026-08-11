"""Contrats purs et normalisation des drills HEP.

Les textes pédagogiques et la taxonomie restent dans les sources canoniques du
projet parent. Ce module ne conserve que les contraintes propres au format libre.
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parent
ANALYSE_DIR = ROOT.parent / "analyse_gpt"
PEDAGOGY_PATH = ANALYSE_DIR / "pedagogy_HEP.json"
SCHEMA_DIR = ROOT / "schemas"

DRILL_KEYS = {
    "schema_version", "id", "source_batch_id", "family", "mechanism_id",
    "detail_id", "tense_id", "prompt", "accepted_answers", "display_answer",
    "application_note", "pedagogy_dict_version",
}
FEEDBACK_KEYS = {
    "schema_version", "session_id", "started_at", "completed_at",
    "bank_release", "attempts",
}
ATTEMPT_KEYS = {
    "drill_id", "family", "mechanism_id", "detail_id", "tense_id",
    "correct", "answered_at",
}
SHORT_ID_RE = re.compile(r"^[a-z][a-z0-9_]{1,63}$")
DRILL_ID_RE = re.compile(r"^hep-d1-\d{8}-\d{4}$")
BATCH_ID_RE = re.compile(r"^hep-db1-\d{8}-\d{4}$")
SESSION_ID_RE = re.compile(r"^hep-ds1-[A-Za-z0-9_-]{8,80}$")


class DrillContractError(ValueError):
    """Erreur de contrat stable, destinée au lint et aux tests."""


def normalize_answer(value: str, *, case_sensitive: bool = True) -> str:
    """Normalise sans jamais effacer les accents.

    NFC, espaces et apostrophes sont les seules normalisations communes. La
    casse n'est neutralisée que sur demande explicite de la politique appelante.
    """
    normalized = unicodedata.normalize("NFC", str(value))
    normalized = re.sub(r"\s+", " ", normalized.strip())
    normalized = normalized.replace("\u2019", "'").replace("\u02bc", "'")
    return normalized if case_sensitive else normalized.casefold()


def path_key(item: dict[str, Any]) -> tuple[str, str, str | None, str | None]:
    return (
        str(item.get("family") or ""),
        str(item.get("mechanism_id") or ""),
        item.get("detail_id") or None,
        item.get("tense_id") or None,
    )


def _canonical_pedagogy() -> tuple[Any, Any, dict[str, Any]]:
    if str(ANALYSE_DIR) not in sys.path:
        sys.path.insert(0, str(ANALYSE_DIR))
    from pedagogy_HEP import correction_template, load_pedagogy, validate_classification
    return correction_template, validate_classification, load_pedagogy(PEDAGOGY_PATH)


def _iso_datetime(value: Any, label: str) -> datetime:
    if not isinstance(value, str):
        raise DrillContractError(f"{label}: date absente.")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.utcoffset() is None:
            raise ValueError("timezone missing")
        return parsed
    except ValueError as exc:
        raise DrillContractError(f"{label}: date ISO 8601 invalide.") from exc


def _closed_object(value: Any, expected: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise DrillContractError(f"{label}: objet attendu.")
    missing = expected - set(value)
    extra = set(value) - expected
    if missing or extra:
        raise DrillContractError(
            f"{label}: propriétés invalides (manquantes={sorted(missing)}, supplémentaires={sorted(extra)})."
        )
    return value


def validate_drill(drill: Any, *, case_sensitive: bool = True) -> dict[str, Any]:
    value = _closed_object(drill, DRILL_KEYS, "drill")
    if value["schema_version"] != "hep-drill/1.0":
        raise DrillContractError("drill: schema_version non prise en charge.")
    if not DRILL_ID_RE.fullmatch(str(value["id"])):
        raise DrillContractError("drill: id invalide.")
    if not BATCH_ID_RE.fullmatch(str(value["source_batch_id"])):
        raise DrillContractError("drill: source_batch_id invalide.")
    for name in ("family", "mechanism_id"):
        if not SHORT_ID_RE.fullmatch(str(value.get(name) or "")):
            raise DrillContractError(f"drill: {name} invalide.")
    for name in ("detail_id", "tense_id"):
        if value.get(name) is not None and not SHORT_ID_RE.fullmatch(str(value[name])):
            raise DrillContractError(f"drill: {name} invalide.")
    if str(value.get("prompt") or "").count("___") != 1:
        raise DrillContractError("drill: exactement un blanc ___ est requis.")
    if not 8 <= len(str(value["prompt"])) <= 320:
        raise DrillContractError("drill: longueur du prompt invalide.")
    answers = value.get("accepted_answers")
    if not isinstance(answers, list) or not 1 <= len(answers) <= 8:
        raise DrillContractError("drill: accepted_answers doit contenir 1 à 8 réponses.")
    if any(not isinstance(answer, str) or not 1 <= len(answer.strip()) <= 80 for answer in answers):
        raise DrillContractError("drill: réponse admise vide ou trop longue.")
    normalized = [normalize_answer(answer, case_sensitive=case_sensitive) for answer in answers]
    if len(normalized) != len(set(normalized)):
        raise DrillContractError("drill: réponses admises dupliquées après normalisation.")
    display = normalize_answer(value.get("display_answer", ""), case_sensitive=case_sensitive)
    if display not in normalized:
        raise DrillContractError("drill: display_answer n'appartient pas aux réponses admises.")
    if not 12 <= len(str(value.get("application_note") or "").strip()) <= 360:
        raise DrillContractError("drill: application_note absente ou trop longue.")

    correction_template, validate_classification, pedagogy = _canonical_pedagogy()
    if value.get("pedagogy_dict_version") != pedagogy.get("schema_version"):
        raise DrillContractError("drill: version pédagogique périmée.")
    defects = validate_classification(
        value.get("family"), value.get("mechanism_id"), value.get("detail_id"),
        require_detail=False, require_precise_variant=False, document=pedagogy,
    )
    if defects:
        raise DrillContractError("drill: chemin canonique invalide: " + ", ".join(defects))
    if correction_template(*path_key(value), document=pedagogy) is None:
        raise DrillContractError("drill: aucune fiche pédagogique ne résout ce chemin.")
    return value


def validate_feedback(session: Any) -> dict[str, Any]:
    value = _closed_object(session, FEEDBACK_KEYS, "feedback")
    if value["schema_version"] != "hep-drill-feedback/1.0":
        raise DrillContractError("feedback: schema_version non prise en charge.")
    if not SESSION_ID_RE.fullmatch(str(value["session_id"])):
        raise DrillContractError("feedback: session_id invalide.")
    if not re.fullmatch(r"drills-[A-Za-z0-9_-]{4,80}", str(value["bank_release"])):
        raise DrillContractError("feedback: bank_release invalide.")
    started = _iso_datetime(value["started_at"], "started_at")
    completed = _iso_datetime(value["completed_at"], "completed_at")
    if completed < started:
        raise DrillContractError("feedback: completed_at précède started_at.")
    attempts = value.get("attempts")
    if not isinstance(attempts, list) or not 1 <= len(attempts) <= 500:
        raise DrillContractError("feedback: 1 à 500 tentatives sont requises.")
    _, validate_classification, pedagogy = _canonical_pedagogy()
    previous: datetime | None = None
    for index, attempt in enumerate(attempts):
        item = _closed_object(attempt, ATTEMPT_KEYS, f"attempts[{index}]")
        if not DRILL_ID_RE.fullmatch(str(item["drill_id"])):
            raise DrillContractError(f"attempts[{index}]: drill_id invalide.")
        if not SHORT_ID_RE.fullmatch(str(item["family"])) or not SHORT_ID_RE.fullmatch(str(item["mechanism_id"])):
            raise DrillContractError(f"attempts[{index}]: chemin invalide.")
        for name in ("detail_id", "tense_id"):
            if item.get(name) is not None and not SHORT_ID_RE.fullmatch(str(item[name])):
                raise DrillContractError(f"attempts[{index}]: {name} invalide.")
        defects = validate_classification(
            item["family"], item["mechanism_id"], item.get("detail_id"),
            require_detail=False, require_precise_variant=False, document=pedagogy,
        )
        if defects:
            raise DrillContractError(
                f"attempts[{index}]: chemin canonique invalide: " + ", ".join(defects)
            )
        if not isinstance(item["correct"], bool):
            raise DrillContractError(f"attempts[{index}]: correct doit être booléen.")
        when = _iso_datetime(item["answered_at"], f"attempts[{index}].answered_at")
        if when < started or when > completed:
            raise DrillContractError(f"attempts[{index}]: answered_at hors de la séance.")
        if previous and when < previous:
            raise DrillContractError("feedback: tentatives non chronologiques.")
        previous = when
    return value


def validate_drill_batch(drills: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    validated = [validate_drill(drill) for drill in drills]
    ids = [drill["id"] for drill in validated]
    if len(ids) != len(set(ids)):
        raise DrillContractError("lot: collision d'identifiants.")
    return validated


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DrillContractError(f"Impossible de lire {path}: {exc}") from exc
