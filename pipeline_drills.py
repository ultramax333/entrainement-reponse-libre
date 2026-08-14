#!/usr/bin/env python3
"""CLI minimal pour planifier et contrôler les drills, sans générateur intégré."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
import tempfile
import unicodedata
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any, Iterable

from bridge_priorities import (
    ANALYSE_DIR,
    DEFAULT_EXAM_EVIDENCE,
    DEFAULT_MANUAL_RULES,
    DEFAULT_QCM_PRIORITIES,
    DEFAULT_STORE,
    BridgeError,
    aggregate_mastery,
    atomic_write_json,
    bridge_audit,
    build_bridge,
    import_sessions,
    load_bridge_config,
    load_manual_review_rules,
    load_store,
    parse_qcm_priorities,
)
from drill_contracts import (
    DrillContractError,
    load_json,
    normalize_answer,
    path_key,
    validate_drill,
    validate_drill_batch,
)


ROOT = Path(__file__).resolve().parent
QCM_SIGNATURES = ANALYSE_DIR / "signatures_banque.json"
CANONICAL_DRILL_BANK = ROOT.parent / "quiz-app" / "entrainement" / "drills.js"


class PipelineDrillError(ValueError):
    pass


def _items(value: Any, *keys: str) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        for key in keys:
            if isinstance(value.get(key), list):
                return value[key]
    raise PipelineDrillError("Une liste d'objets est attendue.")


def _write_json(path: Path, value: Any) -> None:
    atomic_write_json(path, value)


def _stock_and_spacing(
    drills: Iterable[dict[str, Any]], sessions: Iterable[dict[str, Any]],
) -> tuple[dict[Any, int], dict[Any, int]]:
    by_path: dict[Any, set[str]] = defaultdict(set)
    for drill in drills:
        by_path[path_key(drill)].add(str(drill["id"]))
    seen_ids: set[str] = set()
    attempts: list[dict[str, Any]] = []
    for session in sorted(sessions, key=lambda item: (item["completed_at"], item["session_id"])):
        attempts.extend(session["attempts"])
        seen_ids.update(str(item["drill_id"]) for item in session["attempts"])
    unseen = {key: len(ids - seen_ids) for key, ids in by_path.items()}
    distances: dict[Any, int] = {}
    total = len(attempts)
    for index, attempt in enumerate(attempts):
        distances[path_key(attempt)] = total - index - 1
    return unseen, distances


def build_current_bridge(bank: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    store = load_store()
    mastery = aggregate_mastery(store["sessions"])
    qcm = parse_qcm_priorities()
    evidence = load_json(DEFAULT_EXAM_EVIDENCE)
    config = load_bridge_config()
    requested = load_manual_review_rules()
    unseen, distances = _stock_and_spacing(bank or [], store["sessions"])
    rows = build_bridge(
        mastery, qcm, evidence, unseen_stock=unseen,
        distance_since_seen=distances, requested_paths=requested, config=config,
    )
    return bridge_audit(
        mastery, rows,
        sources={
            "qcm_priorities": DEFAULT_QCM_PRIORITIES,
            "exam_evidence": DEFAULT_EXAM_EVIDENCE,
            "drill_observations": DEFAULT_STORE,
            "manual_review_rules": DEFAULT_MANUAL_RULES,
        },
        config=config,
    )


def plan_slots(bridge: dict[str, Any], *, limit: int) -> dict[str, Any]:
    priorities = [row for row in bridge.get("priorities", []) if row.get("eligible") and row.get("generation_weight", 0) > 0]
    slots: list[dict[str, Any]] = []
    round_index = 0
    while len(slots) < limit:
        added = False
        for priority in priorities:
            missing = max(0, 5 - int(priority.get("unseen_available") or 0))
            if round_index >= missing or len(slots) >= limit:
                continue
            added = True
            slots.append({
                "slot_id": f"hep-dslot1-{len(slots) + 1:04d}",
                "family": priority["family"],
                "mechanism_id": priority["mechanism_id"],
                "detail_id": priority.get("detail_id"),
                "tense_id": priority.get("tense_id"),
                "generation_weight": priority["generation_weight"],
                "factors": {
                    name: priority[name] for name in (
                        "exam_factor", "personal_factor", "stock_gap", "spacing_factor"
                    )
                },
                "type": "single_blank_short_answer",
                "case_sensitive": True,
                "level": "bac",
                "constraints": {
                    "blank_count": 1,
                    "hide_rule_before_answer": True,
                    "accents_significant": True,
                },
            })
        if not added:
            break
        round_index += 1
    fingerprint = hashlib.sha256(json.dumps(slots, sort_keys=True).encode("utf-8")).hexdigest()
    return {
        "schema_version": "hep-drill-plan/1.0",
        "source_bridge_generated_at": bridge.get("generated_at"),
        "fingerprint": fingerprint,
        "slots": slots,
    }


def project_plan_context(plan: dict[str, Any]) -> dict[str, Any]:
    """Appelle la projection canonique HEP puis ne garde que les chemins du plan."""
    slots = plan.get("slots") or []
    families = list(dict.fromkeys(str(slot["family"]) for slot in slots))
    mechanisms = list(dict.fromkeys(str(slot["mechanism_id"]) for slot in slots))
    details = list(dict.fromkeys(
        f"{slot['mechanism_id']}={slot['detail_id']}"
        for slot in slots if slot.get("detail_id")
    ))
    tenses = list(dict.fromkeys(str(slot["tense_id"]) for slot in slots if slot.get("tense_id")))
    if not families:
        raise PipelineDrillError("Le plan ne contient aucun slot.")
    if str(ANALYSE_DIR) not in sys.path:
        sys.path.insert(0, str(ANALYSE_DIR))
    try:
        from pipeline_HEP import project_prompt_context
        rules, pedagogy = project_prompt_context(
            families, mechanisms=mechanisms, detail_pairs=details, tenses=tenses,
            mode="generation",
        )
    except Exception as exc:
        raise PipelineDrillError(f"Projection canonique impossible: {exc}") from exc
    compact_rules = {
        "_projection": rules.get("_projection"),
        "locale": rules.get("locale"),
        "families": (rules.get("taxonomie") or {}).get("familles", {}),
        "rule_cards": [
            {
                key: card[key]
                for key in ("rule_id", "nom", "objectif", "pieges", "a_eviter", "norme_stable_uniquement")
                if key in card
            }
            for card in rules.get("rules", [])
        ],
    }
    compact_pedagogy = {
        key: pedagogy.get(key)
        for key in ("_projection", "schema_version", "families", "tenses", "mechanisms")
    }
    return {
        "schema_version": "hep-drill-prompt-context/1.0",
        "plan_fingerprint": plan["fingerprint"],
        "rules": compact_rules,
        "pedagogy": compact_pedagogy,
    }


def _signature(text: str) -> str:
    folded = unicodedata.normalize("NFD", text.casefold())
    folded = "".join(character for character in folded if unicodedata.category(character) != "Mn")
    return " ".join(re.findall(r"[a-z0-9]+", folded.replace("___", " ")))


def _token_similarity(left: str, right: str) -> float:
    a, b = set(left.split()), set(right.split())
    return len(a & b) / len(a | b) if a | b else 0.0


def load_qcm_signatures(path: Path = QCM_SIGNATURES) -> list[dict[str, Any]]:
    return list((load_json(path).get("questions") or []))


def lint_drills(drills: Iterable[dict[str, Any]], qcm_signatures: Iterable[dict[str, Any]] = ()) -> dict[str, Any]:
    qcm = list(qcm_signatures)
    reports: list[dict[str, Any]] = []
    ids: set[str] = set()
    drill_signatures: dict[str, str] = {}
    for raw in drills:
        drill_id = str(raw.get("id") or "") if isinstance(raw, dict) else ""
        defects: list[str] = []
        try:
            drill = validate_drill(raw)
        except DrillContractError as exc:
            reports.append({"drill_id": drill_id, "status": "REJECT", "defects": [str(exc)]})
            continue
        if drill_id in ids:
            defects.append("ID_COLLISION")
        ids.add(drill_id)
        prompt_signature = _signature(drill["prompt"])
        if prompt_signature in drill_signatures:
            defects.append(f"DUPLICATE_DRILL:{drill_signatures[prompt_signature]}")
        drill_signatures[prompt_signature] = drill_id
        for question in qcm:
            existing = str(question.get("statement_signature") or "")
            if not existing:
                continue
            similarity = _token_similarity(prompt_signature, existing)
            if prompt_signature == existing:
                defects.append(f"DUPLICATE_QCM:{question.get('id')}")
                break
            if len(prompt_signature.split()) >= 6 and similarity >= 0.90:
                defects.append(f"SIGNATURE_NEAR_QCM:{question.get('id')}:{similarity:.2f}")
                break
        reconstructed = [drill["prompt"].replace("___", answer, 1) for answer in drill["accepted_answers"]]
        if any("___" in text for text in reconstructed):
            defects.append("RECOMPOSITION_FAILED")
        reports.append({
            "drill_id": drill_id,
            "status": "PASS" if not defects else "REVISE",
            "defects": defects,
            "reconstructed_sentences": reconstructed,
            "signature": prompt_signature,
        })
    return {
        "schema_version": "hep-drill-lint-report/1.0",
        "reports": reports,
        "summary": {
            "total": len(reports),
            "pass": sum(item["status"] == "PASS" for item in reports),
            "revise": sum(item["status"] == "REVISE" for item in reports),
            "reject": sum(item["status"] == "REJECT" for item in reports),
        },
    }


def check_drills_locally(drills: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Petit adaptateur autour des deux moteurs HEP; aucune suggestion appliquée."""
    if str(ANALYSE_DIR) not in sys.path:
        sys.path.insert(0, str(ANALYSE_DIR))
    try:
        from correcteurs_HEP import GrammalecteEngine, LanguageToolLocalEngine
    except Exception as exc:
        raise PipelineDrillError(f"Chargement des correcteurs HEP impossible: {exc}") from exc
    engines = [GrammalecteEngine(), LanguageToolLocalEngine()]
    probes = [engine.probe() for engine in engines]
    reports = []
    for drill in validate_drill_batch(drills):
        sentences = []
        for answer in drill["accepted_answers"]:
            text = drill["prompt"].replace("___", answer, 1)
            findings = []
            for engine, probe in zip(engines, probes):
                if probe.get("state") != "OK":
                    continue
                try:
                    findings.extend({"engine": engine.name, **item} for item in engine.check(text))
                except Exception as exc:
                    probe["state"] = "ERROR"
                    probe["detail"] = str(exc)
            sentences.append({"answer": answer, "text": text, "findings": findings})
        reports.append({"drill_id": drill["id"], "sentences": sentences})
    states = {probe.get("state") for probe in probes}
    state = "COMPLETE" if states == {"OK"} else ("UNAVAILABLE" if states == {"UNAVAILABLE"} else "PARTIAL")
    return {
        "schema_version": "hep-drill-checker-report/1.0",
        "mode": "REPORT_ONLY", "state": state, "engines": probes, "reports": reports,
        "limitation": "L'absence d'alerte ne valide ni le sens, ni l'unicité de la réponse.",
    }


