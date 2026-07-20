#!/usr/bin/env python3
"""Deterministic executive-policy classifier.

The classifier selects an authorization path. It does not approve, execute, or
mutate a proposal, policy, grant, or canonical state.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Iterable

API_VERSION = "modos.pleiades/v1alpha1"


class PolicyError(ValueError):
    pass


def _reject_float(value: str) -> None:
    raise PolicyError(f"floating-point values are forbidden: {value}")


def _reject_constant(value: str) -> None:
    raise PolicyError(f"non-finite JSON constant is forbidden: {value}")


def _no_duplicate_keys(pairs: Iterable[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise PolicyError(f"duplicate JSON key is forbidden: {key}")
        result[key] = value
    return result


def load_json_strict(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle, parse_float=_reject_float, parse_constant=_reject_constant, object_pairs_hook=_no_duplicate_keys)


def _assert_no_floats(value: Any, location: str = "$") -> None:
    if isinstance(value, float):
        raise PolicyError(f"floating-point values are forbidden at {location}")
    if isinstance(value, dict):
        for key, child in value.items():
            _assert_no_floats(child, f"{location}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_no_floats(child, f"{location}[{index}]")


def canonical_bytes(value: Any) -> bytes:
    _assert_no_floats(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_bytes(value)).hexdigest()


def _validate_decision(decision: dict[str, Any], context: str) -> None:
    mode = decision.get("authorizationMode")
    human = decision.get("requiredHumanApprovals")
    machine = decision.get("machineExecutiveDecisionRequired")
    grant = decision.get("delegatedAuthorityGrantRequired")
    risk = decision.get("riskTier")
    capability = decision.get("executorCapability")
    if not isinstance(human, int) or isinstance(human, bool) or human < 0:
        raise PolicyError(f"{context} requiredHumanApprovals must be nonnegative")
    if not isinstance(capability, str) or not capability or "*" in capability:
        raise PolicyError(f"{context} executorCapability must be bounded")
    if mode == "delegated-machine-executive":
        if human != 0 or machine is not True or grant is not True:
            raise PolicyError(f"{context} delegated machine mode requires zero humans, a Mind decision, and a grant")
        if risk in {"high-impact", "constitutional"}:
            raise PolicyError(f"{context} delegated machine mode cannot authorize high-impact or constitutional risk")
    elif mode == "mixed-quorum":
        if human < 1 or machine is not True or grant is not True:
            raise PolicyError(f"{context} mixed quorum requires human approval, Mind decision, and grant")
    elif mode == "human-steward":
        if human < 1:
            raise PolicyError(f"{context} human-steward mode requires human approval")
    else:
        raise PolicyError(f"{context} authorizationMode is unsupported")
    if risk == "constitutional" and mode != "human-steward":
        raise PolicyError(f"{context} constitutional risk requires human-steward mode")


def validate_policy(policy: dict[str, Any]) -> None:
    if policy.get("apiVersion") != API_VERSION or policy.get("kind") != "ExecutivePolicy":
        raise PolicyError("unsupported executive policy envelope")
    if policy.get("authority") != {
        "machineMayModifyPolicy": False,
        "machineMayExpandOwnAuthority": False,
        "policyDecisionOnly": True,
    }:
        raise PolicyError("executive policy authority boundary is not exact")
    rules = policy.get("rules")
    if not isinstance(rules, list) or not rules:
        raise PolicyError("executive policy rules must be nonempty")
    rule_ids: set[str] = set()
    priorities: set[int] = set()
    for rule in rules:
        rule_id = rule.get("ruleId")
        priority = rule.get("priority")
        if not isinstance(rule_id, str) or not rule_id or rule_id in rule_ids:
            raise PolicyError("policy rule ids must be nonempty and unique")
        rule_ids.add(rule_id)
        if not isinstance(priority, int) or isinstance(priority, bool) or priority < 1 or priority in priorities:
            raise PolicyError("policy rule priorities must be positive and unique")
        priorities.add(priority)
        match = rule.get("match")
        if not isinstance(match, dict):
            raise PolicyError(f"policy rule {rule_id} match is required")
        for field in ("domains", "actions", "reversibility", "persistence", "impacts"):
            values = match.get(field)
            if not isinstance(values, list) or not values or len(set(values)) != len(values):
                raise PolicyError(f"policy rule {rule_id} {field} must be nonempty and unique")
            if any(value == "*" for value in values):
                raise PolicyError(f"policy rule {rule_id} wildcard {field} is forbidden")
        _validate_decision(rule.get("decision", {}), f"policy rule {rule_id}")
    reserved = policy.get("reservedPowers")
    if not isinstance(reserved, dict):
        raise PolicyError("reservedPowers are required")
    for field in ("constitutionalActions", "authorityActions"):
        values = reserved.get(field)
        if not isinstance(values, list) or not values or len(set(values)) != len(values) or "*" in values:
            raise PolicyError(f"reservedPowers.{field} must be bounded and unique")
    if not isinstance(reserved.get("requiredHumanApprovals"), int) or reserved["requiredHumanApprovals"] < 1:
        raise PolicyError("reserved powers require human approvals")


def _matches(rule: dict[str, Any], request: dict[str, Any]) -> bool:
    match = rule["match"]
    return (
        request["domain"] in match["domains"]
        and request["action"] in match["actions"]
        and request["reversibility"] in match["reversibility"]
        and request["persistence"] in match["persistence"]
        and request["impact"] in match["impacts"]
    )


def classify(policy: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    validate_policy(policy)
    if request.get("apiVersion") != API_VERSION or request.get("kind") != "ChangeClassificationRequest":
        raise PolicyError("unsupported classification request envelope")
    for field in ("domain", "action", "mindId", "requestId"):
        value = request.get(field)
        if not isinstance(value, str) or not value or value == "*":
            raise PolicyError(f"classification request {field} must be bounded")
    reserved = policy["reservedPowers"]
    if request["action"] in set(reserved["constitutionalActions"]) | set(reserved["authorityActions"]):
        decision = {
            "riskTier": "constitutional",
            "authorizationMode": "human-steward",
            "requiredHumanApprovals": reserved["requiredHumanApprovals"],
            "machineExecutiveDecisionRequired": True,
            "delegatedAuthorityGrantRequired": False,
            "executorCapability": "governance.constitution.stage",
            "rollbackRequired": True,
        }
        matched_rule = "reserved-power"
        reserved_power = True
    else:
        matched = sorted((rule for rule in policy["rules"] if _matches(rule, request)), key=lambda item: item["priority"])
        if not matched:
            raise PolicyError("no executive policy rule matches the request")
        selected = matched[0]
        decision = dict(selected["decision"])
        matched_rule = selected["ruleId"]
        reserved_power = False
        if request["reversibility"] == "irreversible" and decision["authorizationMode"] == "delegated-machine-executive":
            raise PolicyError("irreversible change cannot use delegated-machine-executive mode")
        if request["impact"] in {"high", "constitutional"} and decision["authorizationMode"] == "delegated-machine-executive":
            raise PolicyError("high-impact change cannot use delegated-machine-executive mode")
    _validate_decision(decision, "selected policy decision")
    return {
        "apiVersion": API_VERSION,
        "kind": "PolicyDecisionReceipt",
        "requestId": request["requestId"],
        "policyId": policy["policyId"],
        "policyDigest": digest(policy),
        "requestDigest": digest(request),
        "matchedRuleId": matched_rule,
        "classification": {"riskTier": decision["riskTier"], "reservedPower": reserved_power},
        "authorization": {
            "mode": decision["authorizationMode"],
            "requiredHumanApprovals": decision["requiredHumanApprovals"],
            "machineExecutiveDecisionRequired": decision["machineExecutiveDecisionRequired"],
            "delegatedAuthorityGrantRequired": decision["delegatedAuthorityGrantRequired"],
            "executorCapability": decision["executorCapability"],
            "rollbackRequired": decision["rollbackRequired"],
        },
        "authority": {
            "decisionAuthority": "classification-only",
            "canonicalMutationApplied": False,
            "policyMutationApplied": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--out-receipt", type=Path, required=True)
    args = parser.parse_args()
    try:
        receipt = classify(load_json_strict(args.policy), load_json_strict(args.request))
        args.out_receipt.parent.mkdir(parents=True, exist_ok=True)
        args.out_receipt.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(receipt["classification"]["riskTier"])
        return 0
    except (OSError, json.JSONDecodeError, PolicyError) as exc:
        print(f"policy classification failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
