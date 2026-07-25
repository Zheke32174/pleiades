#!/usr/bin/env python3
"""Deterministic administrative judgment and runtime-assurance gate.

This layer sits after policy classification, recurrent Mind deliberation, and
transition trust preflight. It adds explicit assumption closure, calibrated
abstention, bitemporal validity, and Simplex-style runtime takeover before a
mandate may be constructed. It never constructs or executes a mandate, changes
policy, mutates authority, or broadens its own scope.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

API_VERSION = "modos.pleiades/v1alpha1"
RFC3339_PATTERN = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})T"
    r"(?P<time>\d{2}:\d{2}:\d{2})"
    r"(?P<fraction>\.\d+)?"
    r"(?P<offset>Z|[+-]\d{2}:\d{2})$"
)


class JudgmentError(ValueError):
    pass


def _reject_float(value: str) -> None:
    raise JudgmentError(f"floating-point values are forbidden: {value}")


def _reject_constant(value: str) -> None:
    raise JudgmentError(f"non-finite JSON constant is forbidden: {value}")


def _pairs(items: Iterable[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in items:
        if key in result:
            raise JudgmentError(f"duplicate JSON key is forbidden: {key}")
        result[key] = value
    return result


def load_json_strict(path: Path) -> Any:
    return json.loads(
        path.read_text(encoding="utf-8"),
        parse_float=_reject_float,
        parse_constant=_reject_constant,
        object_pairs_hook=_pairs,
    )


def _assert_no_floats(value: Any, location: str = "$") -> None:
    if isinstance(value, float):
        raise JudgmentError(f"floating-point values are forbidden at {location}")
    if isinstance(value, dict):
        for key, child in value.items():
            _assert_no_floats(child, f"{location}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_no_floats(child, f"{location}[{index}]")


def canonical_bytes(value: Any) -> bytes:
    _assert_no_floats(value)
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_bytes(value)).hexdigest()


def _sha(value: Any, field: str) -> str:
    if not isinstance(value, str) or len(value) != 71 or not value.startswith("sha256:"):
        raise JudgmentError(f"{field} must be sha256-bound")
    if any(ch not in "0123456789abcdef" for ch in value[7:]):
        raise JudgmentError(f"{field} must use lowercase hexadecimal")
    return value


def _time(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or RFC3339_PATTERN.fullmatch(value) is None:
        raise JudgmentError(f"{field} must be an RFC3339 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise JudgmentError(f"{field} must be an RFC3339 timestamp") from exc
    offset = parsed.utcoffset()
    if offset is None or not (-24 * 60 < offset.total_seconds() / 60 < 24 * 60):
        raise JudgmentError(f"{field} must use a valid RFC3339 timezone offset")
    return parsed


def _bps(value: Any, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 10000:
        raise JudgmentError(f"{field} must be an integer from 0 through 10000")
    return value


def _bounded_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value or value == "*" or "*" in value:
        raise JudgmentError(f"{field} must be a bounded non-wildcard string")
    return value


def _validate_upstream(
    case: dict[str, Any],
    policy_receipt: dict[str, Any],
    workspace_receipt: dict[str, Any],
    preflight_receipt: dict[str, Any],
) -> None:
    if policy_receipt.get("apiVersion") != API_VERSION or policy_receipt.get("kind") != "PolicyDecisionReceipt":
        raise JudgmentError("unsupported policy decision receipt")
    if workspace_receipt.get("apiVersion") != API_VERSION or workspace_receipt.get("kind") != "WorkspaceDeliberationReceipt":
        raise JudgmentError("unsupported workspace deliberation receipt")
    if preflight_receipt.get("apiVersion") != API_VERSION or preflight_receipt.get("kind") != "TransitionPreflightReceipt":
        raise JudgmentError("unsupported transition preflight receipt")
    if workspace_receipt.get("mindId") != case.get("mindId"):
        raise JudgmentError("workspace mindId does not match the judgment case")
    bindings = case.get("bindings")
    if not isinstance(bindings, dict):
        raise JudgmentError("judgment bindings are required")
    expected = {
        "policyReceiptDigest": digest(policy_receipt),
        "workspaceReceiptDigest": digest(workspace_receipt),
        "transitionPreflightReceiptDigest": digest(preflight_receipt),
    }
    for field, value in expected.items():
        if bindings.get(field) != value:
            raise JudgmentError(f"{field} mismatch")
    for field in ("proposalDigest", "atlasBeliefDigest", "forgeStateDigest", "evidenceSetDigest"):
        _sha(bindings.get(field), f"bindings.{field}")
    workspace_bindings = workspace_receipt.get("bindings", {})
    if workspace_bindings.get("proposalDigest") != bindings["proposalDigest"]:
        raise JudgmentError("workspace proposal digest does not match the judgment case")
    if workspace_bindings.get("atlasBeliefDigest") != bindings["atlasBeliefDigest"]:
        raise JudgmentError("workspace Atlas digest does not match the judgment case")
    if workspace_bindings.get("forgeStateDigest") != bindings["forgeStateDigest"]:
        raise JudgmentError("workspace Forge digest does not match the judgment case")
    if workspace_bindings.get("policyReceiptDigest") != bindings["policyReceiptDigest"]:
        raise JudgmentError("workspace policy digest does not match the judgment case")
    decision = preflight_receipt.get("decision", {})
    if decision.get("domain") != case.get("domain") or decision.get("action") != case.get("action"):
        raise JudgmentError("preflight decision scope does not match the judgment case")
    if policy_receipt.get("classification", {}).get("riskTier") != decision.get("riskTier"):
        raise JudgmentError("policy and preflight risk tiers disagree")


def _assumption_closure(case: dict[str, Any], evaluated_at: datetime) -> dict[str, Any]:
    assumptions = case.get("assumptions")
    if not isinstance(assumptions, list) or not assumptions:
        raise JudgmentError("assumptions must be nonempty")
    by_id: dict[str, dict[str, Any]] = {}
    for row in assumptions:
        assumption_id = _bounded_text(row.get("assumptionId"), "assumptionId")
        if assumption_id in by_id:
            raise JudgmentError(f"duplicate assumptionId: {assumption_id}")
        status = row.get("status")
        if status not in {"active", "defeated", "unknown"}:
            raise JudgmentError(f"{assumption_id} status is unsupported")
        depends = row.get("dependsOn")
        if not isinstance(depends, list) or len(set(depends)) != len(depends):
            raise JudgmentError(f"{assumption_id} dependsOn must be unique")
        refs = row.get("evidenceRefs")
        if not isinstance(refs, list) or not refs or len(set(refs)) != len(refs):
            raise JudgmentError(f"{assumption_id} evidenceRefs must be nonempty and unique")
        for ref in refs:
            _bounded_text(ref, f"{assumption_id}.evidenceRefs")
        _bps(row.get("confidenceBps"), f"{assumption_id}.confidenceBps")
        valid_from = _time(row.get("validFrom"), f"{assumption_id}.validFrom")
        valid_until = _time(row.get("validUntil"), f"{assumption_id}.validUntil")
        _time(row.get("recordedAt"), f"{assumption_id}.recordedAt")
        if valid_from >= valid_until:
            raise JudgmentError(f"{assumption_id} valid-time interval is empty")
        by_id[assumption_id] = row

    for assumption_id, row in by_id.items():
        for dependency in row["dependsOn"]:
            if dependency not in by_id:
                raise JudgmentError(f"{assumption_id} depends on unknown assumption {dependency}")

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> None:
        if node in visiting:
            raise JudgmentError(f"assumption dependency cycle detected at {node}")
        if node in visited:
            return
        visiting.add(node)
        for dependency in by_id[node]["dependsOn"]:
            visit(dependency)
        visiting.remove(node)
        visited.add(node)

    for assumption_id in sorted(by_id):
        visit(assumption_id)

    required = case.get("requiredAssumptionRefs")
    if not isinstance(required, list) or not required or len(set(required)) != len(required):
        raise JudgmentError("requiredAssumptionRefs must be nonempty and unique")
    for assumption_id in required:
        if assumption_id not in by_id:
            raise JudgmentError(f"required assumption is unknown: {assumption_id}")

    closure: set[str] = set()

    def collect(node: str) -> None:
        if node in closure:
            return
        closure.add(node)
        for dependency in by_id[node]["dependsOn"]:
            collect(dependency)

    for assumption_id in required:
        collect(assumption_id)

    blockers: list[str] = []
    retracted: list[str] = []
    normalized: list[dict[str, Any]] = []
    for assumption_id in sorted(closure):
        row = by_id[assumption_id]
        valid_from = _time(row["validFrom"], f"{assumption_id}.validFrom")
        valid_until = _time(row["validUntil"], f"{assumption_id}.validUntil")
        recorded_at = _time(row["recordedAt"], f"{assumption_id}.recordedAt")
        current = valid_from <= evaluated_at < valid_until and recorded_at <= evaluated_at
        if row["status"] == "defeated":
            blockers.append(f"assumption-defeated:{assumption_id}")
            retracted.append(assumption_id)
        elif row["status"] == "unknown":
            blockers.append(f"assumption-unknown:{assumption_id}")
            retracted.append(assumption_id)
        if not current:
            blockers.append(f"assumption-not-current:{assumption_id}")
            retracted.append(assumption_id)
        normalized.append(
            {
                "assumptionId": assumption_id,
                "status": row["status"],
                "dependsOn": sorted(row["dependsOn"]),
                "confidenceBps": row["confidenceBps"],
                "currentAtEvaluation": current,
                "contentDigest": _sha(row.get("contentDigest"), f"{assumption_id}.contentDigest"),
            }
        )

    triggered: list[str] = []
    nogoods = case.get("nogoods", [])
    if not isinstance(nogoods, list):
        raise JudgmentError("nogoods must be an array")
    nogood_ids: set[str] = set()
    for row in nogoods:
        nogood_id = _bounded_text(row.get("nogoodId"), "nogoodId")
        if nogood_id in nogood_ids:
            raise JudgmentError(f"duplicate nogoodId: {nogood_id}")
        nogood_ids.add(nogood_id)
        refs = row.get("assumptionRefs")
        if not isinstance(refs, list) or len(refs) < 2 or len(set(refs)) != len(refs):
            raise JudgmentError(f"{nogood_id} assumptionRefs must contain at least two unique assumptions")
        if any(ref not in by_id for ref in refs):
            raise JudgmentError(f"{nogood_id} references an unknown assumption")
        active_refs = {
            ref
            for ref in refs
            if ref in closure and by_id[ref]["status"] == "active"
        }
        if set(refs).issubset(active_refs):
            triggered.append(nogood_id)
            blockers.append(f"nogood-triggered:{nogood_id}")

    return {
        "requiredRefs": sorted(required),
        "closure": normalized,
        "retractedRefs": sorted(set(retracted)),
        "triggeredNogoods": sorted(triggered),
        "blockers": sorted(set(blockers)),
    }


def _risk_gate(case: dict[str, Any], evaluated_at: datetime) -> dict[str, Any]:
    budget = case.get("riskBudget")
    certificate = case.get("riskCertificate")
    if not isinstance(budget, dict) or not isinstance(certificate, dict):
        raise JudgmentError("riskBudget and riskCertificate are required")
    maximum_risk = _bps(budget.get("maximumSelectiveRiskBps"), "riskBudget.maximumSelectiveRiskBps")
    minimum_coverage = _bps(budget.get("minimumCoverageBps"), "riskBudget.minimumCoverageBps")
    maximum_calibration_error = _bps(budget.get("maximumCalibrationErrorBps"), "riskBudget.maximumCalibrationErrorBps")
    maximum_shift = _bps(budget.get("maximumDistributionShiftBps"), "riskBudget.maximumDistributionShiftBps")
    minimum_samples = budget.get("minimumCalibrationSamples")
    if not isinstance(minimum_samples, int) or isinstance(minimum_samples, bool) or minimum_samples < 1:
        raise JudgmentError("riskBudget.minimumCalibrationSamples must be positive")

    method = certificate.get("method")
    if method not in {"conformal-risk-control", "selective-risk-holdout", "calibrated-threshold"}:
        raise JudgmentError("risk certificate method is unsupported")
    _bounded_text(certificate.get("certificateId"), "riskCertificate.certificateId")
    sample_size = certificate.get("sampleSize")
    if not isinstance(sample_size, int) or isinstance(sample_size, bool) or sample_size < 1:
        raise JudgmentError("riskCertificate.sampleSize must be positive")
    coverage = _bps(certificate.get("coverageBps"), "riskCertificate.coverageBps")
    upper_risk = _bps(certificate.get("riskUpperBoundBps"), "riskCertificate.riskUpperBoundBps")
    calibration_error = _bps(certificate.get("expectedCalibrationErrorBps"), "riskCertificate.expectedCalibrationErrorBps")
    shift = _bps(certificate.get("distributionShiftBps"), "riskCertificate.distributionShiftBps")
    _bps(certificate.get("scoreThresholdBps"), "riskCertificate.scoreThresholdBps")
    generated = _time(certificate.get("generatedAt"), "riskCertificate.generatedAt")
    valid_until = _time(certificate.get("validUntil"), "riskCertificate.validUntil")
    if generated >= valid_until:
        raise JudgmentError("risk certificate validity interval is empty")
    _sha(certificate.get("evidenceDigest"), "riskCertificate.evidenceDigest")

    blockers: list[str] = []
    if sample_size < minimum_samples:
        blockers.append("calibration-sample-below-minimum")
    if coverage < minimum_coverage:
        blockers.append("coverage-below-minimum")
    if upper_risk > maximum_risk:
        blockers.append("selective-risk-above-budget")
    if calibration_error > maximum_calibration_error:
        blockers.append("calibration-error-above-budget")
    if shift > maximum_shift:
        blockers.append("distribution-shift-above-budget")
    if not generated <= evaluated_at < valid_until:
        blockers.append("risk-certificate-not-current")
    return {
        "method": method,
        "sampleSize": sample_size,
        "coverageBps": coverage,
        "riskUpperBoundBps": upper_risk,
        "expectedCalibrationErrorBps": calibration_error,
        "distributionShiftBps": shift,
        "blockers": sorted(blockers),
    }


def _runtime_gate(case: dict[str, Any], evaluated_at: datetime) -> dict[str, Any]:
    runtime = case.get("runtimeAssurance")
    if not isinstance(runtime, dict):
        raise JudgmentError("runtimeAssurance is required")
    monitor = _bounded_text(runtime.get("monitorPrincipal"), "runtimeAssurance.monitorPrincipal")
    fallback = _bounded_text(runtime.get("fallbackController"), "runtimeAssurance.fallbackController")
    independent = runtime.get("monitorIndependent")
    fallback_ready = runtime.get("fallbackReady")
    if not isinstance(independent, bool) or not isinstance(fallback_ready, bool):
        raise JudgmentError("runtime monitor independence and fallback readiness must be boolean")
    hazard = _bps(runtime.get("hazardScoreBps"), "runtimeAssurance.hazardScoreBps")
    threshold = _bps(runtime.get("takeoverThresholdBps"), "runtimeAssurance.takeoverThresholdBps")
    issued = _time(runtime.get("issuedAt"), "runtimeAssurance.issuedAt")
    valid_until = _time(runtime.get("validUntil"), "runtimeAssurance.validUntil")
    if issued >= valid_until:
        raise JudgmentError("runtime assurance validity interval is empty")
    invariants = runtime.get("invariants")
    if not isinstance(invariants, list) or not invariants:
        raise JudgmentError("runtime invariants must be nonempty")
    blockers: list[str] = []
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in invariants:
        invariant_id = _bounded_text(row.get("invariantId"), "runtime invariantId")
        if invariant_id in seen:
            raise JudgmentError(f"duplicate runtime invariant: {invariant_id}")
        seen.add(invariant_id)
        status = row.get("status")
        if status not in {"pass", "fail"}:
            raise JudgmentError(f"runtime invariant {invariant_id} status is unsupported")
        evidence_digest = _sha(row.get("evidenceDigest"), f"runtime invariant {invariant_id}.evidenceDigest")
        normalized.append({"invariantId": invariant_id, "status": status, "evidenceDigest": evidence_digest})
        if status == "fail":
            blockers.append(f"runtime-invariant-failed:{invariant_id}")
    if not independent:
        blockers.append("runtime-monitor-not-independent")
    if not fallback_ready:
        blockers.append("runtime-fallback-not-ready")
    if not issued <= evaluated_at < valid_until:
        blockers.append("runtime-assurance-not-current")
    if hazard >= threshold:
        blockers.append("runtime-takeover-threshold-breached")
    return {
        "monitorPrincipal": monitor,
        "fallbackController": fallback,
        "hazardScoreBps": hazard,
        "takeoverThresholdBps": threshold,
        "invariants": sorted(normalized, key=lambda item: item["invariantId"]),
        "blockers": sorted(blockers),
    }


def evaluate_judgment(
    case: dict[str, Any],
    policy_receipt: dict[str, Any],
    workspace_receipt: dict[str, Any],
    preflight_receipt: dict[str, Any],
) -> dict[str, Any]:
    if case.get("apiVersion") != API_VERSION or case.get("kind") != "AdministrativeJudgmentCase":
        raise JudgmentError("unsupported administrative judgment case")
    _assert_no_floats(case)
    _bounded_text(case.get("judgmentId"), "judgmentId")
    _bounded_text(case.get("mindId"), "mindId")
    _bounded_text(case.get("domain"), "domain")
    _bounded_text(case.get("action"), "action")
    evaluated_at = _time(case.get("evaluatedAt"), "evaluatedAt")
    _validate_upstream(case, policy_receipt, workspace_receipt, preflight_receipt)

    transaction = case.get("transactionTime")
    world = case.get("worldTime")
    if not isinstance(transaction, dict) or not isinstance(world, dict):
        raise JudgmentError("worldTime and transactionTime are required")
    world_valid_from = _time(world.get("validFrom"), "worldTime.validFrom")
    world_valid_until = _time(world.get("validUntil"), "worldTime.validUntil")
    evidence_cutoff = _time(world.get("evidenceKnowledgeCutoff"), "worldTime.evidenceKnowledgeCutoff")
    recorded_at = _time(transaction.get("recordedAt"), "transactionTime.recordedAt")
    expires_at = _time(transaction.get("decisionExpiresAt"), "transactionTime.decisionExpiresAt")
    if world_valid_from >= world_valid_until or not world_valid_from <= evaluated_at < world_valid_until:
        raise JudgmentError("evaluatedAt must be inside world valid time")
    if evidence_cutoff > evaluated_at:
        raise JudgmentError("evidence knowledge cutoff cannot be in the future")
    if recorded_at > evaluated_at:
        raise JudgmentError("transaction time cannot be in the future")
    if expires_at <= evaluated_at:
        raise JudgmentError("decision expiry must be after evaluation")
    supersedes = transaction.get("supersedesReceiptDigest")
    if supersedes is not None:
        _sha(supersedes, "transactionTime.supersedesReceiptDigest")

    assumption_state = _assumption_closure(case, evaluated_at)
    risk_state = _risk_gate(case, evaluated_at)
    runtime_state = _runtime_gate(case, evaluated_at)

    upstream_blockers: list[str] = []
    if policy_receipt.get("decision") != "allow":
        upstream_blockers.append("policy-decision-not-allow")
    if workspace_receipt.get("outcome") != "approve":
        upstream_blockers.append("workspace-deliberation-not-approve")
    if preflight_receipt.get("status") != "eligible":
        upstream_blockers.append("transition-preflight-not-eligible")

    if runtime_state["blockers"]:
        disposition = "fallback-only"
    elif upstream_blockers:
        disposition = "reject"
    elif assumption_state["blockers"]:
        disposition = "defer"
    elif risk_state["blockers"]:
        disposition = "abstain"
    else:
        disposition = "approve"

    blockers = sorted(
        set(
            upstream_blockers
            + assumption_state["blockers"]
            + risk_state["blockers"]
            + runtime_state["blockers"]
        )
    )
    status = "eligible-for-mandate-construction" if disposition == "approve" else "ineligible"
    bindings = case["bindings"]
    receipt = {
        "apiVersion": API_VERSION,
        "kind": "AdministrativeJudgmentReceipt",
        "judgmentId": case["judgmentId"],
        "mindId": case["mindId"],
        "domain": case["domain"],
        "action": case["action"],
        "status": status,
        "disposition": disposition,
        "bindings": {
            "caseDigest": digest(case),
            "policyReceiptDigest": bindings["policyReceiptDigest"],
            "workspaceReceiptDigest": bindings["workspaceReceiptDigest"],
            "transitionPreflightReceiptDigest": bindings["transitionPreflightReceiptDigest"],
            "proposalDigest": bindings["proposalDigest"],
            "atlasBeliefDigest": bindings["atlasBeliefDigest"],
            "forgeStateDigest": bindings["forgeStateDigest"],
            "evidenceSetDigest": bindings["evidenceSetDigest"],
        },
        "assumptionState": assumption_state,
        "riskState": risk_state,
        "runtimeState": runtime_state,
        "bitemporal": {
            "worldValidFrom": world["validFrom"],
            "worldValidUntil": world["validUntil"],
            "evidenceKnowledgeCutoff": world["evidenceKnowledgeCutoff"],
            "evaluatedAt": case["evaluatedAt"],
            "recordedAt": transaction["recordedAt"],
            "decisionExpiresAt": transaction["decisionExpiresAt"],
            "supersedesReceiptDigest": supersedes,
        },
        "authority": {
            "operatorApprovalRequiredForThisJudgment": False,
            "mandateConstructionEligible": disposition == "approve",
            "mandateConstructed": False,
            "executionApplied": False,
            "fallbackTakeoverRequired": disposition == "fallback-only",
            "authorityExpanded": False,
            "reservedPowerExercised": False,
        },
        "blockers": blockers,
    }
    receipt["receiptDigest"] = digest(receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", type=Path, required=True)
    parser.add_argument("--policy-receipt", type=Path, required=True)
    parser.add_argument("--workspace-receipt", type=Path, required=True)
    parser.add_argument("--preflight-receipt", type=Path, required=True)
    args = parser.parse_args()
    try:
        receipt = evaluate_judgment(
            load_json_strict(args.case),
            load_json_strict(args.policy_receipt),
            load_json_strict(args.workspace_receipt),
            load_json_strict(args.preflight_receipt),
        )
    except (JudgmentError, OSError, json.JSONDecodeError) as exc:
        print(f"administrative judgment refused: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