def _publish_bank(drills: Iterable[dict[str, Any]], target: Path, header: str) -> dict[str, Any]:
    resolved = target.resolve()
    validated = validate_drill_batch(drills)
    compact = json.dumps(validated, ensure_ascii=False, separators=(",", ":"))
    digest = hashlib.sha256(compact.encode("utf-8")).hexdigest()[:8]
    release = f"drills-{date.today():%Y%m%d}-{digest}"
    payload = (
        f"// {header}\n"
        f"window.HEP_DRILL_BANK = {{release: {json.dumps(release)}, drills: {compact}}};\n"
        "if (typeof module !== 'undefined') module.exports = window.HEP_DRILL_BANK;\n"
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
    return {"target": str(resolved), "release": release, "drills": len(validated)}


def publish_test_bank(drills: Iterable[dict[str, Any]], target: Path) -> dict[str, Any]:
    if target.resolve() == CANONICAL_DRILL_BANK.resolve():
        raise PipelineDrillError("La banque canonique exige la validation utilisateur de la partie 07.")
    return _publish_bank(drills, target, "Artefact de test généré ; ne pas intégrer comme source canonique.")


def publish_canonical_bank(drills: Iterable[dict[str, Any]], confirmed: bool = False) -> dict[str, Any]:
    if not confirmed:
        raise PipelineDrillError("La publication canonique exige --confirm-pilot après validation utilisateur explicite.")
    return _publish_bank(drills, CANONICAL_DRILL_BANK, "Banque canonique des drills validés.")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)
    imported = commands.add_parser("import-feedback")
    imported.add_argument("inputs", nargs="+", type=Path)
    imported.add_argument("--store", type=Path, default=DEFAULT_STORE)
    bridge = commands.add_parser("bridge")
    bridge.add_argument("output", type=Path)
    bridge.add_argument("--bank-json", type=Path)
    plan = commands.add_parser("plan")
    plan.add_argument("bridge", type=Path)
    plan.add_argument("output", type=Path)
    plan.add_argument("--limit", type=int, default=20)
    projection = commands.add_parser("project-context")
    projection.add_argument("plan", type=Path)
    projection.add_argument("output", type=Path)
    lint = commands.add_parser("lint")
    lint.add_argument("candidates", type=Path)
    lint.add_argument("output", type=Path)
    check = commands.add_parser("check-local")
    check.add_argument("candidates", type=Path)
    check.add_argument("output", type=Path)
    publish = commands.add_parser("publish-test")
    publish.add_argument("candidates", type=Path)
    publish.add_argument("target", type=Path)
    canonical = commands.add_parser("publish-canonical")
    canonical.add_argument("candidates", type=Path)
    canonical.add_argument("--confirm-pilot", action="store_true")
    return root


