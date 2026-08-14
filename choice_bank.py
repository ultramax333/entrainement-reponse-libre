"""Construction de la banque autonome à choix orthographiques."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from datetime import date
from pathlib import Path
from typing import Any

from drill_contracts import ANALYSE_DIR, DrillContractError, load_json, normalize_answer, validate_drill_batch

if str(ANALYSE_DIR) not in sys.path:
    sys.path.insert(0, str(ANALYSE_DIR))

from pedagogy_HEP import correction_template, describe, load_pedagogy


ROOT = Path(__file__).resolve().parent
DEFAULT_CANDIDATES = ROOT / "data" / "pilot_candidates.json"
DEFAULT_OPTIONS = ROOT / "data" / "pilot_choice_options.json"
DEFAULT_CORRECTIONS = ROOT / "data" / "pilot_choice_corrections.json"
DEFAULT_MANIFEST = ROOT / "data" / "bank_manifest.json"
DEFAULT_ERROR_MECHANISMS = ROOT / "data" / "error_mechanisms.json"
DEFAULT_OUTPUT = ROOT / "bank.js"

VAGUE_DIAGNOSTICS = (
    "mauvaise réponse",
    "mauvais accord",
    "forme fausse",
    "forme incorrecte",
    "est faux",
    "est incorrect",
)


class ChoiceBankError(ValueError):
    """Erreur de cohérence entre le pilote validé et ses choix."""


def _display_prompt(prompt: str) -> str:
    without_lemma = re.sub(r"\s*\([^()]{1,40}\)", "", prompt)
    return without_lemma.replace("___", "…")


def build_choice_bank(
    candidates: dict[str, Any],
    options: dict[str, Any],
    corrections: dict[str, Any],
    error_mechanisms: dict[str, Any],
) -> dict[str, Any]:
    if options.get("schema_version") != "hep-drill-choice-options/1.0":
        raise ChoiceBankError("Version des choix non prise en charge.")
    drills = validate_drill_batch(candidates.get("drills", []))
    if options.get("source_batch_id") != candidates.get("source_batch_id"):
        raise ChoiceBankError("Le lot des choix ne correspond pas au pilote.")
    if corrections.get("schema_version") != "hep-choice-corrections/2.0":
        raise ChoiceBankError("Version des corrigés non prise en charge.")
    if corrections.get("source_batch_id") != candidates.get("source_batch_id"):
        raise ChoiceBankError("Le lot des corrigés ne correspond pas au pilote.")

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

    if error_mechanisms.get("schema_version") != "hep-error-mechanisms/1.0":
        raise ChoiceBankError("Version des mécanismes d’erreur non prise en charge.")
    mechanism_catalog = error_mechanisms.get("mechanisms")
    if not isinstance(mechanism_catalog, dict) or not mechanism_catalog:
        raise ChoiceBankError("Le catalogue des mécanismes d’erreur est absent.")
    required_mechanism_fields = {"label", "likely_reasoning", "decision_test", "repair_strategy"}
    if any(
        not isinstance(mechanism_id, str)
        or not isinstance(mechanism, dict)
        or set(mechanism) != required_mechanism_fields
        or any(
            not isinstance(mechanism[field], str) or len(mechanism[field].strip()) < 12
            for field in required_mechanism_fields
        )
        for mechanism_id, mechanism in mechanism_catalog.items()
    ):
        raise ChoiceBankError("Le catalogue des mécanismes d’erreur est invalide.")

    correction_rows = corrections.get("corrections")
    if not isinstance(correction_rows, list):
        raise ChoiceBankError("La liste des corrigés est absente.")
    correction_by_id: dict[str, dict[str, dict[str, str]]] = {}
    for row in correction_rows:
        if not isinstance(row, dict) or set(row) != {"drill_id", "diagnostics"}:
            raise ChoiceBankError("Une entrée de corrigé est invalide.")
        drill_id = str(row["drill_id"])
        diagnostics = row["diagnostics"]
        if drill_id in correction_by_id:
            raise ChoiceBankError(f"Corrigé dupliqué pour {drill_id}.")
        if not isinstance(diagnostics, dict) or any(
            not isinstance(choice, str)
            or not isinstance(diagnostic, dict)
            or set(diagnostic) != {"mechanism_id", "reasoning_break"}
            or not isinstance(diagnostic["mechanism_id"], str)
            or diagnostic["mechanism_id"] not in mechanism_catalog
            or not isinstance(diagnostic["reasoning_break"], str)
            or not 12 <= len(diagnostic["reasoning_break"].strip()) <= 280
            for choice, diagnostic in diagnostics.items()
        ):
            raise ChoiceBankError(f"{drill_id}: diagnostics invalides.")
        for diagnostic in diagnostics.values():
            reason = diagnostic["reasoning_break"]
            if any(marker in reason.casefold() for marker in VAGUE_DIAGNOSTICS):
                raise ChoiceBankError(f"{drill_id}: diagnostic trop vague.")
        correction_by_id[drill_id] = diagnostics
    if set(correction_by_id) != expected_ids:
        missing = sorted(expected_ids - set(correction_by_id))
        extra = sorted(set(correction_by_id) - expected_ids)
        raise ChoiceBankError(f"Corrigés incomplets (manquants={missing}, supplémentaires={extra}).")

    pedagogy = load_pedagogy()
    questions = []
    for drill in drills:
        choices = by_id[drill["id"]]
        diagnostics = correction_by_id[drill["id"]]
        accepted = {normalize_answer(answer) for answer in drill["accepted_answers"]}
        matches = [choice for choice in choices if normalize_answer(choice) in accepted]
        if matches != [drill["display_answer"]]:
            raise ChoiceBankError(f"{drill['id']}: une seule réponse affichée doit être correcte.")
        false_choices = {choice for choice in choices if choice != drill["display_answer"]}
        if set(diagnostics) != false_choices:
            raise ChoiceBankError(f"{drill['id']}: un diagnostic est requis pour chaque forme fautive.")
        template = correction_template(
            drill["family"], drill["mechanism_id"], drill["detail_id"], drill["tense_id"],
            document=pedagogy,
        )
        if template is None:
            raise ChoiceBankError(f"{drill['id']}: modèle pédagogique introuvable.")
        application = drill["application_note"].strip()
        conclusion = f"On écrit donc « {drill['display_answer']} » dans cette phrase."
        method = " ".join(
            f"{index}. {step}" for index, step in enumerate(template["method_steps"], 1)
        )
        explanation = (
            f"Règle : {template['rule']}\n"
            f"Méthode : {method}\n"
            f"Dans cette phrase : {application}\n"
            f"Donc : {conclusion}"
        )
        why = {}
        published_diagnostics = {}
        for choice in choices:
            if choice == drill["display_answer"]:
                why[choice] = f"La forme « {choice} » est correcte ici. {application}"
            else:
                source_diagnostic = diagnostics[choice]
                reason = source_diagnostic["reasoning_break"].strip()
                mechanism = mechanism_catalog[source_diagnostic["mechanism_id"]]
                why[choice] = f"`{choice}` : {reason} La forme attendue est « {drill['display_answer']} »."
                published_diagnostics[choice] = {
                    "mechanism_id": source_diagnostic["mechanism_id"],
                    "label": mechanism["label"],
                    "likely_reasoning": mechanism["likely_reasoning"],
                    "reasoning_break": f"La forme « {choice} » {reason}",
                    "decision_test": mechanism["decision_test"],
                    "repair_strategy": mechanism["repair_strategy"],
                }
        description = describe(
            drill["family"], drill["mechanism_id"], drill["detail_id"], drill["tense_id"],
            document=pedagogy,
        )
        questions.append({
            "id": drill["id"],
            "family": drill["family"],
            "mechanism_id": drill["mechanism_id"],
            "rule_label": description["mechanism_label"],
            "detail_id": drill["detail_id"],
            "tense_id": drill["tense_id"],
            "prompt": _display_prompt(drill["prompt"]),
            "choices": choices,
            "answer": drill["display_answer"],
            "correction": {
                "rule": template["rule"],
                "method_steps": template["method_steps"],
                "application": application,
                "conclusion": conclusion,
                "explanation": explanation,
                "why": why,
                "diagnostics": published_diagnostics,
            },
        })

    compact = json.dumps(questions, ensure_ascii=False, separators=(",", ":"))
    digest = hashlib.sha256(compact.encode("utf-8")).hexdigest()[:8]
    return {
        "schema_version": "hep-choice-bank/1.0",
        "release": f"choices-{date.today():%Y%m%d}-{digest}",
        "questions": questions,
    }


def combine_choice_banks(banks: list[dict[str, Any]]) -> dict[str, Any]:
    """Combine des lots déjà validés sans modifier leurs questions."""
    if not banks:
        raise ChoiceBankError("Aucun lot à publier.")
    questions: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for bank in banks:
        if bank.get("schema_version") != "hep-choice-bank/1.0":
            raise ChoiceBankError("Version de banque intermédiaire invalide.")
        rows = bank.get("questions")
        if not isinstance(rows, list) or not rows:
            raise ChoiceBankError("Un lot intermédiaire ne contient aucune question.")
        for question in rows:
            drill_id = question.get("id") if isinstance(question, dict) else None
            if not isinstance(drill_id, str) or not drill_id:
                raise ChoiceBankError("Une question publiée ne possède pas d’identifiant.")
            if drill_id in seen_ids:
                raise ChoiceBankError(f"Question dupliquée entre les lots : {drill_id}.")
            seen_ids.add(drill_id)
            questions.append(question)
    compact = json.dumps(questions, ensure_ascii=False, separators=(",", ":"))
    digest = hashlib.sha256(compact.encode("utf-8")).hexdigest()[:8]
    return {
        "schema_version": "hep-choice-bank/1.0",
        "release": f"choices-{date.today():%Y%m%d}-{digest}",
        "questions": questions,
    }


def build_choice_bank_from_manifest(
    manifest: dict[str, Any], error_mechanisms: dict[str, Any]
) -> dict[str, Any]:
    if set(manifest) != {"schema_version", "batches"}:
        raise ChoiceBankError("Le manifeste de publication contient des champs invalides.")
    if manifest.get("schema_version") != "hep-choice-bank-manifest/1.0":
        raise ChoiceBankError("Version du manifeste de publication invalide.")
    batches = manifest.get("batches")
    if not isinstance(batches, list) or not batches:
        raise ChoiceBankError("Le manifeste de publication ne contient aucun lot.")

    banks = []
    required = {"candidates", "options", "corrections"}
    for index, batch in enumerate(batches, 1):
        if not isinstance(batch, dict) or set(batch) != required:
            raise ChoiceBankError(f"Lot {index} invalide dans le manifeste.")
        paths = {}
        for field in required:
            value = batch[field]
            if not isinstance(value, str) or not value.strip():
                raise ChoiceBankError(f"Lot {index} : chemin {field} invalide.")
            path = (ROOT / value).resolve()
            if path != ROOT and ROOT not in path.parents:
                raise ChoiceBankError(f"Lot {index} : chemin {field} hors du sous-projet.")
            paths[field] = path
        banks.append(build_choice_bank(
            load_json(paths["candidates"]),
            load_json(paths["options"]),
            load_json(paths["corrections"]),
            error_mechanisms,
        ))
    return combine_choice_banks(banks)


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
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--candidates", type=Path)
    parser.add_argument("--options", type=Path)
    parser.add_argument("--corrections", type=Path)
    parser.add_argument("--error-mechanisms", type=Path, default=DEFAULT_ERROR_MECHANISMS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        explicit_sources = (args.candidates, args.options, args.corrections)
        if any(explicit_sources):
            if not all(explicit_sources):
                raise ChoiceBankError(
                    "--candidates, --options et --corrections doivent être fournis ensemble."
                )
            bank = build_choice_bank(
                load_json(args.candidates),
                load_json(args.options),
                load_json(args.corrections),
                load_json(args.error_mechanisms),
            )
        else:
            bank = build_choice_bank_from_manifest(
                load_json(args.manifest), load_json(args.error_mechanisms)
            )
        write_bank(bank, args.output)
    except (DrillContractError, ChoiceBankError) as exc:
        raise SystemExit(f"ERREUR: {exc}") from exc
    print(json.dumps({"release": bank["release"], "questions": len(bank["questions"]), "output": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
