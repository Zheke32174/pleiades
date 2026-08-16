#!/usr/bin/env python3
"""Validate the operator-input contract, fixture, compiler, and golden receipt."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "modos" / "handoff" / "intake.py"
SPEC = importlib.util.spec_from_file_location("pleiades_operator_intake_validator", MODULE_PATH)
assert SPEC and SPEC.loader
intake = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = intake
SPEC.loader.exec_module(intake)


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    schema = load(ROOT / "modos" / "contracts" / "operator-input-candidate.schema.json")
    candidate = load(ROOT / "modos" / "handoff" / "fixtures" / "operator-input-candidate.synthetic-ready.json")
    expected = load(ROOT / "modos" / "handoff" / "fixtures" / "expected-operator-input-compilation-receipt.json")

    Draft202012Validator.check_schema(schema)
    errors = list(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(candidate))
    if errors:
        for error in errors:
            print(error.message, file=sys.stderr)
        return 1

    actual = intake.compile_candidate(candidate, schema)
    if intake.canonical_bytes(actual) != intake.canonical_bytes(expected):
        print("operator input golden receipt mismatch", file=sys.stderr)
        return 1
    if actual["state"] != "ready-to-derive-next-progression":
        print("synthetic candidate did not reach expected preparation state", file=sys.stderr)
        return 1
    if actual["authority"] != {
        "ceiling": "none",
        "proposalOnly": True,
        "canonicalMutationApplied": False,
        "liveExecutionApplied": False,
        "historyRewriteApplied": False,
        "grantIssued": False,
    }:
        print("operator input authority boundary is not exact", file=sys.stderr)
        return 1

    print(f"validated operator input compiler and golden receipt: {actual['receiptDigest']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
