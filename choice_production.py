#!/usr/bin/env python3
"""Prépare et audite les lots de nouveaux exercices à choix diagnostiques."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

from bridge_priorities import ANALYSE_DIR, atomic_write_json
from choice_bank import ChoiceBankError, build_choice_bank
from drill_contracts import DrillContractError, load_json, validate_drill_batch
from pipeline_drills import lint_drills, load_qcm_signatures, project_plan_context

if str(ANALYSE_DIR) not in sys.path:
    sys.path.insert(0, str(ANALYSE_DIR))

from pedagogy_HEP import correction_template, load_pedagogy


ROOT = Path(__file__).resolve().parent
DEFAULT_REQUEST = ROOT / "data" / "production_request.json"
DEFAULT_EXISTING = ROOT / "data" / "pilot_candidates.json"
DEFAULT_PLAN = ROOT / "data" / "drill_plan.json"
DEFAULT_CONTEXT = ROOT / "data" / "prompt_context.json"
DEFAULT_MECHANISMS = ROOT / "data" / "error_mechanisms.json"

REQUEST_KEYS = {
    "schema_version", "request_id", "source_batch_id", "count", "batch_size",
    "first_sequence", "level", "target_choice_count", "review_mode", "quotas",
}
QUOTA_KEYS = {"family", "mechanism_id", "detail_id", "tense_id", "count"}
QUOTA_CHOICE_KEYS = QUOTA_KEYS | {"target_choice_count"}
REQUEST_ID_RE = re.compile(r"^hep-cpr1-(\d{8})-\d{4}$")
BATCH_ID_RE = re.compile(r"^hep-db1-(\d{8})-\d{4}$")


class ChoiceProductionError(ValueError):
    """Erreur bloquante dans la préparation ou l’audit d’un lot."""


def _path(value: dict[str, Any]) -> tuple[Any, Any, Any, Any]:
    return (
        value.get("family"), value.get("mechanism_id"),
        value.get("detail_id"), value.get("tense_id"),
    )


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def validate_production_request(
    request: dict[str, Any], existing_drills: list[dict[str, Any]],
) -> dict[str, Any]:
    if not isinstance(request, dict) or set(request) != REQUEST_KEYS:
        raise ChoiceProductionError("La demande de production ne respecte pas le contrat fermé.")
    if request.get("schema_version") != "hep-choice-production-request/1.0":
        raise ChoiceProductionError("Version de demande de production non prise en charge.")
    if not REQUEST_ID_RE.fullmatch(str(request.get("request_id") or "")):
        raise ChoiceProductionError("Identifiant de demande invalide.")
    batch_match = BATCH_ID_RE.fullmatch(str(request.get("source_batch_id") or ""))
    if not batch_match:
        raise ChoiceProductionError("Identifiant de lot source invalide.")
    count = request.get("count")
    batch_size = request.get("batch_size")
    first_sequence = request.get("first_sequence")
    if not isinstance(count, int) or not 1 <= count <= 500:
        raise ChoiceProductionError("Le nombre demandé doit être compris entre 1 et 500.")
    if not isinstance(batch_size, int) or not 5 <= batch_size <= 20:
        raise ChoiceProductionError("La taille nominale des lots doit être comprise entre 5 et 20.")
    if not isinstance(first_sequence, int) or first_sequence < 1 or first_sequence + count - 1 > 9999:
        raise ChoiceProductionError("La plage d’identifiants dépasse le contrat HEP.")
    if request.get("level") != "bac" or request.get("target_choice_count") != 4:
        raise ChoiceProductionError("La production exige le niveau bac et quatre choix par défaut.")
    if request.get("review_mode") != "exhaustive":
        raise ChoiceProductionError("La première production de 100 exige une revue exhaustive.")
    quotas = request.get("quotas")
    if not isinstance(quotas, list) or not quotas:
        raise ChoiceProductionError("Aucun quota de règle n’est défini.")
    if any(
        not isinstance(row, dict) or set(row) not in (QUOTA_KEYS, QUOTA_CHOICE_KEYS)
        for row in quotas
    ):
        raise ChoiceProductionError("Un quota de règle est invalide.")
    if any(not isinstance(row["count"], int) or row["count"] < 1 for row in quotas):
        raise ChoiceProductionError("Chaque quota doit être strictement positif.")
    if any(
        not isinstance(row.get("target_choice_count", request["target_choice_count"]), int)
        or not 2 <= row.get("target_choice_count", request["target_choice_count"]) <= 4
        for row in quotas
    ):
        raise ChoiceProductionError("Chaque quota doit prévoir entre deux et quatre choix.")
    if sum(row["count"] for row in quotas) != count:
        raise ChoiceProductionError("La somme des quotas ne correspond pas au total demandé.")
    paths = [_path(row) for row in quotas]
    if len(paths) != len(set(paths)):
        raise ChoiceProductionError("Un chemin canonique est présent plusieurs fois dans les quotas.")

    pedagogy = load_pedagogy()
    for row in quotas:
        template = correction_template(
            row["family"], row["mechanism_id"], row["detail_id"], row["tense_id"],
            document=pedagogy,
        )
        if template is None:
            raise ChoiceProductionError(
                "Règle canonique absente de la pédagogie HEP: " + "/".join(
                    str(value) for value in _path(row)
                )
            )

    existing_ids = {str(drill["id"]) for drill in validate_drill_batch(existing_drills)}
    date_code = batch_match.group(1)
    reserved_ids = {
        f"hep-d1-{date_code}-{sequence:04d}"
        for sequence in range(first_sequence, first_sequence + count)
    }
    collisions = sorted(existing_ids & reserved_ids)
    if collisions:
        raise ChoiceProductionError(f"Identifiants déjà utilisés: {collisions[:5]}")
    return deepcopy(request)


def build_production_plan(
    request: dict[str, Any], existing_drills: list[dict[str, Any]],
) -> dict[str, Any]:
    validated = validate_production_request(request, existing_drills)
    remaining = [row["count"] for row in validated["quotas"]]
    ordered_paths: list[dict[str, Any]] = []
    while len(ordered_paths) < validated["count"]:
        for index, quota in enumerate(validated["quotas"]):
            if remaining[index] <= 0:
                continue
            ordered_paths.append(quota)
            remaining[index] -= 1
    date_code = BATCH_ID_RE.fullmatch(validated["source_batch_id"]).group(1)  # type: ignore[union-attr]
    slots = []
    for index, quota in enumerate(ordered_paths):
        sequence = validated["first_sequence"] + index
        slots.append({
            "slot_id": f"hep-cslot1-{index + 1:04d}",
            "drill_id": f"hep-d1-{date_code}-{sequence:04d}",
            "source_batch_id": validated["source_batch_id"],
            "family": quota["family"],
            "mechanism_id": quota["mechanism_id"],
            "detail_id": quota["detail_id"],
            "tense_id": quota["tense_id"],
            "type": "single_blank_choice_diagnostic",
            "level": validated["level"],
            "case_sensitive": True,
            "constraints": {
                "blank_count": 1,
                "target_choice_count": quota.get("target_choice_count", validated["target_choice_count"]),
                "target_distractor_count": quota.get("target_choice_count", validated["target_choice_count"]) - 1,
                "distinct_error_reasoning_preferred": True,
                "hide_rule_before_answer": True,
                "accents_significant": True,
            },
        })
    fingerprint = hashlib.sha256(_canonical_json(slots)).hexdigest()
    batches = []
    size = validated["batch_size"]
    for offset in range(0, len(slots), size):
        batch_slots = slots[offset:offset + size]
        batches.append({
            "batch_index": len(batches) + 1,
            "batch_id": f"hep-cbatch1-{len(batches) + 1:02d}",
            "slots": batch_slots,
        })
    return {
        "schema_version": "hep-choice-production-plan/1.0",
        "request_id": validated["request_id"],
        "source_batch_id": validated["source_batch_id"],
        "fingerprint": fingerprint,
        "new_questions": len(slots),
        "existing_questions": len(existing_drills),
        "projected_bank_size": len(existing_drills) + len(slots),
        "batch_size": size,
        "review_mode": validated["review_mode"],
        "batches": batches,
    }


def project_production_context(plan: dict[str, Any]) -> dict[str, Any]:
    slots = [slot for batch in plan.get("batches", []) for slot in batch.get("slots", [])]
    projected = project_plan_context({"fingerprint": plan["fingerprint"], "slots": slots})
    return {
        "schema_version": "hep-choice-production-context/1.0",
        "plan_fingerprint": plan["fingerprint"],
        "rules": projected["rules"],
        "pedagogy": projected["pedagogy"],
        "diagnostic_catalog": load_json(DEFAULT_MECHANISMS),
        "stages": [
            "phrase_answer_application",
            "choices_and_diagnostics",
            "independent_review",
            "targeted_correction",
        ],
    }


def audit_production_batch(
    batch: dict[str, Any],
    candidates_document: dict[str, Any],
    options: dict[str, Any],
    corrections: dict[str, Any],
    existing_drills: list[dict[str, Any]],
    mechanisms: dict[str, Any],
) -> dict[str, Any]:
    candidates = validate_drill_batch(candidates_document.get("drills", []))
    planned = {slot["drill_id"]: slot for slot in batch.get("slots", [])}
    actual = {drill["id"]: drill for drill in candidates}
    defects: list[str] = []
    if set(actual) != set(planned):
        defects.append("BATCH_IDS_MISMATCH")
    for drill_id in sorted(set(actual) & set(planned)):
        if _path(actual[drill_id]) != _path(planned[drill_id]):
            defects.append(f"{drill_id}:PATH_MISMATCH")
        if actual[drill_id]["source_batch_id"] != planned[drill_id]["source_batch_id"]:
            defects.append(f"{drill_id}:SOURCE_BATCH_MISMATCH")

    combined_lint = lint_drills([*existing_drills, *candidates], load_qcm_signatures())
    new_reports = combined_lint["reports"][len(existing_drills):]
    for report in new_reports:
        defects.extend(
            f"{report['drill_id']}:{defect}" for defect in report["defects"]
        )
    try:
        bank = build_choice_bank(candidates_document, options, corrections, mechanisms)
    except (ChoiceBankError, DrillContractError) as exc:
        defects.append(f"CHOICE_BANK:{exc}")
        bank = {"questions": []}
    for question in bank["questions"]:
        expected_choices = planned[question["id"]]["constraints"]["target_choice_count"]
        expected_diagnostics = expected_choices - 1
        if len(question["choices"]) != expected_choices:
            defects.append(f"{question['id']}:CHOICE_COUNT_MISMATCH")
        if len(question["correction"]["diagnostics"]) != expected_diagnostics:
            defects.append(f"{question['id']}:DIAGNOSTIC_COUNT_MISMATCH")
    return {
        "schema_version": "hep-choice-production-audit/1.0",
        "batch_id": batch.get("batch_id"),
        "publishable": not defects and len(bank["questions"]) == len(planned),
        "defects": defects,
        "summary": {
            "planned": len(planned),
            "candidates": len(candidates),
            "assembled": len(bank["questions"]),
            "lint_pass": sum(not report["defects"] for report in new_reports),
        },
    }


def _slice_for_batch(
    batch: dict[str, Any],
    candidates: dict[str, Any],
    options: dict[str, Any],
    corrections: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Projette des documents de production complets sur un lot du plan."""
    ids = {slot["drill_id"] for slot in batch.get("slots", [])}
    candidate_slice = deepcopy(candidates)
    candidate_slice["drills"] = [
        drill for drill in candidates.get("drills", []) if drill.get("id") in ids
    ]
    option_slice = deepcopy(options)
    option_slice["options"] = [
        item for item in options.get("options", []) if item.get("drill_id") in ids
    ]
    correction_slice = deepcopy(corrections)
    correction_slice["corrections"] = [
        item for item in corrections.get("corrections", []) if item.get("drill_id") in ids
    ]
    return candidate_slice, option_slice, correction_slice


