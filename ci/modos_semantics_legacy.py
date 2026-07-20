"""Semantic checks for the original MODOS contract families."""
from __future__ import annotations

from typing import Any

from modos_validation_common import (
    canonical_json_bytes,
    contains_float,
    ingress_batch_digest,
    parse_time,
    sha256_id,
)


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

    elif kind == "AgentConvergenceContract":
        participation = instance["participation"]
        authority = instance["authority"]
        budget = authority["capabilityBudget"]
        if participation["forgeScope"] == "delegated-bounded":
            if authority["authorityCeiling"] != "local-enforcement":
                errors.append("delegated-bounded Forge scope requires local-enforcement authority")
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
