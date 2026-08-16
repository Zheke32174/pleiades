#!/usr/bin/env python3
"""Validate MODOS ontology-revision proposals.

This validator does not decide whether a proposed concept is true or useful.
It proves that ontology mutation remains revision-aware, plural, reversible,
and evidence-gated.

Research assimilated:
- distributed ontology change management and layered change logs;
- axiom weakening before deletion;
- Task-Method-Knowledge metacognitive diagnosis;
- hermeneutical-gap and boundary-object handling;
- semantic uncertainty and cross-model disagreement;
- reasoning-alignment audits for apparent consensus.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator, FormatChecker


NON_DESTRUCTIVE_OPERATIONS = {
    "add-distinction",
    "split-concept",
    "weaken-axiom",
    "scope-concept",
    "add-boundary-object",
    "add-concept-sense",
    "revise-relation",
}
GAP_RECOVERY_OPERATIONS = {
    "add-distinction",
    "split-concept",
    "add-boundary-object",
    "add-concept-sense",
}
STATUS_TO_DECISION = {
    "approved": "approve",
    "rejected": "reject",
    "experimental": "experiment",
}


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def duplicate_values(values: Iterable[str]) -> list[str]:
    counts = Counter(values)
    return sorted(value for value, count in counts.items() if count > 1)


def schema_errors(instance: Any, schema: dict[str, Any]) -> list[str]:
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    rows = sorted(validator.iter_errors(instance), key=lambda error: list(error.path))
    errors: list[str] = []
    for error in rows:
        location = "/".join(str(part) for part in error.absolute_path) or "<root>"
        errors.append(f"proposal schema {location}: {error.message}")
    return errors


def validate_semantics(proposal: dict[str, Any]) -> tuple[list[str], list[str], dict[str, Any]]:
    errors: list[str] = []
    warnings: list[str] = []

    metadata = proposal["metadata"]
    spec = proposal["spec"]
    trigger = spec["trigger"]
    diagnosis = spec["diagnosis"]
    change = spec["change"]
    plurality = spec["plurality"]
    alternatives = spec["alternatives"]
    obligations = spec["proofObligations"]
    review = spec["review"]

    residual_ids = [row["id"] for row in trigger["observedResiduals"]]
    duplicates = duplicate_values(residual_ids)
    if duplicates:
        errors.append("duplicate observed residual ids: " + ", ".join(duplicates))

    result_ids = [row["id"] for row in change["resultingConcepts"]]
    duplicates = duplicate_values(result_ids)
    if duplicates:
        errors.append("duplicate resulting concept ids: " + ", ".join(duplicates))

    viewpoint_ids = [row["viewpointId"] for row in plurality["localInterpretations"]]
    duplicates = duplicate_values(viewpoint_ids)
    if duplicates:
        errors.append("duplicate viewpoint ids: " + ", ".join(duplicates))

    alternative_ids = [row["id"] for row in alternatives]
    duplicates = duplicate_values(alternative_ids)
    if duplicates:
        errors.append("duplicate alternative ids: " + ", ".join(duplicates))

    operation = change["operation"]
    hermeneutical_gap = diagnosis["hermeneuticalGap"]

    if hermeneutical_gap:
        if len(trigger["observedResiduals"]) < 2:
            errors.append(
                "hermeneutical-gap diagnosis requires at least two recurring residual cases"
            )
        if operation not in GAP_RECOVERY_OPERATIONS:
            errors.append(
                "hermeneutical-gap diagnosis must propose a concept-forming or boundary-forming operation"
            )
        if not diagnosis.get("falseBinary") and len(change["resultingConcepts"]) < 2:
            errors.append(
                "hermeneutical-gap diagnosis requires a falseBinary record or at least two resulting concepts"
            )
        if "vocabulary" not in diagnosis["failureLayers"]:
            warnings.append(
                "hermeneutical-gap diagnosis does not name vocabulary as a failure layer"
            )

    if operation == "add-distinction" and len(change["resultingConcepts"]) < 2:
        errors.append("add-distinction requires at least two resulting concepts")

    if operation == "split-concept" and len(change["resultingConcepts"]) < 2:
        errors.append("split-concept requires at least two resulting concepts")

    if operation == "add-concept-sense" and not change["resultingConcepts"]:
        errors.append("add-concept-sense requires at least one resulting concept")

    if operation == "add-boundary-object":
        if not plurality.get("sharedCore", "").strip():
            errors.append("add-boundary-object requires a non-empty sharedCore")
        if len(plurality["localInterpretations"]) < 2:
            errors.append("add-boundary-object requires at least two local interpretations")
        if not plurality["translationRules"]:
            errors.append("add-boundary-object requires at least one translation rule")

    known_viewpoints = set(viewpoint_ids)
    for index, rule in enumerate(plurality["translationRules"]):
        if rule["fromViewpoint"] not in known_viewpoints:
            errors.append(
                f"translationRules[{index}] has unknown fromViewpoint: {rule['fromViewpoint']}"
            )
        if rule["toViewpoint"] not in known_viewpoints:
            errors.append(
                f"translationRules[{index}] has unknown toViewpoint: {rule['toViewpoint']}"
            )
        if rule["fromViewpoint"] == rule["toViewpoint"]:
            errors.append(f"translationRules[{index}] translates a viewpoint into itself")

    if operation == "deprecate-concept":
        non_destructive_alternatives = [
            row for row in alternatives
            if row["operation"] in NON_DESTRUCTIVE_OPERATIONS
            and row["status"] in {"active", "rejected", "deferred"}
        ]
        if not non_destructive_alternatives:
            errors.append(
                "deprecate-concept requires a documented weakening, scoping, splitting, "
                "sense-addition, relation-revision, or boundary-object alternative"
            )
        if not change["deprecatesRefs"]:
            errors.append("deprecate-concept names no concept to deprecate")

    if change["deprecatesRefs"] and operation != "deprecate-concept":
        warnings.append(
            "proposal deprecates concepts even though its primary operation is not deprecate-concept"
        )

    if not alternatives:
        errors.append("proposal records no alternative ontology change")

    active_or_deferred = [
        row for row in alternatives if row["status"] in {"active", "deferred"}
    ]
    if not active_or_deferred:
        warnings.append(
            "all alternatives are rejected; the proposal may be prematurely converged"
        )

    if not obligations["independentFirstPass"]:
        warnings.append(
            "independent first-pass reasoning is disabled; debate may amplify anchoring"
        )
    if not obligations["dissentRetention"]:
        errors.append("dissentRetention must remain true")

    if not all(question.rstrip().endswith("?") for question in obligations["competencyQuestions"]):
        warnings.append("one or more competency questions lack a trailing '?'")

    metrics = trigger.get("metrics", {})
    answer_agreement = metrics.get("answerAgreement")
    reasoning_alignment = metrics.get("reasoningAlignment")
    semantic_entropy = metrics.get("semanticEntropy")
    inter_model = metrics.get("interModelDisagreement")
    intra_model = metrics.get("intraModelVariation")

    consistency_illusion = (
        answer_agreement is not None
        and reasoning_alignment is not None
        and answer_agreement >= 0.8
        and reasoning_alignment < 0.5
    )
    if consistency_illusion:
        warnings.append(
            "high answer agreement coexists with low reasoning alignment: possible consistency illusion"
        )
        if not obligations.get("consistencyIllusionMitigation", "").strip():
            errors.append(
                "consistency-illusion signal requires an explicit mitigation"
            )
        if "coordination" not in diagnosis["failureLayers"] and "method" not in diagnosis["failureLayers"]:
            errors.append(
                "consistency-illusion signal requires coordination or method in failureLayers"
            )

    if trigger["kind"] == "semantic-uncertainty" and semantic_entropy is None:
        errors.append("semantic-uncertainty trigger requires metrics.semanticEntropy")

    if trigger["kind"] == "cross-model-disagreement" and inter_model is None:
        errors.append(
            "cross-model-disagreement trigger requires metrics.interModelDisagreement"
        )

    if trigger["kind"] == "reasoning-misalignment":
        if answer_agreement is None or reasoning_alignment is None:
            errors.append(
                "reasoning-misalignment trigger requires answerAgreement and reasoningAlignment"
            )

    if (
        inter_model is not None
        and intra_model is not None
        and inter_model > intra_model + 0.25
    ):
        warnings.append(
            "cross-model disagreement substantially exceeds within-model variation; "
            "treat this as epistemic uncertainty rather than mere sampling noise"
        )

    expected_decision = STATUS_TO_DECISION.get(metadata["status"])
    if expected_decision and review["decision"] != expected_decision:
        errors.append(
            f"metadata status {metadata['status']} requires review decision {expected_decision}"
        )
    if metadata["status"] in {"candidate", "contested", "superseded"} and review["decision"] == "approve":
        errors.append(
            f"metadata status {metadata['status']} cannot carry an approving review decision"
        )

    promoted = metadata["status"] == "approved"
    if promoted:
        if not obligations["independentFirstPass"]:
            errors.append("approved proposal requires independentFirstPass=true")
        source_groups = review["evidenceSourceGroups"]
        if len(source_groups) < obligations["minimumIndependentSourceGroups"]:
            errors.append(
                "approved proposal has fewer independent evidence source groups than required "
                f"({len(source_groups)} < {obligations['minimumIndependentSourceGroups']})"
            )
        if not review["argumentRefs"]:
            errors.append("approved proposal records no supporting or dissenting arguments")
        if not review.get("decidedBy") or not review.get("decidedAt"):
            errors.append("approved proposal requires decidedBy and decidedAt")
        if consistency_illusion and not obligations.get("consistencyIllusionMitigation", "").strip():
            errors.append(
                "approved proposal may not ignore high-consensus/low-alignment reasoning"
            )

    if review["decision"] in {"approve", "reject", "experiment"}:
        if not review.get("decidedBy") or not review.get("decidedAt"):
            errors.append(
                f"review decision {review['decision']} requires decidedBy and decidedAt"
            )

    if metadata["status"] == "experimental" and not metadata.get("branchRef"):
        errors.append("experimental proposal requires a branchRef")

    report = {
        "proposal": metadata["id"],
        "status": metadata["status"],
        "operation": operation,
        "triggerKind": trigger["kind"],
        "residualCount": len(trigger["observedResiduals"]),
        "resultingConceptCount": len(change["resultingConcepts"]),
        "viewpointCount": len(plurality["localInterpretations"]),
        "translationRuleCount": len(plurality["translationRules"]),
        "alternativeCount": len(alternatives),
        "sourceGroupCount": len(review["evidenceSourceGroups"]),
        "hermeneuticalGap": hermeneutical_gap,
        "consistencyIllusionSignal": consistency_illusion,
    }
    return errors, warnings, report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--proposal", type=Path, required=True)
    parser.add_argument("--schema", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    proposal = load_json(args.proposal)
    schema = load_json(args.schema)

    errors = schema_errors(proposal, schema)
    warnings: list[str] = []
    report: dict[str, Any]

    if not errors:
        semantic_errors, semantic_warnings, semantic_report = validate_semantics(proposal)
        errors.extend(semantic_errors)
        warnings.extend(semantic_warnings)
        report = {
            "valid": not errors,
            "proposal": semantic_report,
            "warningCount": len(warnings),
            "errorCount": len(errors),
        }
    else:
        report = {
            "valid": False,
            "warningCount": 0,
            "errorCount": len(errors),
        }

    for warning in warnings:
        print(f"WARNING: {warning}", file=sys.stderr)
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    if errors:
        return 1

    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
