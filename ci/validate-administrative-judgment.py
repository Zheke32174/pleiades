#!/usr/bin/env python3
"""Validate the administrative judgment contract and deterministic golden fixture."""
from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
GOVERNANCE = ROOT / "modos" / "governance"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    schema = load(ROOT / "modos" / "contracts" / "administrative-judgment.schema.json")
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    judgment = load_module(GOVERNANCE / "judgment.py", "administrative_judgment")
    fixtures = load_module(GOVERNANCE / "judgment_fixtures.py", "administrative_judgment_fixtures")
    policy = copy.deepcopy(fixtures.POLICY_RECEIPT)
    workspace = copy.deepcopy(fixtures.WORKSPACE_RECEIPT)
    preflight = copy.deepcopy(fixtures.PREFLIGHT_RECEIPT)
    case = copy.deepcopy(fixtures.CASE)
    workspace["bindings"]["policyReceiptDigest"] = judgment.digest(policy)
    case["bindings"].update({
        "policyReceiptDigest": judgment.digest(policy),
        "workspaceReceiptDigest": judgment.digest(workspace),
        "transitionPreflightReceiptDigest": judgment.digest(preflight),
    })
    validator.validate(case)
    receipt = judgment.evaluate_judgment(case, policy, workspace, preflight)
    validator.validate(receipt)
    if judgment.digest(receipt) != fixtures.EXPECTED_RECEIPT_DIGEST:
        raise ValueError("administrative judgment golden digest mismatch")
    if receipt["disposition"] != "approve" or receipt["status"] != "eligible-for-mandate-construction":
        raise ValueError("golden judgment must demonstrate bounded autonomous approval")
    if receipt["authority"] != {
        "decisionPrincipal": "persistent-mind",
        "operatorApprovalRequiredForThisJudgment": False,
        "mandateConstructionEligible": True,
        "mandateConstructed": False,
        "executionApplied": False,
        "fallbackTakeoverRequired": False,
        "policyMutationApplied": False,
        "authorityMutationApplied": False,
        "selfExpansionApplied": False,
    }:
        raise ValueError("golden judgment authority boundary changed")
    print("administrative judgment contracts: valid")
    print("golden disposition: approve")
    print("runtime takeover: not required")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"administrative judgment validation failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
