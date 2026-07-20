#!/usr/bin/env python3
"""Deterministic constitutional amendment gate.

The gate verifies institutional identity, mixed deliberation, reserved-power
quorum, recusals, timelocks, cancellation, appeal, and rollback lineage. It
never activates an amendment.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

API_VERSION = "modos.pleiades/v1alpha1"


class ConstitutionalError(ValueError):
    pass


def _reject_float(value):
    raise ConstitutionalError(f"floating-point values are forbidden: {value}")


def _reject_constant(value):
    raise ConstitutionalError(f"non-finite JSON constant is forbidden: {value}")


def _pairs(items: Iterable[tuple[str, Any]]):
    result = {}
    for key, value in items:
        if key in result:
            raise ConstitutionalError(f"duplicate JSON key is forbidden: {key}")
        result[key] = value
    return result


def load_json_strict(path: Path):
    return json.loads(path.read_text(), parse_float=_reject_float, parse_constant=_reject_constant, object_pairs_hook=_pairs)


def canonical_bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value):
    return "sha256:" + hashlib.sha256(canonical_bytes(value)).hexdigest()


def _sha(value, field):
    if not isinstance(value, str) or len(value) != 71 or not value.startswith("sha256:"):
        raise ConstitutionalError(f"{field} must be sha256-bound")


def _time(value, field):
    if not isinstance(value, str):
        raise ConstitutionalError(f"{field} must be RFC3339")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ConstitutionalError(f"{field} must be RFC3339") from exc


def gate_amendment(registry: dict[str, Any], proposal: dict[str, Any], deliberation: dict[str, Any], evaluated_at: str) -> dict[str, Any]:
    if registry.get("apiVersion") != API_VERSION or registry.get("kind") != "ConstitutionalGovernanceRegistry":
        raise ConstitutionalError("unsupported governance registry")
    if registry.get("authority") != {
        "registryMayActivateAmendment": False,
        "registryMaySelfModify": False,
        "closureOnly": True,
    }:
        raise ConstitutionalError("governance registry authority boundary is not exact")
    principals = registry.get("principals")
    if not isinstance(principals, list) or len(principals) < 4:
        raise ConstitutionalError("governance registry requires institutional plurality")
    principal_map = {}
    active_roles = {}
    for principal in principals:
        principal_ref = principal.get("principalRef")
        if not isinstance(principal_ref, str) or not principal_ref or principal_ref in principal_map:
            raise ConstitutionalError("principal identities must be unique")
        if principal.get("principalType") not in {"human", "mind", "institution", "auditor", "appeal"}:
            raise ConstitutionalError(f"{principal_ref} principal type is unsupported")
        roles = principal.get("roles")
        if not isinstance(roles, list) or not roles or len(set(roles)) != len(roles):
            raise ConstitutionalError(f"{principal_ref} roles must be unique")
        if principal.get("status") not in {"active", "inactive", "succeeded"}:
            raise ConstitutionalError(f"{principal_ref} status is unsupported")
        conflicts = principal.get("conflictDomains", [])
        if not isinstance(conflicts, list) or len(set(conflicts)) != len(conflicts):
            raise ConstitutionalError(f"{principal_ref} conflicts must be unique")
        principal_map[principal_ref] = principal
        if principal["status"] == "active":
            for role in roles:
                active_roles.setdefault(role, []).append(principal_ref)
    for role in ("constitutional-steward", "machine-executive", "independent-auditor", "appeal-authority"):
        if role not in active_roles:
            raise ConstitutionalError(f"active governance role is missing: {role}")
    for principal in principals:
        successor = principal.get("successorRef")
        if successor is not None and successor not in principal_map:
            raise ConstitutionalError(f"{principal['principalRef']} successor is missing")
        if principal["status"] == "succeeded" and not successor:
            raise ConstitutionalError(f"{principal['principalRef']} succeeded principal requires successor")

    if proposal.get("apiVersion") != API_VERSION or proposal.get("kind") != "ConstitutionalAmendmentProposal":
        raise ConstitutionalError("unsupported amendment proposal")
    if proposal.get("authority") != {"ceiling": "proposal", "activationApplied": False, "selfApprovalAllowed": False}:
        raise ConstitutionalError("amendment proposal authority boundary is not exact")
    for field in ("currentConstitutionDigest", "candidateConstitutionDigest", "rollbackDigest", "rationaleDigest"):
        _sha(proposal.get(field), f"proposal.{field}")
    if proposal["rollbackDigest"] != proposal["currentConstitutionDigest"]:
        raise ConstitutionalError("constitutional rollback must restore the predecessor")
    amendment_class = proposal.get("amendmentClass")
    policies = registry.get("quorumPolicies")
    if not isinstance(policies, dict) or amendment_class not in policies:
        raise ConstitutionalError("amendment class lacks quorum policy")
    policy = policies[amendment_class]
    proposed = _time(proposal.get("proposedAt"), "proposal proposedAt")
    cancellation_deadline = _time(proposal.get("cancellationDeadline"), "proposal cancellationDeadline")
    activation = _time(proposal.get("activationNotBefore"), "proposal activationNotBefore")
    evaluated = _time(evaluated_at, "evaluatedAt")
    minimum_hours = policy.get("minimumTimelockHours")
    if not isinstance(minimum_hours, int) or minimum_hours < 1:
        raise ConstitutionalError("minimum timelock is invalid")
    if not proposed < cancellation_deadline <= activation:
        raise ConstitutionalError("cancellation and activation ordering is invalid")
    if activation - proposed < timedelta(hours=minimum_hours):
        raise ConstitutionalError("constitutional timelock is too short")
    if proposal.get("supersedesRef") == proposal.get("proposalId"):
        raise ConstitutionalError("amendment cannot supersede itself")

    if deliberation.get("apiVersion") != API_VERSION or deliberation.get("kind") != "ConstitutionalDeliberation":
        raise ConstitutionalError("unsupported constitutional deliberation")
    if deliberation.get("proposalId") != proposal.get("proposalId") or deliberation.get("proposalDigest") != digest(proposal):
        raise ConstitutionalError("deliberation proposal binding failed")
    contributions = deliberation.get("contributions")
    if not isinstance(contributions, list) or not contributions:
        raise ConstitutionalError("constitutional deliberation requires contributions")
    counted = []
    recused = []
    auditors = []
    appeals = []
    contribution_ids = set()
    for contribution in contributions:
        contribution_id = contribution.get("contributionId")
        principal_ref = contribution.get("principalRef")
        if not isinstance(contribution_id, str) or not contribution_id or contribution_id in contribution_ids:
            raise ConstitutionalError("contribution ids must be unique")
        contribution_ids.add(contribution_id)
        principal = principal_map.get(principal_ref)
        if principal is None or principal["status"] != "active":
            raise ConstitutionalError(f"contribution principal is not active: {principal_ref}")
        if contribution.get("firstPassIndependent") is not True:
            raise ConstitutionalError(f"{contribution_id} must preserve independent first pass")
        if contribution.get("position") not in {"approve", "reject", "abstain", "audit", "appeal"}:
            raise ConstitutionalError(f"{contribution_id} position is unsupported")
        conflict = amendment_class in principal.get("conflictDomains", []) or contribution.get("conflictDeclared") is True
        if conflict:
            if contribution.get("recused") is not True:
                raise ConstitutionalError(f"{contribution_id} conflicted principal must recuse")
            recused.append(principal_ref)
            continue
        if contribution.get("recused") is True:
            recused.append(principal_ref)
            continue
        if "independent-auditor" in principal["roles"]:
            if contribution["position"] != "audit":
                raise ConstitutionalError(f"{contribution_id} auditor must submit audit position")
            auditors.append(principal_ref)
            continue
        if "appeal-authority" in principal["roles"]:
            if contribution["position"] != "appeal":
                raise ConstitutionalError(f"{contribution_id} appeal authority cannot approve amendment")
            appeals.append(principal_ref)
            continue
        counted.append((principal, contribution))

    human_approvals = sum(
        1 for principal, contribution in counted
        if principal["principalType"] in {"human", "institution"}
        and contribution["position"] == "approve"
        and "constitutional-steward" in principal["roles"]
    )
    machine_approvals = sum(
        1 for principal, contribution in counted
        if principal["principalType"] == "mind"
        and contribution["position"] == "approve"
        and "machine-executive" in principal["roles"]
    )
    rejects = sum(1 for _, contribution in counted if contribution["position"] == "reject")
    if human_approvals < policy.get("requiredHumanApprovals", 0):
        raise ConstitutionalError("reserved human quorum is not satisfied")
    if machine_approvals < policy.get("requiredMachineApprovals", 0):
        raise ConstitutionalError("machine executive quorum is not satisfied")
    if len(set(auditors)) < policy.get("requiredIndependentAudits", 1):
        raise ConstitutionalError("independent audit quorum is not satisfied")
    if rejects > policy.get("maximumRejects", 0):
        raise ConstitutionalError("constitutional reject threshold exceeded")

    cancellations = deliberation.get("cancellationRequests", [])
    if not isinstance(cancellations, list):
        raise ConstitutionalError("cancellationRequests must be an array")
    valid_cancellations = []
    for item in cancellations:
        principal_ref = item.get("principalRef")
        requested = _time(item.get("requestedAt"), "cancellation requestedAt")
        principal = principal_map.get(principal_ref)
        if principal is None or principal["status"] != "active" or "constitutional-steward" not in principal["roles"]:
            raise ConstitutionalError("cancellation requester lacks authority")
        if requested > cancellation_deadline:
            raise ConstitutionalError("cancellation request missed deadline")
        valid_cancellations.append(principal_ref)

    status = "cancelled" if valid_cancellations else ("timelock-pending" if evaluated < activation else "eligible-for-activation")
    appeal_window_end = activation + timedelta(hours=policy.get("appealWindowHours", 24))
    return {
        "apiVersion": API_VERSION,
        "kind": "ConstitutionalAmendmentReceipt",
        "proposalId": proposal["proposalId"],
        "status": status,
        "bindings": {
            "registryDigest": digest(registry),
            "proposalDigest": digest(proposal),
            "deliberationDigest": digest(deliberation),
            "predecessorDigest": proposal["currentConstitutionDigest"],
            "candidateDigest": proposal["candidateConstitutionDigest"],
            "rollbackDigest": proposal["rollbackDigest"],
            "supersedesRef": proposal.get("supersedesRef"),
        },
        "quorum": {
            "humanApprovals": human_approvals,
            "machineApprovals": machine_approvals,
            "independentAuditors": sorted(set(auditors)),
            "appealAuthorities": sorted(set(appeals)),
            "recusedPrincipals": sorted(set(recused)),
            "rejects": rejects,
        },
        "timing": {
            "proposedAt": proposal["proposedAt"],
            "cancellationDeadline": proposal["cancellationDeadline"],
            "activationNotBefore": proposal["activationNotBefore"],
            "appealWindowEndsAt": appeal_window_end.isoformat().replace("+00:00", "Z"),
            "evaluatedAt": evaluated_at,
        },
        "cancellationRequests": sorted(set(valid_cancellations)),
        "checks": [
            {"name": "institutional-plurality", "status": "pass"},
            {"name": "succession-resolves", "status": "pass"},
            {"name": "conflicts-recused", "status": "pass"},
            {"name": "mixed-quorum-satisfied", "status": "pass"},
            {"name": "independent-audit-satisfied", "status": "pass"},
            {"name": "appeal-separated", "status": "pass"},
            {"name": "timelock-bound", "status": "pass"},
            {"name": "cancellation-window-bound", "status": "pass"},
            {"name": "rollback-lineage-bound", "status": "pass"},
            {"name": "supersession-acyclic-local", "status": "pass"},
        ],
        "authority": {
            "activationApplied": False,
            "constitutionalMutationApplied": False,
            "executorAuthority": "none",
            "reservedPowerRequired": True,
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--proposal", type=Path, required=True)
    parser.add_argument("--deliberation", type=Path, required=True)
    parser.add_argument("--evaluated-at", required=True)
    parser.add_argument("--out-receipt", type=Path, required=True)
    args = parser.parse_args()
    try:
        receipt = gate_amendment(
            load_json_strict(args.registry),
            load_json_strict(args.proposal),
            load_json_strict(args.deliberation),
            args.evaluated_at,
        )
        args.out_receipt.parent.mkdir(parents=True, exist_ok=True)
        args.out_receipt.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
        print(receipt["status"])
        return 0
    except (OSError, json.JSONDecodeError, ConstitutionalError) as exc:
        print(f"constitutional gate failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
