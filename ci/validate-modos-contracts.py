#!/usr/bin/env python3
"""Validate MODOS JSON Schemas plus adversarial semantic fixtures."""
from __future__ import annotations

import argparse
import copy
import hashlib
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


def canonical_json_bytes(value: Any) -> bytes:
    """MODOS canonical JSON v1 for finite, integer-only contract values."""
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def contains_float(value: Any) -> bool:
    if isinstance(value, float):
        return True
    if isinstance(value, dict):
        return any(contains_float(item) for item in value.values())
    if isinstance(value, list):
        return any(contains_float(item) for item in value)
    return False


def sha256_id(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def ingress_batch_digest(instance: dict[str, Any]) -> str:
    material = copy.deepcopy(instance)
    material["integrity"]["batchDigest"] = ""
    if "signature" in material["proof"]:
        material["proof"]["signature"] = ""
    return sha256_id(canonical_json_bytes(material))


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
        if contribution_type == "dissent" and dissent_status not in {
            "minority",
            "formal-dissent",
        }:
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

    elif kind == "AgentConvergenceContract":
        participation = instance["participation"]
        authority = instance["authority"]
        budget = authority["capabilityBudget"]
        if participation["forgeScope"] == "delegated-bounded":
            if authority["authorityCeiling"] != "local-enforcement":
                errors.append(
                    "delegated-bounded Forge scope requires local-enforcement authority"
                )
            if budget["maxActions"] < 1:
                errors.append("delegated-bounded agent requires a nonzero action budget")
        if authority["authorityCeiling"] in {"none", "proposal"}:
            if budget["maxActions"] != 0 or budget["allowedCapabilities"]:
                errors.append("proposal-side agent cannot carry an action capability budget")
        if instance["verification"]["verifierRef"] == instance["metadata"]["agentId"]:
            errors.append("agent cannot be its only verifier")

    elif kind == "ObservationIngressBatch":
        meta = instance["metadata"]
        created = parse_time(meta["createdAt"])
        expires = parse_time(meta["expiresAt"])
        if expires <= created:
            errors.append("ingress batch expiresAt must be after createdAt")
        if "notBefore" in meta:
            not_before = parse_time(meta["notBefore"])
            if not created <= not_before < expires:
                errors.append("ingress batch notBefore must be within its interval")

        delivery = instance["delivery"]
        events = instance["events"]
        first = delivery["firstSequence"]
        last = delivery["lastSequence"]
        count = delivery["eventCount"]
        if count != len(events):
            errors.append("ingress batch eventCount must equal events length")
        if last - first + 1 != count:
            errors.append("ingress batch delivery range must be contiguous and match eventCount")

        expected_sequences = list(range(first, last + 1))
        actual_sequences = [event["deliverySequence"] for event in events]
        if actual_sequences != expected_sequences:
            errors.append("ingress event deliverySequence values must exactly cover the ordered range")

        encoded_bytes = 0
        seen_event_ids: set[str] = set()
        for event in events:
            record = event["record"]
            if contains_float(record):
                errors.append("ingress records cannot contain floating-point values")
                continue
            record_bytes = canonical_json_bytes(record)
            encoded_bytes += len(record_bytes)
            if event["eventDigest"] != sha256_id(record_bytes):
                errors.append(
                    "ingress event digest mismatch for delivery sequence "
                    f"{event['deliverySequence']}"
                )
            record_event_id = record.get("event_id", record.get("eventId"))
            if record_event_id is not None and record_event_id != event["eventId"]:
                errors.append(
                    "ingress event ID does not match record at delivery sequence "
                    f"{event['deliverySequence']}"
                )
            if event["eventId"] in seen_event_ids:
                errors.append("ingress batch contains a duplicate event ID")
            seen_event_ids.add(event["eventId"])

        if delivery["encodedBytes"] != encoded_bytes:
            errors.append("ingress batch encodedBytes must equal canonical record byte total")
        if instance["integrity"]["batchDigest"] != ingress_batch_digest(instance):
            errors.append("ingress batch digest does not match canonical batch material")

    elif kind == "ObservationIngressReceipt":
        meta = instance["metadata"]
        delivery = instance["delivery"]
        if delivery["lastSequence"] - delivery["firstSequence"] + 1 != delivery["eventCount"]:
            errors.append("ingress receipt range must be contiguous and match eventCount")
        if instance["authentication"]["authenticatedPrincipalId"] != meta["producerPrincipalId"]:
            errors.append("ingress receipt authenticated principal must match producer principal")

    elif kind == "DeliveryStreamState":
        meta = instance["metadata"]
        state = instance["state"]
        if parse_time(meta["observedAt"]) < parse_time(meta["createdAt"]):
            errors.append("delivery stream observedAt cannot precede createdAt")
        acknowledged = state["acknowledgedHighWater"]
        queued = state["queuedHighWater"]
        next_sequence = state["nextSequence"]
        if acknowledged > queued:
            errors.append("acknowledged high water cannot exceed queued high water")
        if next_sequence != queued + 1:
            errors.append("next delivery sequence must equal queued high water plus one")
        if state["pendingEvents"] != queued - acknowledged:
            errors.append("pendingEvents must equal queued minus acknowledged high water")
        if state["pendingEvents"] == 0 and "oldestPendingAt" in state:
            errors.append("empty delivery stream must not claim an oldest pending time")
        if acknowledged > 0 and "lastReceiptRef" not in state:
            errors.append("acknowledged delivery state requires lastReceiptRef")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contracts", type=Path, default=Path("modos/contracts"))
    args = parser.parse_args()

    contracts = args.contracts.resolve()
    checker = FormatChecker()
    failures: list[str] = []

    schemas: dict[str, dict[str, Any]] = {}
    for schema_path in sorted(contracts.glob("*.schema.json")):
        schema = load_json(schema_path)
        Draft202012Validator.check_schema(schema)
        schemas[schema_path.name] = schema
        print(f"schema ok: {schema_path.name}")

    fixture_paths = sorted(contracts.glob("*.fixtures.json"))
    if not fixture_paths:
        print("no contract fixture bundles found", file=sys.stderr)
        return 1

    case_count = 0
    for fixture_path in fixture_paths:
        fixture_bundle = load_json(fixture_path)
        cases = fixture_bundle.get("cases")
        if not isinstance(cases, list) or not cases:
            failures.append(f"{fixture_path.name}: cases must be a nonempty list")
            continue
        print(f"fixture bundle: {fixture_path.name}")
        for case in cases:
            case_count += 1
            schema_name = case["schema"]
            instance_name = case["name"]
            expected_valid = bool(case["valid"])
            schema = schemas.get(schema_name)
            if schema is None:
                failures.append(
                    f"{fixture_path.name}/{instance_name}: unknown schema {schema_name}"
                )
                continue
            instance = case["instance"]
            validator = Draft202012Validator(schema, format_checker=checker)
            schema_errors = sorted(
                validator.iter_errors(instance), key=lambda error: list(error.path)
            )
            semantics = semantic_errors(instance) if not schema_errors else []
            actual_valid = not schema_errors and not semantics

            if actual_valid != expected_valid:
                detail = [error.message for error in schema_errors] + semantics
                failures.append(
                    f"{fixture_path.name}/{instance_name}: expected valid={expected_valid}, "
                    f"got valid={actual_valid}; " + "; ".join(detail)
                )
            else:
                outcome = "accepted" if actual_valid else "rejected"
                print(f"fixture {outcome}: {instance_name}")

    if failures:
        print("contract validation failures:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print(
        f"validated {len(schemas)} schemas, {len(fixture_paths)} bundles, "
        f"and {case_count} fixtures"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
