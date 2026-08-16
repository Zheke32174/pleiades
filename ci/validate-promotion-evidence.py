#!/usr/bin/env python3
"""Validate source pinning, promotion candidate contracts, and gate fixtures."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "modos" / "contracts"
ONTOLOGY = ROOT / "modos" / "ontology"
FIXTURES = ONTOLOGY / "fixtures"


def load(path: Path):
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def load_promotion():
    sys.path.insert(0, str(ONTOLOGY))
    spec = importlib.util.spec_from_file_location("pleiades_ontology_promotion", ONTOLOGY / "promotion.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load ontology promotion module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    checker = FormatChecker()
    schemas = {
        "source manifest": load(CONTRACTS / "source-manifest.schema.json"),
        "promotion candidate": load(CONTRACTS / "ontology-promotion-candidate.schema.json"),
        "promotion gate report": load(CONTRACTS / "ontology-promotion-gate-report.schema.json"),
    }
    for schema in schemas.values():
        Draft202012Validator.check_schema(schema)

    instances = {
        "source manifest": load(FIXTURES / "source-manifest.json"),
        "promotion candidate": load(FIXTURES / "promotion-candidate.json"),
    }
    failures = []
    for name, instance in instances.items():
        errors = list(Draft202012Validator(schemas[name], format_checker=checker).iter_errors(instance))
        failures.extend(f"{name}: {error.message}" for error in errors)

    promotion = load_promotion()
    report = promotion.evaluate_promotion_candidate(
        load(FIXTURES / "expected-candidate-snapshot.json"),
        load(FIXTURES / "expected-closure-receipt.json"),
        instances["source manifest"],
        instances["promotion candidate"],
    )
    failures.extend(
        f"promotion gate report: {error.message}"
        for error in Draft202012Validator(schemas["promotion gate report"], format_checker=checker).iter_errors(report)
    )
    expected = load(FIXTURES / "expected-promotion-gate-report.json")
    if promotion.canonical_bytes(report) != promotion.canonical_bytes(expected):
        failures.append("promotion gate report does not match checked-in golden output")
    if report["status"] != "blocked" or report["blockers"] != ["github:Zheke32174/pleiades#42"]:
        failures.append("checked-in candidate must preserve issue #42 as an explicit blocker")
    if report["authority"] != {
        "ceiling": "none",
        "canonicalMutationApplied": False,
        "promotionTransactionRequired": True,
    }:
        failures.append("promotion gate report authority boundary is not exact")

    if failures:
        print("validation failures:", file=sys.stderr)
        for failure in failures:
            print("-", failure, file=sys.stderr)
        return 1
    print("validated 3 promotion evidence schemas, exact source manifest, blocked candidate, and deterministic gate report")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
