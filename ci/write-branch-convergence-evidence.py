#!/usr/bin/env python3
"""Write a compact, public-safe convergence evidence summary.

The writer consumes receipts already produced by the validation suite. It never
executes live actions, mutates canonical state, or includes private material.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


class EvidenceError(ValueError):
    pass


def load_optional(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise EvidenceError(f"receipt must be an object: {path}")
    return value


def digest(value: Any) -> str:
    data = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(data).hexdigest()


def failed_details(suite: dict[str, Any] | None) -> dict[str, Any]:
    details: dict[str, Any] = {}
    if suite is None:
        return details
    for row in suite.get("results", []):
        if isinstance(row, dict) and row.get("status") == "fail":
            command_id = row.get("id")
            if isinstance(command_id, str):
                details[command_id] = row.get("diagnostics", {})
    return details


def build_summary(args: argparse.Namespace) -> dict[str, Any]:
    artifacts = args.artifacts
    suite = load_optional(artifacts / "convergence-suite-receipt.json")
    current = load_optional(artifacts / "current-tree-sensitivity-receipt.json")
    history = load_optional(artifacts / "reachable-history-sensitivity-receipt.json")
    rehearsal = load_optional(artifacts / "synthetic-rehearsal-receipt.json")
    frontier = load_optional(artifacts / "intervention-frontier.json")
    package = load_optional(artifacts / "validation-package-receipt.json")
    ecology = load_optional(artifacts / "public-ecology-ontology-receipt.json")

    summary: dict[str, Any] = {
        "apiVersion": "modos.pleiades/v1alpha1",
        "kind": "BranchConvergenceEvidence",
        "validatedCommit": args.validated_commit,
        "suite": {
            "exitCode": args.suite_exit,
            "status": suite.get("status") if suite else "missing",
            "receiptDigest": suite.get("receiptDigest") if suite else None,
            "failures": suite.get("failures", []) if suite else ["receipt-missing"],
            "failureDetails": failed_details(suite),
            "notRun": suite.get("notRun", []) if suite else [],
            "executedCount": suite.get("executedCount", 0) if suite else 0,
            "commandCount": suite.get("commandCount", 0) if suite else 0,
        },
        "publicEcologyAdapter": {
            "exitCode": args.adapter_exit,
            "resultSnapshotDigest": ecology.get("resultSnapshotDigest") if ecology else None,
            "receiptDigest": ecology.get("receiptDigest") if ecology else None,
            "objectCount": ecology.get("objectCount") if ecology else None,
            "relationCount": ecology.get("relationCount") if ecology else None,
            "blockers": ecology.get("blockers", []) if ecology else ["receipt-missing"],
        },
        "currentTreeSensitivity": {
            "status": current.get("status") if current else "missing",
            "findingCount": current.get("findingCount") if current else None,
            "findings": current.get("findings", []) if current else [],
            "receiptDigest": current.get("receiptDigest") if current else None,
        },
        "reachableHistorySensitivity": {
            "exitCode": args.history_exit,
            "status": history.get("status") if history else "missing",
            "findingCount": history.get("findingCount") if history else None,
            "receiptDigest": history.get("receiptDigest") if history else None,
            "contentDisclosed": history.get("contentDisclosed") if history else False,
        },
        "syntheticRehearsal": {
            "status": rehearsal.get("status") if rehearsal else "missing",
            "receiptDigest": rehearsal.get("receiptDigest") if rehearsal else None,
            "remainingBlockers": rehearsal.get("remainingBlockers", []) if rehearsal else ["receipt-missing"],
        },
        "interventionFrontier": {
            "status": frontier.get("status") if frontier else "missing",
            "receiptDigest": frontier.get("receiptDigest") if frontier else None,
            "autonomousActionCount": frontier.get("autonomousActionCount") if frontier else None,
            "operatorActionCount": frontier.get("operatorActionCount") if frontier else None,
        },
        "validationPackage": {
            "packageDigest": package.get("packageDigest") if package else None,
            "manifestDigest": package.get("manifestDigest") if package else None,
            "sbomDigest": package.get("sbomDigest") if package else None,
            "receiptDigest": package.get("receiptDigest") if package else None,
            "privateMaterialIncluded": package.get("privateMaterialIncluded") if package else None,
        },
        "authority": {
            "ceiling": "none",
            "canonicalMutationApplied": False,
            "liveExecutionApplied": False,
        },
    }
    summary["evidenceDigest"] = digest(summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifacts", type=Path, default=Path("artifacts"))
    parser.add_argument("--out", type=Path, default=Path("modos/convergence/BRANCH_EVIDENCE.json"))
    parser.add_argument("--validated-commit", required=True)
    parser.add_argument("--suite-exit", type=int, required=True)
    parser.add_argument("--adapter-exit", type=int, required=True)
    parser.add_argument("--history-exit", type=int, required=True)
    args = parser.parse_args()
    try:
        summary = build_summary(args)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(summary["evidenceDigest"])
        return 0
    except (OSError, json.JSONDecodeError, EvidenceError) as exc:
        print(f"branch evidence publication failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
