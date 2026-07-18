#!/usr/bin/env python3
"""Validate MODOS JSON Schemas plus adversarial semantic fixtures."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def semantic_errors(instance: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    kind = instance.get("kind")

    if kind == "CapabilityLease":
        meta = instance["metadata"]
        issued = parse_time(meta["issuedAt"])
        expires = parse_time(meta["expiresAt"])
        if expires <= issued:
            errors.append("capability lease expiresAt must be after issuedAt")
        if "notBefore" in meta:
            not_before = parse_time(meta["notBefore"])
            if not issued <= not_before < expires:
                errors.append("capability lease notBefore must be within the lease interval")
        state = instance["state"]
        max_uses = instance["capability"].get("maxUses")
        if max_uses is not None and state["uses"] > max_uses:
            errors.append("capability lease uses exceeds maxUses")

    elif kind == "WorkspaceContribution":
        meta = instance["metadata"]
        if meta["stage"] == "first-pass" and meta.get("observedContributionRefs"):
            errors.append("first-pass contribution must not observe other contributions")
        contribution_type = instance["contribution"]["type"]
        dissent_status = instance["epistemics"]["dissentStatus"]
        if contribution_type == "dissent" and dissent_status not in {"minority", "formal-dissent"}:
            errors.append("dissent contribution must preserve a dissent status")
        if instance["security"]["authorityCeiling"] not in {"none", "proposal"}:
            errors.append("workspace contribution exceeds proposal authority")

    elif kind == "ExperienceRecord":
        if instance["security"]["authorityCeiling"] != "none":
            errors.append("experience records are evidence and must have no action authority")
        if instance["recordType"] == "promotion-candidate":
            if not instance["evidence"]["independentVerification"]:
                errors.append("promotion candidate requires independent verification")
            if instance["security"]["trainingDisposition"] == "steward-approved":
                errors.append("a record cannot self-assert steward approval")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contracts", type=Path, default=Path("modos/contracts"))
    args = parser.parse_args()

    contracts = args.contracts.resolve()
    fixture_bundle = load_json(contracts / "canon-wave-v1.fixtures.json")
    checker = FormatChecker()
    failures: list[str] = []

    schemas: dict[str, dict[str, Any]] = {}
    for schema_path in sorted(contracts.glob("*.schema.json")):
        schema = load_json(schema_path)
        Draft202012Validator.check_schema(schema)
        schemas[schema_path.name] = schema
        print(f"schema ok: {schema_path.name}")

    for case in fixture_bundle["cases"]:
        schema_name = case["schema"]
        instance_name = case["name"]
        expected_valid = bool(case["valid"])
        schema = schemas[schema_name]
        instance = case["instance"]
        validator = Draft202012Validator(schema, format_checker=checker)
        schema_errors = sorted(validator.iter_errors(instance), key=lambda err: list(err.path))
        semantics = semantic_errors(instance) if not schema_errors else []
        actual_valid = not schema_errors and not semantics

        if actual_valid != expected_valid:
            detail = [error.message for error in schema_errors] + semantics
            failures.append(
                f"{instance_name}: expected valid={expected_valid}, got valid={actual_valid}; "
                + "; ".join(detail)
            )
        else:
            outcome = "accepted" if actual_valid else "rejected"
            print(f"fixture {outcome}: {instance_name}")

    if failures:
        print("contract validation failures:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print(f"validated {len(schemas)} schemas and {len(fixture_bundle['cases'])} fixtures")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