def audit_production(
    plan: dict[str, Any],
    candidates: dict[str, Any],
    options: dict[str, Any],
    corrections: dict[str, Any],
    existing_drills: list[dict[str, Any]],
    mechanisms: dict[str, Any],
) -> dict[str, Any]:
    """Audite exhaustivement une production complète, lot après lot."""
    reports = []
    for batch in plan.get("batches", []):
        slices = _slice_for_batch(batch, candidates, options, corrections)
        reports.append(audit_production_batch(
            batch, *slices, existing_drills, mechanisms,
        ))
    planned_ids = {
        slot["drill_id"]
        for batch in plan.get("batches", [])
        for slot in batch.get("slots", [])
    }
    candidate_ids = {item.get("id") for item in candidates.get("drills", [])}
    option_ids = {item.get("drill_id") for item in options.get("options", [])}
    correction_ids = {item.get("drill_id") for item in corrections.get("corrections", [])}
    defects = [
        f"{report['batch_id']}:{defect}"
        for report in reports
        for defect in report["defects"]
    ]
    if candidate_ids != planned_ids:
        defects.append("PRODUCTION_CANDIDATE_IDS_MISMATCH")
    if option_ids != planned_ids:
        defects.append("PRODUCTION_OPTION_IDS_MISMATCH")
    if correction_ids != planned_ids:
        defects.append("PRODUCTION_CORRECTION_IDS_MISMATCH")
    return {
        "schema_version": "hep-choice-production-review/1.0",
        "plan_fingerprint": plan.get("fingerprint"),
        "review_mode": plan.get("review_mode"),
        "model": "gpt-5.6-sol",
        "reasoning": "high",
        "publishable": not defects and len(candidate_ids) == len(planned_ids),
        "defects": defects,
        "summary": {
            "planned": len(planned_ids),
            "candidates": len(candidate_ids),
            "options": len(option_ids),
            "corrections": len(correction_ids),
            "batches_passed": sum(report["publishable"] for report in reports),
            "batches_total": len(reports),
            "lint_pass": sum(report["summary"]["lint_pass"] for report in reports),
        },
        "batches": reports,
    }


