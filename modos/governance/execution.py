#!/usr/bin/env python3
"""Deterministic evaluator for reported execution and rollback evidence.

This module does not execute a mandate. It checks whether one reported attempt
remained inside an already-authorized mandate and whether rollback evidence
restored the exact predecessor when required.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

API_VERSION = "modos.pleiades/v1alpha1"


class ExecutionEvidenceError(ValueError):
    pass


def _reject_float(value: str) -> None:
    raise ExecutionEvidenceError(f"floating-point values are forbidden: {value}")


def _reject_constant(value: str) -> None:
    raise ExecutionEvidenceError(f"non-finite JSON constant is forbidden: {value}")


def _no_duplicate_keys(pairs: Iterable[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ExecutionEvidenceError(f"duplicate JSON key is forbidden: {key}")
        result[key] = value
    return result


def load_json_strict(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle, parse_float=_reject_float, parse_constant=_reject_constant, object_pairs_hook=_no_duplicate_keys)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_bytes(value)).hexdigest()


def _time(value: Any, field: str) -> datetime:
    if not isinstance(value, str):
        raise ExecutionEvidenceError(f"{field} must be an RFC3339 timestamp")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ExecutionEvidenceError(f"{field} must be an RFC3339 timestamp") from exc


def _audit(event_id: str, event_type: str, subject_ref: str, subject_digest: str, sequence: int, previous: str, recorded_at: str) -> dict[str, Any]:
    return {
        "apiVersion": API_VERSION,
        "kind": "ExecutiveAuditEvent",
        "eventId": event_id,
        "eventType": event_type,
        "subjectRef": subject_ref,
        "subjectDigest": subject_digest,
        "sequence": sequence,
        "previousEventDigest": previous,
        "recordedAt": recorded_at,
        "authority": {"appendOnly": True, "canonicalMutation": False},
    }


def evaluate_execution(authorization: dict[str, Any], mandate: dict[str, Any], attempt: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    if authorization.get("apiVersion") != API_VERSION or authorization.get("kind") != "ExecutiveAuthorizationReceipt":
        raise ExecutionEvidenceError("unsupported executive authorization receipt")
    if authorization.get("status") != "authorized" or authorization.get("authority", {}).get("executionStillPending") is not True:
        raise ExecutionEvidenceError("authorization receipt is not execution-pending and authorized")
    if mandate.get("apiVersion") != API_VERSION or mandate.get("kind") != "AdmissionMandate":
        raise ExecutionEvidenceError("unsupported admission mandate")
    if attempt.get("apiVersion") != API_VERSION or attempt.get("kind") != "ExecutionAttempt":
        raise ExecutionEvidenceError("unsupported execution attempt")
    if attempt.get("mandateId") != mandate.get("mandateId") or attempt.get("mandateId") != authorization.get("mandateId"):
        raise ExecutionEvidenceError("execution attempt mandate identity mismatch")
    if attempt.get("mandateDigest") != digest(mandate):
        raise ExecutionEvidenceError("execution attempt mandate digest mismatch")
    if attempt.get("authorizationReceiptDigest") != digest(authorization):
        raise ExecutionEvidenceError("execution attempt authorization digest mismatch")
    executor = mandate.get("executor", {})
    if attempt.get("executorRef") != executor.get("principalRef") or executor.get("decisionAuthority") != "none":
        raise ExecutionEvidenceError("execution attempt executor is not the exact decisionless mandate executor")
    started = _time(attempt.get("startedAt"), "attempt startedAt")
    completed = _time(attempt.get("completedAt"), "attempt completedAt")
    expires = _time(mandate.get("expiresAt"), "mandate expiresAt")
    if started >= completed or completed > expires:
        raise ExecutionEvidenceError("execution attempt time window is invalid or expired")
    preconditions = attempt.get("preconditions")
    postconditions = attempt.get("postconditions")
    if not isinstance(preconditions, list) or not preconditions or any(item.get("status") != "pass" for item in preconditions):
        raise ExecutionEvidenceError("all execution preconditions must pass")
    if not isinstance(postconditions, list) or not postconditions:
        raise ExecutionEvidenceError("execution postconditions must be reported")
    usage = attempt.get("resourceUsage", {})
    constraints = mandate.get("constraints", {})
    if usage.get("wallSeconds", 10**9) > constraints.get("timeoutSeconds", -1):
        raise ExecutionEvidenceError("execution wall time exceeds mandate budget")
    write_scope = constraints.get("writeScope")
    if not isinstance(write_scope, list) or not write_scope:
        raise ExecutionEvidenceError("mandate writeScope must be bounded")
    if usage.get("writeOperations", 10**9) > len(write_scope):
        raise ExecutionEvidenceError("execution write operations exceed bounded writeScope")
    transition = mandate.get("stateTransition", {})
    target_ok = attempt.get("observedTargetDigest") == transition.get("targetDigest")
    post_ok = all(item.get("status") == "pass" for item in postconditions)
    rollback = attempt.get("rollback", {})
    auto = constraints.get("automaticRollbackOnFailure") is True

    if target_ok and post_ok:
        status = "succeeded"
        rollback_status = "not-required"
        if rollback.get("attempted") is True:
            raise ExecutionEvidenceError("successful execution cannot report an attempted rollback")
    elif auto and rollback.get("attempted") is True and rollback.get("succeeded") is True and rollback.get("restoredDigest") == transition.get("predecessorDigest"):
        status = "rolled-back"
        rollback_status = "succeeded"
    else:
        status = "failed"
        rollback_status = "failed" if rollback.get("attempted") else "not-required"

    attempt_digest = digest(attempt)
    start_event = _audit(
        f"audit:{attempt['attemptId']}:1",
        "execution-started",
        attempt["attemptId"],
        attempt_digest,
        1,
        "sha256:" + "1" * 64,
        attempt["startedAt"],
    )
    terminal_type = {"succeeded": "execution-succeeded", "failed": "execution-failed", "rolled-back": "rollback-succeeded"}[status]
    terminal_event = _audit(
        f"audit:{attempt['attemptId']}:2",
        terminal_type,
        attempt["attemptId"],
        attempt_digest,
        2,
        digest(start_event),
        attempt["completedAt"],
    )
    checks = [
        {"name": "authorization-bound", "status": "pass"},
        {"name": "mandate-bound", "status": "pass"},
        {"name": "executor-decisionless", "status": "pass"},
        {"name": "preconditions-pass", "status": "pass"},
        {"name": "resource-budget-bound", "status": "pass"},
        {"name": "target-state-observed", "status": "pass" if target_ok else "fail", **({"detail": "target digest mismatch"} if not target_ok else {})},
        {"name": "postconditions-pass", "status": "pass" if post_ok else "fail", **({"detail": "one or more postconditions failed"} if not post_ok else {})},
        {"name": "rollback-restored-predecessor", "status": "pass" if status in {"succeeded", "rolled-back"} else "fail", **({"detail": "rollback did not restore predecessor"} if status == "failed" else {})},
    ]
    receipt = {
        "apiVersion": API_VERSION,
        "kind": "ExecutionReceipt",
        "attemptId": attempt["attemptId"],
        "mandateId": mandate["mandateId"],
        "status": status,
        "bindings": {
            "authorizationReceiptDigest": digest(authorization),
            "mandateDigest": digest(mandate),
            "attemptDigest": attempt_digest,
            "predecessorDigest": transition["predecessorDigest"],
            "targetDigest": transition["targetDigest"],
            "observedTargetDigest": attempt["observedTargetDigest"],
            "rollbackDigest": transition["rollbackDigest"],
        },
        "checks": checks,
        "resourceUsage": usage,
        "auditEvents": [start_event, terminal_event],
        "authority": {"executorDecisionAuthority": "none", "planAltered": False, "authorityExpanded": False},
    }
    rollback_receipt = {
        "apiVersion": API_VERSION,
        "kind": "RollbackReceipt",
        "attemptId": attempt["attemptId"],
        "status": rollback_status,
        "predecessorDigest": transition["predecessorDigest"],
        "restoredDigest": rollback.get("restoredDigest"),
        "evidenceDigest": rollback.get("evidenceDigest"),
        "authority": {"rollbackOnly": True, "targetChanged": False},
    }
    return receipt, rollback_receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--authorization", type=Path, required=True)
    parser.add_argument("--mandate", type=Path, required=True)
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--out-receipt", type=Path, required=True)
    parser.add_argument("--out-rollback", type=Path, required=True)
    args = parser.parse_args()
    try:
        receipt, rollback = evaluate_execution(load_json_strict(args.authorization), load_json_strict(args.mandate), load_json_strict(args.attempt))
        for path, value in ((args.out_receipt, receipt), (args.out_rollback, rollback)):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(receipt["status"])
        return 0 if receipt["status"] in {"succeeded", "rolled-back"} else 2
    except (OSError, json.JSONDecodeError, ExecutionEvidenceError) as exc:
        print(f"execution evidence validation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
