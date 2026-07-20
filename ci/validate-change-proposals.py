#!/usr/bin/env python3
"""Validate proposal-only ontology changes and their authority boundary."""
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "modos" / "contracts"


def load(path):
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def semantic_errors(proposal):
    errors = []
    operations = proposal["operations"]
    identities = set()
    for index, operation in enumerate(operations):
        identity = json.dumps(operation, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        if identity in identities:
            errors.append(f"operation {index} duplicates an earlier operation")
        identities.add(identity)
        if operation["op"] in {"link", "unlink"}:
            if not operation.get("relationType") or not operation.get("targetRef"):
                errors.append(f"operation {index} relation requires relationType and targetRef")
        elif operation.get("relationType") or operation.get("targetRef"):
            errors.append(f"operation {index} non-relation cannot carry relationType or targetRef")
        if operation["op"] in {"create", "update"} and not operation.get("payload"):
            errors.append(f"operation {index} {operation['op']} requires a non-empty payload")
        if operation["op"] in {"delete", "link", "unlink"} and operation.get("payload"):
            errors.append(f"operation {index} {operation['op']} cannot carry payload")
    authority = proposal["authority"]
    if authority != {
        "ceiling": "none",
        "canonicalMutation": "forbidden",
        "promotionTransactionRequired": True,
        "selfPromotionAllowed": False,
    }:
        errors.append("proposal authority boundary is not exact")
    if proposal["objectFamily"] == "Model":
        for effect in proposal["expectedSemanticEffects"]:
            lowered = effect.lower()
            if "whole mind" in lowered or "is the mind" in lowered:
                errors.append("Model cannot be declared the whole Mind")
    return errors


def main():
    schema = load(CONTRACTS / "change-proposal.schema.json")
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    bundle = load(CONTRACTS / "change-proposal.fixtures.json")
    failures = []
    for case in bundle["cases"]:
        instance = case["instance"]
        shape = list(validator.iter_errors(instance))
        semantics = semantic_errors(instance) if not shape else []
        actual = not shape and not semantics
        if actual != case["valid"]:
            messages = [error.message for error in shape] + semantics
            failures.append(f"{case['name']}: expected {case['valid']}, got {actual}: {'; '.join(messages)}")
        else:
            print("case", "accepted:" if actual else "rejected:", case["name"])
    if failures:
        print("validation failures:", file=sys.stderr)
        for failure in failures:
            print("-", failure, file=sys.stderr)
        return 1
    print(f"validated ChangeProposal schema and {len(bundle['cases'])} semantic cases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