def _select_batch(plan: dict[str, Any], index: int) -> dict[str, Any]:
    batches = plan.get("batches", [])
    if not 1 <= index <= len(batches):
        raise ChoiceProductionError("Numéro de lot absent du plan.")
    return batches[index - 1]


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--request", type=Path, default=DEFAULT_REQUEST)
    prepare.add_argument("--existing", type=Path, default=DEFAULT_EXISTING)
    prepare.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    prepare.add_argument("--context", type=Path, default=DEFAULT_CONTEXT)
    audit = commands.add_parser("audit-batch")
    audit.add_argument("plan", type=Path)
    audit.add_argument("batch_index", type=int)
    audit.add_argument("candidates", type=Path)
    audit.add_argument("options", type=Path)
    audit.add_argument("corrections", type=Path)
    audit.add_argument("output", type=Path)
    audit.add_argument("--existing", type=Path, default=DEFAULT_EXISTING)
    audit_all = commands.add_parser("audit-all")
    audit_all.add_argument("plan", type=Path)
    audit_all.add_argument("candidates", type=Path)
    audit_all.add_argument("options", type=Path)
    audit_all.add_argument("corrections", type=Path)
    audit_all.add_argument("output", type=Path)
    audit_all.add_argument("--existing", type=Path, default=DEFAULT_EXISTING)
    return root


