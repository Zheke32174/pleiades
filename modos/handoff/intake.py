#!/usr/bin/env python3
"""Compile opaque operator references into non-authoritative preparation plans."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator, FormatChecker

API_VERSION = "modos.pleiades/v1alpha1"
INPUT_IDS = (
    "privateEcology",
    "observedInventory",
    "nodeInventory",
    "signingIdentity",
    "historyDecision",
    "authorityGrant",
    "canaryPlan",
    "observationPlan",
)
OUTPUT_REQUIREMENTS: dict[str, tuple[str, ...]] = {
    "private-closure-candidate": ("privateEcology", "observedInventory"),
    "history-rewrite-decision-record": ("historyDecision",),
    "node-admission-candidate": ("nodeInventory", "signingIdentity"),
    "grant-issuance-proposal": ("authorityGrant", "signingIdentity"),
    "canary-admission-plan": ("nodeInventory", "canaryPlan"),
    "observation-window-plan": ("observationPlan",),
    "next-progression-candidate": INPUT_IDS,
}
SECRET_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\bghp_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
)
SENSITIVE_KEYS = {"password", "secret", "token", "privatekey", "private_key", "credential", "credentials"}


class IntakeError(ValueError):
    pass


def _no_duplicate_keys(pairs: Iterable[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, child in pairs:
        if key in value:
            raise IntakeError(f"duplicate JSON key: {key}")
        value[key] = child
    return value


def load(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle, object_pairs_hook=_no_duplicate_keys)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_bytes(value)).hexdigest()


def _walk_for_secrets(value: Any, location: str = "$") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = key.lower().replace("-", "").replace(" ", "")
            if normalized in SENSITIVE_KEYS:
                raise IntakeError(f"sensitive key is forbidden at {location}.{key}")
            _walk_for_secrets(child, f"{location}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _walk_for_secrets(child, f"{location}[{index}]")
    elif isinstance(value, str):
        for pattern in SECRET_PATTERNS:
            if pattern.search(value):
                raise IntakeError(f"secret-like material is forbidden at {location}")


def _validate_evidence_binding(input_id: str, row: dict[str, Any]) -> None:
    bound = all(row[field] is not None for field in ("artifactRef", "artifactDigest", "receiptDigest"))
    empty = all(row[field] is None for field in ("artifactRef", "artifactDigest", "receiptDigest"))
    if row["supplied"] is True and not bound:
        raise IntakeError(f"supplied input {input_id} must bind artifactRef, artifactDigest, and receiptDigest")
    if row["supplied"] is False and not empty:
        raise IntakeError(f"unsupplied input {input_id} must not carry artifact or receipt bindings")
    if row["classification"] != "public-reference" and row["artifactRef"] is not None:
        if not row["artifactRef"].startswith("urn:pleiades:"):
            raise IntakeError(f"non-public input {input_id} must use an opaque Pleiades URN")


def validate_candidate(candidate: dict[str, Any], schema: dict[str, Any]) -> None:
    Draft202012Validator.check_schema(schema)
    errors = sorted(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(candidate),
        key=lambda error: list(error.path),
    )
    if errors:
        rendered = "; ".join(
            "/".join(map(str, error.absolute_path)) + ": " + error.message for error in errors
        )
        raise IntakeError("candidate schema validation failed: " + rendered)
    _walk_for_secrets(candidate)
    for input_id in INPUT_IDS:
        _validate_evidence_binding(input_id, candidate["inputs"][input_id])

    decision = candidate["decisions"]
    history_supplied = candidate["inputs"]["historyDecision"]["supplied"]
    if decision["historyRewrite"] == "pending":
        if decision["authorizationRef"] is not None or decision["planDigest"] is not None:
            raise IntakeError("pending history decision cannot carry authorization or plan bindings")
    else:
        if not history_supplied or decision["authorizationRef"] is None:
            raise IntakeError("approved or declined history decision requires supplied sovereign evidence")

    selections = candidate["selections"]
    if selections["canaryNodeId"] is not None:
        if not candidate["inputs"]["nodeInventory"]["supplied"] or not candidate["inputs"]["canaryPlan"]["supplied"]:
            raise IntakeError("canary selection requires supplied node inventory and canary plan evidence")
    if selections["observationWindowSeconds"] is not None and not candidate["inputs"]["observationPlan"]["supplied"]:
        raise IntakeError("observation window requires supplied observation plan evidence")


def _output_plan(candidate: dict[str, Any], output_id: str) -> dict[str, Any]:
    requirements = OUTPUT_REQUIREMENTS[output_id]
    missing = [input_id for input_id in requirements if candidate["inputs"][input_id]["supplied"] is not True]
    if output_id == "history-rewrite-decision-record" and candidate["decisions"]["historyRewrite"] == "pending":
        missing.append("historyRewriteDecision")
    if output_id == "canary-admission-plan" and candidate["selections"]["canaryNodeId"] is None:
        missing.append("canaryNodeId")
    if output_id == "observation-window-plan" and candidate["selections"]["observationWindowSeconds"] is None:
        missing.append("observationWindowSeconds")
    if output_id == "next-progression-candidate" and candidate["decisions"]["historyRewrite"] == "pending":
        missing.append("historyRewriteDecision")

    evidence_refs = sorted(
        candidate["inputs"][input_id]["artifactRef"]
        for input_id in requirements
        if candidate["inputs"][input_id]["supplied"] is True
    )
    plan = {
        "outputId": output_id,
        "status": "ready-for-sovereign-review" if not missing else "blocked",
        "requiredInputs": list(requirements),
        "missingBindings": sorted(set(missing)),
        "evidenceRefs": evidence_refs,
        "executionApplied": False,
        "canonicalMutationApplied": False,
    }
    plan["planDigest"] = digest(plan)
    return plan


def compile_candidate(candidate: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    validate_candidate(candidate, schema)
    satisfied = sorted(input_id for input_id in INPUT_IDS if candidate["inputs"][input_id]["supplied"] is True)
    pending = sorted(set(INPUT_IDS) - set(satisfied))
    plans = [_output_plan(candidate, output_id) for output_id in sorted(candidate["requestedOutputs"])]
    blockers = sorted(
        {f"input-missing:{binding}" for plan in plans for binding in plan["missingBindings"]}
    )
    ready_count = sum(plan["status"] == "ready-for-sovereign-review" for plan in plans)
    blocked_count = len(plans) - ready_count
    if blocked_count:
        state = "operator-inputs-required"
    elif "next-progression-candidate" in candidate["requestedOutputs"]:
        state = "ready-to-derive-next-progression"
    else:
        state = "ready-for-sovereign-review"

    receipt: dict[str, Any] = {
        "apiVersion": API_VERSION,
        "kind": "OperatorInputCompilationReceipt",
        "candidateId": candidate["candidateId"],
        "candidateDigest": digest(candidate),
        "sourceCommit": candidate["sourceCommit"],
        "state": state,
        "satisfiedInputs": satisfied,
        "pendingInputs": pending,
        "outputPlans": plans,
        "readyOutputCount": ready_count,
        "blockedOutputCount": blocked_count,
        "blockers": blockers,
        "contentSafety": {
            "embeddedPayloadDetected": False,
            "privateKeyMaterialDetected": False,
            "secretPatternDetected": False,
        },
        "authority": {
            "ceiling": "none",
            "proposalOnly": True,
            "canonicalMutationApplied": False,
            "liveExecutionApplied": False,
            "historyRewriteApplied": False,
            "grantIssued": False,
        },
    }
    receipt["receiptDigest"] = digest(receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--schema", type=Path, default=Path("modos/contracts/operator-input-candidate.schema.json"))
    parser.add_argument("--report", type=Path, default=Path("artifacts/operator-input-compilation-receipt.json"))
    args = parser.parse_args()
    try:
        receipt = compile_candidate(load(args.candidate), load(args.schema))
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"operator input compilation {receipt['state']}: {receipt['receiptDigest']}")
        return 0
    except (OSError, json.JSONDecodeError, IntakeError) as exc:
        print(f"operator input compilation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
