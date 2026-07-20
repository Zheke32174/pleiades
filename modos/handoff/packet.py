#!/usr/bin/env python3
"""Bind convergence and operator-input evidence into a review-only handoff packet."""
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

try:
    from . import intake
except ImportError:
    import intake  # type: ignore

RUNBOOK_REFS = [
    "modos/convergence/OPERATOR_RUNBOOKS.md#private-ecology-closure",
    "modos/convergence/OPERATOR_RUNBOOKS.md#delegated-authority-grant-lifecycle",
    "modos/convergence/OPERATOR_RUNBOOKS.md#canary-admission",
    "modos/convergence/OPERATOR_RUNBOOKS.md#rollback-and-failed-postconditions",
    "modos/convergence/OPERATOR_RUNBOOKS.md#public-history-rewrite",
    "modos/convergence/OPERATOR_RUNBOOKS.md#sustained-autonomy-observation",
]


class PacketError(ValueError):
    pass


def _verify_self_digest(value: dict[str, Any], field: str, label: str) -> str:
    claimed = value.get(field)
    if not isinstance(claimed, str):
        raise PacketError(f"{label} is missing {field}")
    unsigned = copy.deepcopy(value)
    unsigned.pop(field, None)
    if intake.digest(unsigned) != claimed:
        raise PacketError(f"{label} {field} does not reproduce")
    return claimed


def _plan_summary(plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "outputId": plan["outputId"],
        "status": plan["status"],
        "planDigest": plan["planDigest"],
        "missingBindings": plan["missingBindings"],
    }


def build_packet(
    candidate: dict[str, Any],
    compilation: dict[str, Any],
    branch_evidence: dict[str, Any],
    frontier: dict[str, Any],
    schema: dict[str, Any],
    packet_id: str,
) -> dict[str, Any]:
    candidate_digest = intake.digest(candidate)
    if compilation.get("candidateDigest") != candidate_digest:
        raise PacketError("compilation receipt does not bind the exact operator candidate")
    if compilation.get("candidateId") != candidate.get("candidateId"):
        raise PacketError("compilation receipt candidateId mismatch")

    compilation_digest = _verify_self_digest(compilation, "receiptDigest", "compilation receipt")
    branch_digest = _verify_self_digest(branch_evidence, "evidenceDigest", "branch evidence")
    frontier_digest = _verify_self_digest(frontier, "receiptDigest", "frontier receipt")

    readiness = {
        "suitePassed": branch_evidence.get("suite", {}).get("status") == "pass"
        and branch_evidence.get("suite", {}).get("exitCode") == 0,
        "currentTreeClear": branch_evidence.get("currentTreeSensitivity", {}).get("status") == "clear",
        "syntheticRehearsalPassed": branch_evidence.get("syntheticRehearsal", {}).get("status") == "pass",
        "validationPackagePresent": bool(branch_evidence.get("validationPackage", {}).get("receiptDigest"))
        and branch_evidence.get("validationPackage", {}).get("privateMaterialIncluded") is False,
    }

    ready_plans = sorted(
        (_plan_summary(row) for row in compilation.get("outputPlans", []) if row.get("status") == "ready-for-sovereign-review"),
        key=lambda row: row["outputId"],
    )
    blocked_plans = sorted(
        (_plan_summary(row) for row in compilation.get("outputPlans", []) if row.get("status") == "blocked"),
        key=lambda row: row["outputId"],
    )
    operator_actions = sorted(
        frontier.get("operatorOrLiveActions", []),
        key=lambda row: row.get("id", ""),
    )

    if not all(readiness.values()):
        state = "repository-repair-required"
    elif blocked_plans:
        state = "operator-inputs-required"
    elif operator_actions:
        state = "operator-intervention-required"
    else:
        state = "ready-for-sovereign-review"

    packet: dict[str, Any] = {
        "apiVersion": "modos.pleiades/v1alpha1",
        "kind": "OperatorHandoffPacket",
        "packetId": packet_id,
        "bindings": {
            "candidateDigest": candidate_digest,
            "compilationReceiptDigest": compilation_digest,
            "branchEvidenceDigest": branch_digest,
            "frontierReceiptDigest": frontier_digest,
        },
        "state": state,
        "repositoryReadiness": readiness,
        "readyPlans": ready_plans,
        "blockedPlans": blocked_plans,
        "operatorActions": operator_actions,
        "runbookRefs": RUNBOOK_REFS,
        "contentSafety": {
            "privatePayloadIncluded": False,
            "privateKeyMaterialIncluded": False,
            "secretMaterialIncluded": False,
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
    packet["packetDigest"] = intake.digest(packet)

    Draft202012Validator.check_schema(schema)
    errors = sorted(Draft202012Validator(schema).iter_errors(packet), key=lambda error: list(error.path))
    if errors:
        rendered = "; ".join(
            "/".join(map(str, error.absolute_path)) + ": " + error.message for error in errors
        )
        raise PacketError("generated packet failed schema validation: " + rendered)
    return packet


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--compilation", type=Path, required=True)
    parser.add_argument("--branch-evidence", type=Path, default=Path("modos/convergence/BRANCH_EVIDENCE.json"))
    parser.add_argument("--frontier", type=Path, default=Path("artifacts/intervention-frontier.json"))
    parser.add_argument("--schema", type=Path, default=Path("modos/contracts/operator-handoff-packet.schema.json"))
    parser.add_argument("--packet-id", default="operator-handoff:pleiades-0001")
    parser.add_argument("--out", type=Path, default=Path("artifacts/operator-handoff-packet.json"))
    args = parser.parse_args()
    try:
        packet = build_packet(
            intake.load(args.candidate),
            intake.load(args.compilation),
            intake.load(args.branch_evidence),
            intake.load(args.frontier),
            intake.load(args.schema),
            args.packet_id,
        )
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"operator handoff packet {packet['state']}: {packet['packetDigest']}")
        return 0
    except (OSError, json.JSONDecodeError, intake.IntakeError, PacketError) as exc:
        print(f"operator handoff packet failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
