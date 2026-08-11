"""Construction de la banque autonome à choix orthographiques."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from datetime import date
from pathlib import Path
from typing import Any

from drill_contracts import DrillContractError, load_json, normalize_answer, validate_drill_batch


ROOT = Path(__file__).resolve().parent
DEFAULT_CANDIDATES = ROOT / "data" / "pilot_candidates.json"
DEFAULT_OPTIONS = ROOT / "data" / "pilot_choice_options.json"
DEFAULT_OUTPUT = ROOT / "bank.js"


class ChoiceBankError(ValueError):
    """Erreur de cohérence entre le pilote validé et ses choix."""


def _display_prompt(prompt: str) -> str:
    without_lemma = re.sub(r"\s*\([^()]{1,40}\)", "", prompt)
    return without_lemma.replace("___", "…")


def build_choice_bank(candidates: dict[str, Any], options: dict[str, Any]) -> dict[str, Any]:
    if options.get("schema_version") != "hep-drill-choice-options/1.0":
        raise ChoiceBankError("Version des choix non prise en charge.")
    drills = validate_drill_batch(candidates.get("drills", []))
    if options.get("source_batch_id") != candidates.get("source_batch_id"):
        raise ChoiceBankError("Le lot des choix ne correspond pas au pilote.")

    rows = options.get("options")
    if not isinstance(rows, list):
        raise ChoiceBankError("La liste des choix est absente.")
    by_id: dict[str, list[str]] = {}
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"drill_id", "choices"}:
            raise ChoiceBankError("Une entrée de choix est invalide.")
        drill_id = str(row["drill_id"])
        choices = row["choices"]
        if drill_id in by_id:
            raise ChoiceBankError(f"Choix dupliqués pour {drill_id}.")
        if not isinstance(choices, list) or not 2 <= len(choices) <= 4:
            raise ChoiceBankError(f"{drill_id}: 2 à 4 choix sont requis.")
        if any(not isinstance(item, str) or not item.strip() or len(item) > 80 for item in choices):
            raise ChoiceBankError(f"{drill_id}: choix vide ou trop long.")
        normalized = [normalize_answer(item) for item in choices]
        if len(normalized) != len(set(normalized)):
            raise ChoiceBankError(f"{drill_id}: choix dupliqués après normalisation.")
        by_id[drill_id] = choices

    expected_ids = {drill["id"] for drill in drills}
    if set(by_id) != expected_ids:
        missing = sorted(expected_ids - set(by_id))
        extra = sorted(set(by_id) - expected_ids)
        raise ChoiceBankError(f"Choix incomplets (manquants={missing}, supplémentaires={extra}).")

    questions = []
    for drill in drills:
        choices = by_id[drill["id"]]
        accepted = {normalize_answer(answer) for answer in drill["accepted_answers"]}
        matches = [choice for choice in choices if normalize_answer(choice) in accepted]
        if matches != [drill["display_answer"]]:
            raise ChoiceBankError(f"{drill['id']}: une seule réponse affichée doit être correcte.")
        questions.append({
            "id": drill["id"],
            "family": drill["family"],
            "mechanism_id": drill["mechanism_id"],
            "detail_id": drill["detail_id"],
            "prompt": _display_prompt(drill["prompt"]),
            "choices": choices,
            "answer": drill["display_answer"],
            "application_note": drill["application_note"],
        })

    compact = json.dumps(questions, ensure_ascii=False, separators=(",", ":"))
    digest = hashlib.sha256(compact.encode("utf-8")).hexdigest()[:8]
    return {
        "schema_version": "hep-choice-bank/1.0",
        "release": f"choices-{date.today():%Y%m%d}-{digest}",
        "questions": questions,
    }


def write_bank(bank: dict[str, Any], output: Path) -> None:
    resolved = output.resolve()
    payload = (
        "// Banque générée depuis le pilote validé et ses choix contrôlés.\n"
        f"window.HEP_CHOICE_BANK = {json.dumps(bank, ensure_ascii=False, separators=(',', ':'))};\n"
        "if (typeof module !== 'undefined') module.exports = window.HEP_CHOICE_BANK;\n"
    )
    resolved.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{resolved.name}.", suffix=".tmp", dir=resolved.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, resolved)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--options", type=Path, default=DEFAULT_OPTIONS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        bank = build_choice_bank(load_json(args.candidates), load_json(args.options))
        write_bank(bank, args.output)
    except (DrillContractError, ChoiceBankError) as exc:
        raise SystemExit(f"ERREUR: {exc}") from exc
    print(json.dumps({"release": bank["release"], "questions": len(bank["questions"]), "output": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
