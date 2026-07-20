#!/usr/bin/env python3
"""Validate proposal ingress and the deterministic ontology compiler slice."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "modos" / "contracts"
ONTOLOGY = ROOT / "modos" / "ontology"


def load(path: Path):
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


def load_compiler():
    spec = importlib.util.spec_from_file_location("pleiades_ontology_compiler", ONTOLOGY / "compiler.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load ontology compiler")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main():
    checker = FormatChecker()
    proposal_schema = load(CONTRACTS / "change-proposal.schema.json")
    snapshot_schema = load(CONTRACTS / "ontology-snapshot.schema.json")
    receipt_schema = load(CONTRACTS / "ontology-closure-receipt.schema.json")
    projection_schema = load(CONTRACTS / "ontology-projection-bundle.schema.json")
    domain_schema = load(CONTRACTS / "domain-object.schema.json")
    for schema in (proposal_schema, snapshot_schema, receipt_schema, projection_schema):
        Draft202012Validator.check_schema(schema)

    proposal_validator = Draft202012Validator(proposal_schema, format_checker=checker)
    bundle = load(CONTRACTS / "change-proposal.fixtures.json")
    failures = []
    for case in bundle["cases"]:
        instance = case["instance"]
        shape = list(proposal_validator.iter_errors(instance))
        semantics = semantic_errors(instance) if not shape else []
        actual = not shape and not semantics
        if actual != case["valid"]:
            messages = [error.message for error in shape] + semantics
            failures.append(f"{case['name']}: expected {case['valid']}, got {actual}: {'; '.join(messages)}")
        else:
            print("case", "accepted:" if actual else "rejected:", case["name"])

    compiler = load_compiler()
    snapshot = load(ONTOLOGY / "fixtures" / "seed-snapshot.json")
    proposal = load(ONTOLOGY / "fixtures" / "link-workspace.proposal.json")
    registry = Registry().with_resource(
        domain_schema["$id"], Resource.from_contents(domain_schema)
    )
    snapshot_validator = Draft202012Validator(
        snapshot_schema,
        registry=registry,
        format_checker=checker,
    )
    snapshot_errors = list(snapshot_validator.iter_errors(snapshot))
    if snapshot_errors:
        failures.extend(f"seed snapshot: {error.message}" for error in snapshot_errors)
    else:
        result, receipt = compiler.compile_proposal(snapshot, proposal)
        result_errors = list(snapshot_validator.iter_errors(result))
        receipt_errors = list(Draft202012Validator(receipt_schema, format_checker=checker).iter_errors(receipt))
        failures.extend(f"compiled snapshot: {error.message}" for error in result_errors)
        failures.extend(f"closure receipt: {error.message}" for error in receipt_errors)
        if compiler.snapshot_digest(result) != receipt["resultSnapshotDigest"]:
            failures.append("closure receipt resultSnapshotDigest does not match compiled snapshot")
        if not failures:
            projection_spec = importlib.util.spec_from_file_location("pleiades_ontology_projection", ONTOLOGY / "projection.py")
            if projection_spec is None or projection_spec.loader is None:
                failures.append("cannot load ontology projection module")
            else:
                projection_module = importlib.util.module_from_spec(projection_spec)
                sys.modules[projection_spec.name] = projection_module
                projection_spec.loader.exec_module(projection_module)
                projection_bundle = projection_module.build_projection_bundle(result, receipt)
                projection_errors = list(Draft202012Validator(projection_schema, format_checker=checker).iter_errors(projection_bundle))
                failures.extend(f"projection bundle: {error.message}" for error in projection_errors)
                if not failures:
                    print("compiler accepted: deterministic closed snapshot, receipt, and read projection")

    if failures:
        print("validation failures:", file=sys.stderr)
        for failure in failures:
            print("-", failure, file=sys.stderr)
        return 1
    print(f"validated 4 ontology schemas, {len(bundle['cases'])} proposal cases, and one compiled closure receipt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
