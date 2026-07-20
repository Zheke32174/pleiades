#!/usr/bin/env python3
"""Deterministic verifier for delegated Pleiades executive authority.

The verifier proves that one persistent Mind decision is covered by an active,
revocable grant and that a capability-bound executor mandate cannot exceed that
decision. It emits an authorization receipt. It does not execute the mandate,
change constitutional policy, or expand authority.
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
DIGEST_RE = re.compile(r"^sha256:(?!0{64}$)[0-9a-f]{64}$")
RISK_ORDER = {
    "observe-only": 0,
    "reversible-local": 1,
    "bounded-persistent": 2,
    "high-impact": 3,
    "constitutional": 4,
}


class ExecutiveAuthorityError(ValueError):
    """Raised when executive evidence is malformed or internally inconsistent."""


def _reject_float(value: str) -> None:
    raise ExecutiveAuthorityError(f"floating-point values are forbidden: {value}")


def _reject_constant(value: str) -> None:
    raise ExecutiveAuthorityError(f"non-finite JSON constant is forbidden: {value}")


def _no_duplicate_keys(pairs: Iterable[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ExecutiveAuthorityError(f"duplicate JSON key is forbidden: {key}")
        result[key] = value
    return result


def load_json_strict(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(
            handle,
            parse_float=_reject_float,
            parse_constant=_reject_constant,
            object_pairs_hook=_no_duplicate_keys,
        )


def _assert_no_floats(value: Any, location: str = "$") -> None:
    if isinstance(value, float):
        raise ExecutiveAuthorityError(f"floating-point values are forbidden at {location}")
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


def _require_digest(value: Any, field: str) -> str:
    if not isinstance(value, str) or not DIGEST_RE.fullmatch(value):
        raise ExecutiveAuthorityError(f"{field} must be a non-placeholder lowercase sha256 digest")
    return value


def _parse_time(value: Any, field: str) -> datetime:
    if not isinstance(value, str):
        raise ExecutiveAuthorityError(f"{field} must be an RFC3339 timestamp")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ExecutiveAuthorityError(f"{field} must be an RFC3339 timestamp") from exc


def _validate_grant(grant: dict[str, Any]) -> None:
    if grant.get("apiVersion") != API_VERSION or grant.get("kind") != "DelegatedAuthorityGrant":
        raise ExecutiveAuthorityError("unsupported delegated authority grant envelope")
    subject = grant.get("subject")
    if not isinstance(subject, dict) or subject.get("principalType") != "mind":
        raise ExecutiveAuthorityError("machine executive grant subject must be a Mind principal")
    if grant.get("status") != "active":
        raise ExecutiveAuthorityError("delegated authority grant must be active")
    if grant.get("autonomyMode") != "execute-within-grant":
        raise ExecutiveAuthorityError("delegated authority grant does not permit autonomous execution")
    domains = grant.get("domains")
    permissions = grant.get("permissions")
    if not isinstance(domains, list) or not domains or len(set(domains)) != len(domains):
        raise ExecutiveAuthorityError("grant domains must be a nonempty unique array")
    if not isinstance(permissions, list) or not permissions or len(set(permissions)) != len(permissions):
        raise ExecutiveAuthorityError("grant permissions must be a nonempty unique array")
    if "*" in domains or "*" in permissions:
        raise ExecutiveAuthorityError("wildcard executive authority is forbidden")
    constraints = grant.get("constraints")
    if not isinstance(constraints, dict):
        raise ExecutiveAuthorityError("grant constraints are required")
    if constraints.get("constitutionalMutationAllowed") is not False:
        raise ExecutiveAuthorityError("grant cannot permit constitutional mutation")
    if constraints.get("authorityExpansionAllowed") is not False:
        raise ExecutiveAuthorityError("grant cannot permit authority expansion")
    delegation = grant.get("delegation")
    if not isinstance(delegation, dict) or delegation.get("maySelfExpand") is not False:
        raise ExecutiveAuthorityError("grant cannot permit self-expansion")
    if delegation.get("revocable") is not True:
        raise ExecutiveAuthorityError("machine executive grant must be revocable")
    _require_digest(grant.get("provenance", {}).get("digest"), "grant provenance.digest")
    not_before = _parse_time(grant.get("validity", {}).get("notBefore"), "grant validity.notBefore")
    not_after = _parse_time(grant.get("validity", {}).get("notAfter"), "grant validity.notAfter")
    if not_before >= not_after:
        raise ExecutiveAuthorityError("grant validity interval is empty or reversed")


def _validate_decision(decision: dict[str, Any]) -> None:
    if decision.get("apiVersion") != API_VERSION or decision.get("kind") != "ExecutiveDecision":
        raise ExecutiveAuthorityError("unsupported executive decision envelope")
    for field in ("proposalDigest", "policyDigest", "rationaleDigest"):
        _require_digest(decision.get(field), f"decision {field}")
    classification = decision.get("classification")
    if not isinstance(classification, dict):
        raise ExecutiveAuthorityError("decision classification is required")
    risk = classification.get("riskTier")
    if risk not in RISK_ORDER:
        raise ExecutiveAuthorityError("decision riskTier is unsupported")
    if risk == "constitutional" or decision.get("separationOfDuties", {}).get("authorityExpansionDecision") is not False:
        raise ExecutiveAuthorityError("machine-only constitutional or authority-expansion decisions are forbidden")
    authority = decision.get("authority")
    if authority != {
        "grantBound": True,
        "selfExpansionApplied": False,
        "constitutionalMutationApplied": False,
    }:
        raise ExecutiveAuthorityError("executive decision authority boundary is not exact")
    separation = decision.get("separationOfDuties")
    if separation != {
        "proposerNotSoleDecider": True,
        "executorHasNoDecisionAuthority": True,
        "authorityExpansionDecision": False,
    }:
        raise ExecutiveAuthorityError("executive decision separation of duties is not exact")
    deliberation = decision.get("deliberation")
    if not isinstance(deliberation, dict) or deliberation.get("mode") != "polycentric-recurrent":
        raise ExecutiveAuthorityError("executive decision must use polycentric recurrent deliberation")
    if deliberation.get("dissentPreserved") is not True or not deliberation.get("dissentSummary"):
        raise ExecutiveAuthorityError("executive decision must preserve dissent")
    contributions = deliberation.get("contributions")
    if not isinstance(contributions, list) or len(contributions) < 3:
        raise ExecutiveAuthorityError("executive deliberation requires at least three contributions")
    principals = {item.get("principalRef") for item in contributions if isinstance(item, dict)}
    roles = {item.get("role") for item in contributions if isinstance(item, dict)}
    if len(principals) < 3:
        raise ExecutiveAuthorityError("executive deliberation requires at least three distinct principals")
    if not {"proposal", "risk", "policy"}.issubset(roles):
        raise ExecutiveAuthorityError("executive deliberation requires proposal, risk, and policy roles")
    if any(item.get("firstPassIndependent") is not True for item in contributions):
        raise ExecutiveAuthorityError("every executive contribution must preserve independent first pass")
    rollback = decision.get("rollback")
    if not isinstance(rollback, dict):
        raise ExecutiveAuthorityError("executive decision rollback binding is required")
    for field in ("planDigest", "predecessorDigest"):
        _require_digest(rollback.get(field), f"decision rollback.{field}")
    window = decision.get("executionWindow")
    start = _parse_time(window.get("notBefore") if isinstance(window, dict) else None, "decision executionWindow.notBefore")
    end = _parse_time(window.get("expiresAt") if isinstance(window, dict) else None, "decision executionWindow.expiresAt")
    if start >= end:
        raise ExecutiveAuthorityError("decision execution window is empty or reversed")


def _validate_mandate(mandate: dict[str, Any]) -> None:
    if mandate.get("apiVersion") != API_VERSION or mandate.get("kind") != "AdmissionMandate":
        raise ExecutiveAuthorityError("unsupported admission mandate envelope")
    for field in ("decisionDigest", "candidateDigest"):
        _require_digest(mandate.get(field), f"mandate {field}")
    transition = mandate.get("stateTransition")
    if not isinstance(transition, dict):
        raise ExecutiveAuthorityError("mandate stateTransition is required")
    for field in ("predecessorDigest", "targetDigest", "rollbackDigest"):
        _require_digest(transition.get(field), f"mandate stateTransition.{field}")
    executor = mandate.get("executor")
    if not isinstance(executor, dict) or executor.get("decisionAuthority") != "none":
        raise ExecutiveAuthorityError("admission executor must have no decision authority")
    authority = mandate.get("authority")
    if authority != {
        "executionOnly": True,
        "mayAlterPlan": False,
        "mayExpandAuthority": False,
        "mayChangeTarget": False,
    }:
        raise ExecutiveAuthorityError("admission mandate authority boundary is not exact")
    constraints = mandate.get("constraints")
    if not isinstance(constraints, dict):
        raise ExecutiveAuthorityError("admission mandate constraints are required")
    if constraints.get("reversible") is not True or constraints.get("automaticRollbackOnFailure") is not True:
        raise ExecutiveAuthorityError("admission mandate must be reversible with automatic rollback")
    if not isinstance(constraints.get("writeScope"), list) or not constraints["writeScope"]:
        raise ExecutiveAuthorityError("admission mandate requires a bounded writeScope")
    _parse_time(mandate.get("expiresAt"), "mandate expiresAt")


def authorize(
    grant: dict[str, Any],
    decision: dict[str, Any],
    mandate: dict[str, Any],
) -> dict[str, Any]:
    """Evaluate delegated machine authority and return an execution-pending receipt."""
    _validate_grant(grant)
    _validate_decision(decision)
    _validate_mandate(mandate)

    grant_start = _parse_time(grant["validity"]["notBefore"], "grant validity.notBefore")
    grant_end = _parse_time(grant["validity"]["notAfter"], "grant validity.notAfter")
    decision_start = _parse_time(decision["executionWindow"]["notBefore"], "decision executionWindow.notBefore")
    decision_end = _parse_time(decision["executionWindow"]["expiresAt"], "decision executionWindow.expiresAt")
    mandate_end = _parse_time(mandate["expiresAt"], "mandate expiresAt")

    classification = decision["classification"]
    transition = mandate["stateTransition"]
    constraints = grant["constraints"]
    comparisons = {
        "mind-principal-bound": grant["subject"]["principalRef"] == decision["mindId"],
        "grant-reference-bound": grant["grantId"] in decision["authorityGrantRefs"],
        "domain-covered": classification["domain"] in grant["domains"],
        "permission-covered": classification["action"] in grant["permissions"],
        "risk-within-ceiling": RISK_ORDER[classification["riskTier"]] <= RISK_ORDER[grant["riskCeiling"]],
        "grant-valid-for-decision-window": grant_start <= decision_start < decision_end <= grant_end,
        "decision-approved": decision["decision"] == "approve",
        "rollback-required-by-grant": (not constraints["rollbackRequired"]) or decision["rollback"]["required"],
        "reversibility-required-by-grant": (not constraints["reversibilityRequired"]) or mandate["constraints"]["reversible"],
        "decision-digest-bound": mandate["decisionDigest"] == digest(decision),
        "candidate-bound": mandate["candidateRef"] == decision["proposalRef"] and mandate["candidateDigest"] == decision["proposalDigest"],
        "target-bound": transition["targetDigest"] == decision["proposalDigest"],
        "predecessor-bound": transition["predecessorDigest"] == decision["rollback"]["predecessorDigest"],
        "rollback-bound": transition["rollbackDigest"] == decision["rollback"]["predecessorDigest"],
        "execution-budget-bound": mandate["constraints"]["timeoutSeconds"] <= constraints["maxExecutionSeconds"],
        "mandate-within-decision-window": decision_start <= mandate_end <= decision_end,
        "executor-is-decisionless": mandate["executor"]["decisionAuthority"] == "none",
        "authority-not-expanded": (
            grant["constraints"]["authorityExpansionAllowed"] is False
            and decision["authority"]["selfExpansionApplied"] is False
            and mandate["authority"]["mayExpandAuthority"] is False
        ),
        "constitution-unchanged": (
            grant["constraints"]["constitutionalMutationAllowed"] is False
            and decision["authority"]["constitutionalMutationApplied"] is False
        ),
    }
    blockers = sorted(name for name, passed in comparisons.items() if not passed)
    checks = [
        {
            "name": name,
            "status": "pass" if passed else "blocked",
            **({"detail": name} if not passed else {}),
        }
        for name, passed in comparisons.items()
    ]
    return {
        "apiVersion": API_VERSION,
        "kind": "ExecutiveAuthorizationReceipt",
        "decisionId": decision["decisionId"],
        "mandateId": mandate["mandateId"],
        "status": "authorized" if not blockers else "blocked",
        "bindings": {
            "mindId": decision["mindId"],
            "grantId": grant["grantId"],
            "proposalDigest": decision["proposalDigest"],
            "decisionDigest": digest(decision),
            "mandateDigest": digest(mandate),
            "predecessorDigest": transition["predecessorDigest"],
            "targetDigest": transition["targetDigest"],
            "rollbackDigest": transition["rollbackDigest"],
        },
        "checks": checks,
        "authority": {
            "decisionPrincipal": "delegated-mind",
            "executorDecisionAuthority": "none",
            "constitutionalMutationApplied": False,
            "authorityExpansionApplied": False,
            "executionStillPending": True,
        },
    }


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--grant", type=Path, required=True)
    parser.add_argument("--decision", type=Path, required=True)
    parser.add_argument("--mandate", type=Path, required=True)
    parser.add_argument("--out-receipt", type=Path, required=True)
    args = parser.parse_args()
    try:
        receipt = authorize(
            load_json_strict(args.grant),
            load_json_strict(args.decision),
            load_json_strict(args.mandate),
        )
        _write_json(args.out_receipt, receipt)
        print(receipt["status"])
        return 0 if receipt["status"] == "authorized" else 2
    except (OSError, json.JSONDecodeError, ExecutiveAuthorityError) as exc:
        print(f"executive authority validation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
