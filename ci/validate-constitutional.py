#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
GOV = ROOT / "modos" / "governance"
SCHEMA = json.loads((ROOT / "modos" / "contracts" / "constitutional-evolution.schema.json").read_text())


def load(name):
    spec = importlib.util.spec_from_file_location(name, GOV / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def validator(name):
    return Draft202012Validator(
        {"$schema": SCHEMA["$schema"], "$defs": SCHEMA["$defs"], "$ref": f"#/$defs/{name}"},
        format_checker=FormatChecker(),
    )


def main():
    Draft202012Validator.check_schema(SCHEMA)
    engine = load("constitutional")
    fixtures = load("constitutional_fixtures")
    failures = []

    def check(name, value, label):
        failures.extend(f"{label}: {error.message}" for error in validator(name).iter_errors(value))

    check("ConstitutionalGovernanceRegistry", fixtures.REGISTRY, "registry")
    check("ConstitutionalAmendmentProposal", fixtures.PROPOSAL, "proposal")
    check("ConstitutionalDeliberation", fixtures.DELIBERATION, "deliberation")
    receipt = engine.gate_amendment(
        fixtures.REGISTRY,
        fixtures.PROPOSAL,
        fixtures.DELIBERATION,
        fixtures.EVALUATED_AT,
    )
    check("ConstitutionalAmendmentReceipt", receipt, "receipt")
    if engine.digest(receipt) != fixtures.EXPECTED:
        failures.append("constitutional golden digest mismatch")

    if failures:
        print("validation failures:", file=sys.stderr)
        for failure in failures:
            print("-", failure, file=sys.stderr)
        return 1
    print("validated 4 constitutional definitions, 1 deterministic engine, 12 adversarial tests, and 1 golden digest")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