def main() -> None:
    args = parser().parse_args()
    try:
        if args.command == "import-feedback":
            sessions = []
            for path in args.inputs:
                sessions.extend(_items(load_json(path), "sessions"))
            result = import_sessions(sessions, args.store)
        elif args.command == "bridge":
            bank = _items(load_json(args.bank_json), "drills") if args.bank_json else []
            result = build_current_bridge(bank)
            _write_json(args.output, result)
        elif args.command == "plan":
            result = plan_slots(load_json(args.bridge), limit=args.limit)
            _write_json(args.output, result)
        elif args.command == "project-context":
            result = project_plan_context(load_json(args.plan))
            _write_json(args.output, result)
        elif args.command == "lint":
            candidates = _items(load_json(args.candidates), "drills", "candidates")
            result = lint_drills(candidates, load_qcm_signatures())
            _write_json(args.output, result)
        elif args.command == "check-local":
            candidates = _items(load_json(args.candidates), "drills", "candidates")
            result = check_drills_locally(candidates)
            _write_json(args.output, result)
        elif args.command == "publish-test":
            candidates = _items(load_json(args.candidates), "drills", "candidates")
            result = publish_test_bank(candidates, args.target)
        else:
            candidates = _items(load_json(args.candidates), "drills", "candidates")
            result = publish_canonical_bank(candidates, confirmed=args.confirm_pilot)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (BridgeError, DrillContractError, PipelineDrillError) as exc:
        raise SystemExit(f"ERREUR: {exc}") from exc


if __name__ == "__main__":
    main()
