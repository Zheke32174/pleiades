#!/usr/bin/env python3
"""Separate remaining autonomous repository work from sovereign/live intervention."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator


class FrontierError(ValueError):
    pass


def _no_duplicate_keys(pairs: Iterable[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise FrontierError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle, object_pairs_hook=_no_duplicate_keys)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_bytes(value)).hexdigest()


def evaluate(bundle: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    Draft202012Validator.check_schema(schema)
    errors = sorted(Draft202012Validator(schema).iter_errors(bundle), key=lambda error: list(error.path))
    if errors:
        rendered = "; ".join("/".join(map(str, error.absolute_path)) + ": " + error.message for error in errors)
        raise FrontierError("bundle schema validation failed: " + rendered)

    repository_actions: list[dict[str, str]] = []
    sovereign_actions: list[dict[str, str]] = []
    readiness = bundle["repositoryReadiness"]
    repository_requirements = {
        "convergenceSuitePassed": ("run-convergence-suite", "Run and repair the aggregate convergence suite until its receipt passes."),
        "currentTreeSensitivityClear": ("clear-current-tree-sensitivity", "Remove every current-tree public sensitivity finding and retain a clear receipt."),
        "syntheticRehearsalPassed": ("run-synthetic-rehearsal", "Complete the full synthetic admission, rollback, learning, and non-escalation rehearsal."),
        "packageReceiptPresent": ("build-validation-package", "Build the offline validation package and retain its manifest/receipt."),
        "runbooksComplete": ("complete-operator-runbooks", "Complete and cross-check all operator and recovery runbooks."),
    }
    for field, (action_id, description) in repository_requirements.items():
        if readiness[field] is not True:
            repository_actions.append({"id": action_id, "description": description})

    if bundle["privateEcology"]["supplied"] is not True:
        sovereign_actions.append({"id": "supply-private-ecology", "description": "Supply the actual exhaustive private ecology registry and its authenticated provenance."})
    if bundle["observedInventory"]["supplied"] is not True:
        sovereign_actions.append({"id": "supply-observed-inventory", "description": "Supply a fresh authenticated repository/account inventory export."})
    if bundle["historyRewrite"]["decision"] == "pending":
        sovereign_actions.append({"id": "decide-history-rewrite", "description": "Approve or decline the coordinated history rewrite governed by issue #42."})
    if bundle["signingAuthority"]["delegated"] is not True:
        sovereign_actions.append({"id": "delegate-signing-authority", "description": "Designate the issuer and public signing-key identity without placing private key material in the bundle."})

    substrate = bundle["liveSubstrate"]
    if not substrate["nodes"]:
        sovereign_actions.append({"id": "supply-live-node-identities", "description": "Supply live node capability, public-key, and rollback-predecessor identities."})
    node_ids = {row["nodeId"] for row in substrate["nodes"]}
    if substrate["canaryNodeId"] is None:
        sovereign_actions.append({"id": "select-live-canary", "description": "Select the first live canary node and exact rollback predecessor."})
    elif substrate["canaryNodeId"] not in node_ids:
        raise FrontierError("canaryNodeId does not resolve to a supplied live node")
    if substrate["delegatedGrantIssued"] is not True:
        sovereign_actions.append({"id": "issue-first-live-grant", "description": "Issue the first real delegated authority grant inside the promoted constitutional envelope."})
    if substrate["liveLoopAuthorized"] is not True:
        sovereign_actions.append({"id": "authorize-live-loop", "description": "Authorize the live admission, observation, rollback, and learning loop."})
    if substrate["liveLoopCompleted"] is not True:
        sovereign_actions.append({"id": "complete-live-loop", "description": "Execute and observe the first live closed-loop transaction after authorization."})

    observation = bundle["sustainedObservation"]
    if observation["authorized"] is not True:
        sovereign_actions.append({"id": "authorize-observation-window", "description": "Authorize the sustained bounded-autonomy observation interval."})
    if observation["completed"] is not True:
        sovereign_actions.append({"id": "complete-observation-window", "description": "Allow the required observation interval to elapse and supply its evidence."})

    if repository_actions:
        status = "autonomous-repository-work-remains"
    elif sovereign_actions:
        status = "operator-intervention-required"
    else:
        status = "ready-to-derive-next-progression"

    receipt = {
        "apiVersion": "modos.pleiades/v1alpha1",
        "kind": "InterventionFrontierReceipt",
        "status": status,
        "bundleDigest": digest(bundle),
        "autonomousRepositoryActions": repository_actions,
        "operatorOrLiveActions": sovereign_actions,
        "autonomousActionCount": len(repository_actions),
        "operatorActionCount": len(sovereign_actions),
        "maySimulateOperatorConsent": False,
        "maySupplyPrivateData": False,
        "mayExecuteLiveActions": False,
        "authority": {"ceiling": "none", "canonicalMutationApplied": False},
    }
    receipt["receiptDigest"] = digest(receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--schema", type=Path, default=Path("modos/contracts/operator-intervention-bundle.schema.json"))
    parser.add_argument("--report", type=Path, default=Path("artifacts/intervention-frontier.json"))
    args = parser.parse_args()
    try:
        receipt = evaluate(load(args.bundle), load(args.schema))
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"intervention frontier: {receipt['status']}; {receipt['receiptDigest']}")
        return 0
    except (OSError, json.JSONDecodeError, FrontierError) as exc:
        print(f"intervention frontier evaluation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
