#!/usr/bin/env python3
"""Verify operational authorization quorum and exact transition lineage.

The preflight may declare a candidate eligible for mandate construction. It
never constructs a mandate, applies authorization, executes a transition, or
modifies the authority registry.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

try:
    from .common import TrustError, canonical_bytes, decode_base64, digest, load, parse_time, verify_self_digest
    from .evidence import validate_registry, validate_schema
except ImportError:
    from common import TrustError, canonical_bytes, decode_base64, digest, load, parse_time, verify_self_digest  # type: ignore
    from evidence import validate_registry, validate_schema  # type: ignore

API_VERSION = "modos.pleiades/v1alpha1"
RISK_ORDER = {"observe-only": 0, "reversible-local": 1, "bounded-persistent": 2, "high-impact": 3, "constitutional": 4}
AUTHORITY = {"ceiling": "none", "preflightOnly": True, "mandateConstructed": False, "authorizationApplied": False, "executionApplied": False, "registryMutationApplied": False}


def approval_statement(candidate: dict[str, Any], approval: dict[str, Any]) -> dict[str, Any]:
    candidate_core = copy.deepcopy(candidate)
    candidate_core.pop("approvals")
    approval_core = copy.deepcopy(approval)
    approval_core.pop("signatureBase64", None)
    return {"authorizationCandidate": candidate_core, "approval": approval_core}


def revocation_for(registry: dict[str, Any], evaluated_at, *, approval_id: str, principal_ref: str, key_ref: str) -> str | None:
    for row in registry["revocations"]:
        if parse_time(row["effectiveAt"], f"{row['revocationId']}.effectiveAt") > evaluated_at:
            continue
        if (row["targetType"], row["targetRef"]) in {("approval", approval_id), ("principal", principal_ref), ("key", key_ref)}:
            return row["revocationId"]
    return None


def matching_policy(registry: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    decision = candidate["decision"]
    matches = [policy for policy in registry["decisionPolicies"] if policy["decisionType"] == decision["decisionType"] and decision["domain"] in policy["domains"] and decision["action"] in policy["actions"] and decision["riskTier"] in policy["riskTiers"]]
    if len(matches) != 1:
        raise TrustError("transition decision must resolve to exactly one operational policy")
    return matches[0]


def evaluate_preflight(registry: dict[str, Any], candidate: dict[str, Any], compilation: dict[str, Any], trust_receipt: dict[str, Any], grant: dict[str, Any], evaluated_at: str, *, registry_schema: dict[str, Any] | None = None, candidate_schema: dict[str, Any] | None = None, trust_schema: dict[str, Any] | None = None, grant_schema: dict[str, Any] | None = None, receipt_schema: dict[str, Any] | None = None) -> dict[str, Any]:
    if registry_schema is not None:
        validate_schema(registry, registry_schema, "operational authority registry")
    if candidate_schema is not None:
        validate_schema(candidate, candidate_schema, "transition authorization candidate")
    if trust_schema is not None:
        validate_schema(trust_receipt, trust_schema, "operator evidence trust receipt")
    if grant_schema is not None:
        validate_schema(grant, grant_schema, "delegated authority grant")
    principals, keys, _ = validate_registry(registry)
    evaluated = parse_time(evaluated_at, "evaluatedAt")

    trust_digest = verify_self_digest(trust_receipt, "receiptDigest", "operator evidence trust receipt")
    compilation_digest = verify_self_digest(compilation, "receiptDigest", "operator compilation receipt")
    if candidate["candidateDigest"] != trust_receipt["candidateDigest"]:
        raise TrustError("authorization candidate does not bind trusted operator candidate")
    if candidate["evidenceTrustReceiptDigest"] != trust_digest:
        raise TrustError("authorization candidate trust receipt binding failed")
    if candidate["candidateDigest"] != compilation["candidateDigest"]:
        raise TrustError("authorization candidate compilation binding failed")
    if candidate["compilationReceiptDigest"] != compilation_digest:
        raise TrustError("authorization candidate compilation receipt digest mismatch")

    plans = {row["outputId"]: row for row in compilation["outputPlans"]}
    plan = plans.get(candidate["plan"]["outputId"])
    if plan is None or plan["status"] != "ready-for-sovereign-review":
        raise TrustError("selected plan is not ready for sovereign review")
    if plan["planDigest"] != candidate["plan"]["planDigest"]:
        raise TrustError("selected plan digest mismatch")

    observed_grant_digest = digest(grant)
    if candidate["grantRef"] != grant["grantId"] or candidate["grantDigest"] != observed_grant_digest:
        raise TrustError("delegated grant binding failed")

    policy = matching_policy(registry, candidate)
    if candidate["decision"]["authorizationMode"] != policy["authorizationMode"]:
        raise TrustError("authorization mode differs from operational policy")
    proposer = principals.get(candidate["proposerRef"])
    executor = principals.get(candidate["executorRef"])
    if proposer is None or proposer["status"] != "active" or "proposer" not in proposer["roles"]:
        raise TrustError("proposer is not an active operational proposer")
    if executor is None or executor["status"] != "active" or "executor" not in executor["roles"]:
        raise TrustError("executor is not an active operational executor")
    if candidate["proposerRef"] == candidate["executorRef"]:
        raise TrustError("proposer and executor must be distinct")
    if candidate["executorCapability"] != policy["executorCapability"]:
        raise TrustError("candidate executor capability differs from policy")
    if candidate["executorCapability"] not in executor["executorCapabilities"]:
        raise TrustError("executor lacks the exact required capability")

    blockers: list[str] = []
    if trust_receipt["state"] != "trusted":
        blockers.append("operator-evidence-not-trusted")
    if trust_receipt["trustedInputCount"] != trust_receipt["requiredInputCount"]:
        blockers.append("operator-evidence-incomplete")
    if policy["rollbackRequired"]:
        if candidate["lineage"]["rollbackDigest"] != candidate["lineage"]["predecessorDigest"]:
            blockers.append("rollback-does-not-restore-predecessor")
        if candidate["lineage"]["targetDigest"] == candidate["lineage"]["predecessorDigest"]:
            blockers.append("target-does-not-change-predecessor")

    grant_revoked = None
    for row in registry["revocations"]:
        if row["targetType"] == "grant" and row["targetRef"] == grant["grantId"] and parse_time(row["effectiveAt"], f"{row['revocationId']}.effectiveAt") <= evaluated:
            grant_revoked = row["revocationId"]
            break
    if policy["grantRequired"]:
        if grant["status"] != "active":
            blockers.append("delegated-grant-not-active")
        if grant_revoked is not None:
            blockers.append(f"delegated-grant-revoked:{grant_revoked}")
        if candidate["decision"]["domain"] not in grant["domains"]:
            blockers.append("delegated-grant-domain-mismatch")
        if candidate["decision"]["action"] not in grant["permissions"]:
            blockers.append("delegated-grant-permission-mismatch")
        if RISK_ORDER[grant["riskCeiling"]] < RISK_ORDER[candidate["decision"]["riskTier"]]:
            blockers.append("delegated-grant-risk-ceiling-too-low")
        not_before = parse_time(grant["validity"]["notBefore"], "grant.validity.notBefore")
        not_after = parse_time(grant["validity"]["notAfter"], "grant.validity.notAfter")
        if not not_before <= evaluated < not_after:
            blockers.append("delegated-grant-outside-validity")
        if policy["rollbackRequired"] and grant["constraints"]["rollbackRequired"] is not True:
            blockers.append("delegated-grant-does-not-require-rollback")

    role_counts = {role: 0 for role in policy["requiredRoleApprovals"]}
    auditors: set[str] = set()
    counted_approvers: set[str] = set()
    recused: set[str] = set()
    rejects = 0
    approval_ids: set[str] = set()
    nonces: set[str] = set()
    principal_contributions: set[str] = set()

    for approval in sorted(candidate["approvals"], key=lambda row: row["approvalId"]):
        approval_id = approval["approvalId"]
        if approval_id in approval_ids:
            raise TrustError(f"duplicate approvalId: {approval_id}")
        if approval["nonce"] in nonces:
            raise TrustError(f"duplicate approval nonce: {approval['nonce']}")
        if approval["principalRef"] in principal_contributions:
            raise TrustError(f"principal contributed more than once: {approval['principalRef']}")
        approval_ids.add(approval_id)
        nonces.add(approval["nonce"])
        principal_contributions.add(approval["principalRef"])

        principal = principals.get(approval["principalRef"])
        key = keys.get(approval["keyRef"])
        if principal is None or principal["status"] != "active":
            raise TrustError(f"approval principal is not active: {approval['principalRef']}")
        if candidate["decision"]["decisionType"] not in principal["decisionTypes"]:
            raise TrustError(f"principal is not scoped to decision type: {approval['principalRef']}")
        if key is None or key["principalRef"] != approval["principalRef"] or key["status"] != "active":
            raise TrustError(f"approval key is not active for principal: {approval_id}")
        if key["algorithm"] != approval["algorithm"] or approval["algorithm"] != "Ed25519":
            raise TrustError(f"approval algorithm mismatch: {approval_id}")

        signed_at = parse_time(approval["signedAt"], f"{approval_id}.signedAt")
        if signed_at > evaluated:
            raise TrustError(f"approval is future-dated: {approval_id}")
        key_start = parse_time(key["validFrom"], f"{key['keyRef']}.validFrom")
        key_end = parse_time(key["validUntil"], f"{key['keyRef']}.validUntil")
        if not key_start <= signed_at < key_end:
            raise TrustError(f"approval was signed outside key validity: {approval_id}")

        revocation = revocation_for(registry, evaluated, approval_id=approval_id, principal_ref=approval["principalRef"], key_ref=approval["keyRef"])
        if revocation is not None:
            raise TrustError(f"approval trust is revoked by {revocation}")

        public_key = decode_base64(key["publicKeyBase64"], f"{key['keyRef']}.publicKeyBase64", 32)
        if "sha256:" + hashlib.sha256(public_key).hexdigest() != key["publicKeyDigest"]:
            raise TrustError(f"approval public key digest mismatch: {approval_id}")
        signature = decode_base64(approval["signatureBase64"], f"{approval_id}.signatureBase64", 64)
        try:
            Ed25519PublicKey.from_public_bytes(public_key).verify(signature, canonical_bytes(approval_statement(candidate, approval)))
        except InvalidSignature as exc:
            raise TrustError(f"approval signature is invalid: {approval_id}") from exc

        conflicted = candidate["decision"]["domain"] in principal["conflictDomains"] or approval["conflictDeclared"] is True
        if conflicted:
            if approval["recused"] is not True:
                raise TrustError(f"conflicted principal must recuse: {approval_id}")
            recused.add(approval["principalRef"])
            continue
        if approval["recused"] is True:
            recused.add(approval["principalRef"])
            continue
        if approval["principalRef"] == candidate["proposerRef"] and approval["position"] == "approve" and policy["proposerMayApprove"] is False:
            raise TrustError("proposer may not approve the transition")
        if approval["principalRef"] == candidate["executorRef"] and approval["position"] == "approve" and policy["executorMayApprove"] is False:
            raise TrustError("executor may not approve the transition")

        if approval["position"] == "reject":
            rejects += 1
        elif approval["position"] == "audit":
            if "independent-auditor" not in principal["roles"]:
                raise TrustError(f"audit contribution lacks auditor role: {approval_id}")
            auditors.add(approval["principalRef"])
        elif approval["position"] == "approve":
            counted_approvers.add(approval["principalRef"])
            for role in role_counts:
                if role in principal["roles"]:
                    role_counts[role] += 1

    for role, required in policy["requiredRoleApprovals"].items():
        if role_counts[role] < required:
            blockers.append(f"required-role-quorum-unsatisfied:{role}")
    if len(auditors) < policy["requiredIndependentAudits"]:
        blockers.append("independent-audit-quorum-unsatisfied")
    if rejects > policy["maximumRejects"]:
        blockers.append("reject-threshold-exceeded")
    if policy["grantRequired"] and grant["subject"]["principalRef"] not in counted_approvers:
        blockers.append("delegated-grant-subject-did-not-approve")

    status = "eligible-for-mandate-construction" if not blockers else "blocked"
    check_names = ["trusted-evidence-bound", "plan-lineage-bound", "decision-policy-closed", "grant-active-and-in-scope", "approval-signatures-valid", "required-role-quorum-satisfied", "independent-audit-satisfied", "proposer-executor-approval-separated", "rollback-restores-predecessor"]
    blocked_checks = {
        "trusted-evidence-bound": any(value.startswith("operator-evidence") for value in blockers),
        "grant-active-and-in-scope": any(value.startswith("delegated-grant") for value in blockers),
        "required-role-quorum-satisfied": any(value.startswith("required-role") for value in blockers),
        "independent-audit-satisfied": "independent-audit-quorum-unsatisfied" in blockers,
        "rollback-restores-predecessor": any(value in {"rollback-does-not-restore-predecessor", "target-does-not-change-predecessor"} for value in blockers),
    }
    checks = [{"name": name, "status": "blocked" if blocked_checks.get(name, False) else "pass"} for name in check_names]

    receipt: dict[str, Any] = {
        "apiVersion": API_VERSION,
        "kind": "TransitionPreflightReceipt",
        "authorizationId": candidate["authorizationId"],
        "status": status,
        "evaluatedAt": evaluated_at,
        "bindings": {"registryDigest": digest(registry), "authorizationCandidateDigest": digest(candidate), "operatorCandidateDigest": candidate["candidateDigest"], "compilationReceiptDigest": compilation_digest, "evidenceTrustReceiptDigest": trust_digest, "planDigest": candidate["plan"]["planDigest"], "grantDigest": observed_grant_digest, "predecessorDigest": candidate["lineage"]["predecessorDigest"], "targetDigest": candidate["lineage"]["targetDigest"], "rollbackDigest": candidate["lineage"]["rollbackDigest"]},
        "decision": {"decisionType": candidate["decision"]["decisionType"], "authorizationMode": candidate["decision"]["authorizationMode"], "domain": candidate["decision"]["domain"], "action": candidate["decision"]["action"], "riskTier": candidate["decision"]["riskTier"], "executorCapability": candidate["executorCapability"]},
        "quorum": {"roleApprovals": role_counts, "independentAuditors": sorted(auditors), "countedApprovers": sorted(counted_approvers), "recusedPrincipals": sorted(recused), "rejects": rejects},
        "checks": checks,
        "blockers": sorted(set(blockers)),
        "authority": AUTHORITY,
    }
    receipt["receiptDigest"] = digest(receipt)
    if receipt_schema is not None:
        validate_schema(receipt, receipt_schema, "transition preflight receipt")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--compilation", type=Path, required=True)
    parser.add_argument("--trust-receipt", type=Path, required=True)
    parser.add_argument("--grant", type=Path, required=True)
    parser.add_argument("--evaluated-at", required=True)
    parser.add_argument("--registry-schema", type=Path, default=Path("modos/contracts/operational-authority-registry.schema.json"))
    parser.add_argument("--candidate-schema", type=Path, default=Path("modos/contracts/transition-authorization-candidate.schema.json"))
    parser.add_argument("--trust-schema", type=Path, default=Path("modos/contracts/operator-evidence-trust-receipt.schema.json"))
    parser.add_argument("--grant-schema", type=Path, default=Path("modos/contracts/delegated-authority-grant.schema.json"))
    parser.add_argument("--receipt-schema", type=Path, default=Path("modos/contracts/transition-preflight-receipt.schema.json"))
    parser.add_argument("--report", type=Path, default=Path("artifacts/transition-preflight-receipt.json"))
    args = parser.parse_args()
    try:
        receipt = evaluate_preflight(load(args.registry), load(args.candidate), load(args.compilation), load(args.trust_receipt), load(args.grant), args.evaluated_at, registry_schema=load(args.registry_schema), candidate_schema=load(args.candidate_schema), trust_schema=load(args.trust_schema), grant_schema=load(args.grant_schema), receipt_schema=load(args.receipt_schema))
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"transition preflight {receipt['status']}: {receipt['receiptDigest']}")
        return 0 if receipt["status"] == "eligible-for-mandate-construction" else 2
    except (OSError, json.JSONDecodeError, TrustError) as exc:
        print(f"transition preflight failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