def main() -> None:
    args = parser().parse_args()
    try:
        if args.command == "prepare":
            existing = load_json(args.existing).get("drills", [])
            plan = build_production_plan(load_json(args.request), existing)
            context = project_production_context(plan)
            atomic_write_json(args.plan, plan)
            atomic_write_json(args.context, context)
            result = {
                "plan": str(args.plan), "context": str(args.context),
                "batches": len(plan["batches"]),
                "new_questions": plan["new_questions"],
                "projected_bank_size": plan["projected_bank_size"],
                "fingerprint": plan["fingerprint"],
            }
        elif args.command == "audit-batch":
            plan = load_json(args.plan)
            result = audit_production_batch(
                _select_batch(plan, args.batch_index),
                load_json(args.candidates), load_json(args.options),
                load_json(args.corrections),
                load_json(args.existing).get("drills", []),
                load_json(DEFAULT_MECHANISMS),
            )
            atomic_write_json(args.output, result)
        else:
            result = audit_production(
                load_json(args.plan), load_json(args.candidates),
                load_json(args.options), load_json(args.corrections),
                load_json(args.existing).get("drills", []),
                load_json(DEFAULT_MECHANISMS),
            )
            atomic_write_json(args.output, result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ChoiceProductionError, ChoiceBankError, DrillContractError) as exc:
        raise SystemExit(f"ERREUR: {exc}") from exc


if __name__ == "__main__":
    main()
