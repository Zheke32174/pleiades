#!/usr/bin/env python3
"""Validate delegated machine executive authority contracts and fixtures."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "modos" / "contracts"
GOVERNANCE = ROOT / "modos" / "governance"
FIXTURES = GOVERNANCE / "fixtures"


def load(path: Path):
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def load_executive():
    spec = importlib.util.spec_from_file_location("pleiades_executive_authority", GOVERNANCE / "executive.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load executive authority module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    checker = FormatChecker()
    schemas = {
        "delegated authority grant": load(CONTRACTS / "delegated-authority-grant.schema.json"),
        "executive decision": load(CONTRACTS / "executive-decision.schema.json"),
        "admission mandate": load(CONTRACTS / "admission-mandate.schema.json"),
        "authorization receipt": load(CONTRACTS / "executive-authorization-receipt.schema.json"),
    }
    for schema in schemas.values():
        Draft202012Validator.check_schema(schema)

    instances = {
        "delegated authority grant": load(FIXTURES / "delegated-authority-grant.json"),
        "executive decision": load(FIXTURES / "executive-decision.json"),
        "admission mandate": load(FIXTURES / "admission-mandate.json"),
    }
    failures = []
    for name, instance in instances.items():
        failures.extend(
            f"{name}: {error.message}"
            for error in Draft202012Validator(schemas[name], format_checker=checker).iter_errors(instance)
        )

    executive = load_executive()
    receipt = executive.authorize(
        instances["delegated authority grant"],
        instances["executive decision"],
        instances["admission mandate"],
    )
    failures.extend(
        f"authorization receipt: {error.message}"
        for error in Draft202012Validator(schemas["authorization receipt"], format_checker=checker).iter_errors(receipt)
    )
    expected = load(FIXTURES / "expected-executive-authorization-receipt.json")
    if executive.canonical_bytes(receipt) != executive.canonical_bytes(expected):
        failures.append("executive authorization receipt does not match checked-in golden output")
    if receipt["status"] != "authorized":
        failures.append("bounded delegated Mind decision was not authorized")
    if receipt["authority"] != {
        "decisionPrincipal": "delegated-mind",
        "executorDecisionAuthority": "none",
        "constitutionalMutationApplied": False,
        "authorityExpansionApplied": False,
        "executionStillPending": True,
    }:
        failures.append("executive authorization receipt authority boundary is not exact")

    if failures:
        print("validation failures:", file=sys.stderr)
        for failure in failures:
            print("-", failure, file=sys.stderr)
        return 1
    print("validated 4 executive authority schemas and one autonomous bounded admission authorization")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
