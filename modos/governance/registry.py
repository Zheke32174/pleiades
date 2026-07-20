#!/usr/bin/env python3
"""Deterministic delegated-authority registry closure.

This module resolves effective grant state from immutable grants and lifecycle
events. It does not issue, suspend, resume, revoke, or enlarge a grant.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

API_VERSION = "modos.pleiades/v1alpha1"


class AuthorityRegistryError(ValueError):
    pass


def _reject_float(value: str) -> None:
    raise AuthorityRegistryError(f"floating-point values are forbidden: {value}")


def _reject_constant(value: str) -> None:
    raise AuthorityRegistryError(f"non-finite JSON constant is forbidden: {value}")


def _no_duplicate_keys(pairs: Iterable[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise AuthorityRegistryError(f"duplicate JSON key is forbidden: {key}")
        result[key] = value
    return result


def load_json_strict(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle, parse_float=_reject_float, parse_constant=_reject_constant, object_pairs_hook=_no_duplicate_keys)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_bytes(value)).hexdigest()


def _time(value: Any, field: str) -> datetime:
    if not isinstance(value, str):
        raise AuthorityRegistryError(f"{field} must be an RFC3339 timestamp")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AuthorityRegistryError(f"{field} must be an RFC3339 timestamp") from exc


def _grant_identity(grant: dict[str, Any]) -> tuple[str, int]:
    grant_id = grant.get("grantId")
    generation = grant.get("generation")
    if not isinstance(grant_id, str) or not grant_id:
        raise AuthorityRegistryError("grantId is required")
    if not isinstance(generation, int) or isinstance(generation, bool) or generation < 1:
        raise AuthorityRegistryError(f"grant {grant_id} generation must be positive")
    subject = grant.get("subject")
    if not isinstance(subject, dict) or subject.get("principalType") != "mind" or not subject.get("principalRef"):
        raise AuthorityRegistryError(f"grant {grant_id} must target a persistent Mind principal")
    if grant.get("delegation", {}).get("maySelfExpand") is not False:
        raise AuthorityRegistryError(f"grant {grant_id} cannot permit self-expansion")
    if grant.get("delegation", {}).get("revocable") is not True:
        raise AuthorityRegistryError(f"grant {grant_id} must be revocable")
    if "*" in grant.get("domains", []) or "*" in grant.get("permissions", []):
        raise AuthorityRegistryError(f"grant {grant_id} wildcard authority is forbidden")
    start = _time(grant.get("validity", {}).get("notBefore"), f"grant {grant_id} validity.notBefore")
    end = _time(grant.get("validity", {}).get("notAfter"), f"grant {grant_id} validity.notAfter")
    if start >= end:
        raise AuthorityRegistryError(f"grant {grant_id} validity interval is invalid")
    return grant_id, generation


def close_registry(registry: dict[str, Any]) -> dict[str, Any]:
    if registry.get("apiVersion") != API_VERSION or registry.get("kind") != "AuthorityRegistry":
        raise AuthorityRegistryError("unsupported authority registry envelope")
    if registry.get("authority") != {
        "registryMayIssueGrants": False,
        "registryMayAlterConstitution": False,
        "closureOnly": True,
    }:
        raise AuthorityRegistryError("authority registry boundary is not exact")
    evaluation = _time(registry.get("evaluationAt"), "registry evaluationAt")
    grants = registry.get("grants")
    events = registry.get("events")
    if not isinstance(grants, list) or not grants or not isinstance(events, list) or not events:
        raise AuthorityRegistryError("registry grants and events must be nonempty")
    grant_map: dict[tuple[str, int], dict[str, Any]] = {}
    latest_generation: dict[str, int] = {}
    for grant in grants:
        identity = _grant_identity(grant)
        if identity in grant_map:
            raise AuthorityRegistryError(f"duplicate grant generation: {identity[0]} generation {identity[1]}")
        grant_map[identity] = grant
        if identity[1] <= latest_generation.get(identity[0], 0):
            raise AuthorityRegistryError(f"grant generations must be strictly increasing for {identity[0]}")
        latest_generation[identity[0]] = identity[1]

    event_ids: set[str] = set()
    grouped: dict[tuple[str, int], list[dict[str, Any]]] = {identity: [] for identity in grant_map}
    for event in events:
        if event.get("apiVersion") != API_VERSION or event.get("kind") != "AuthorityLifecycleEvent":
            raise AuthorityRegistryError("unsupported authority lifecycle event envelope")
        event_id = event.get("eventId")
        if not isinstance(event_id, str) or not event_id or event_id in event_ids:
            raise AuthorityRegistryError("authority event ids must be nonempty and unique")
        event_ids.add(event_id)
        identity = (event.get("grantRef"), event.get("grantGeneration"))
        if identity not in grant_map:
            raise AuthorityRegistryError(f"authority event {event_id} references an unknown grant generation")
        actor = event.get("actor")
        if not isinstance(actor, dict) or actor.get("principalType") not in {"human", "institution", "recovery-quorum", "service"}:
            raise AuthorityRegistryError(f"authority event {event_id} actor must be external")
        if actor.get("principalRef") == grant_map[identity]["subject"]["principalRef"]:
            raise AuthorityRegistryError(f"authority event {event_id} cannot be self-issued by the subject Mind")
        _time(event.get("effectiveAt"), f"authority event {event_id} effectiveAt")
        grouped[identity].append(event)

    active: list[str] = []
    inactive: list[dict[str, str]] = []
    for identity, grant in sorted(grant_map.items()):
        grant_id, generation = identity
        state = "unissued"
        terminal = False
        ordered = sorted(grouped[identity], key=lambda item: (_time(item["effectiveAt"], "event effectiveAt"), item["eventId"]))
        seen_times: set[str] = set()
        for event in ordered:
            if event["effectiveAt"] in seen_times:
                raise AuthorityRegistryError(f"grant {grant_id} generation {generation} has ambiguous same-time events")
            seen_times.add(event["effectiveAt"])
        if not ordered or ordered[0]["eventType"] != "issued":
            raise AuthorityRegistryError(f"grant {grant_id} generation {generation} lacks an initial issued event")
        for event in ordered:
            if _time(event["effectiveAt"], "event effectiveAt") > evaluation:
                continue
            event_type = event["eventType"]
            if terminal:
                raise AuthorityRegistryError(f"grant {grant_id} generation {generation} has events after revocation")
            if event_type == "issued":
                if state != "unissued":
                    raise AuthorityRegistryError(f"grant {grant_id} generation {generation} is issued more than once")
                state = "active"
            elif event_type == "suspended":
                if state != "active":
                    raise AuthorityRegistryError(f"grant {grant_id} generation {generation} cannot suspend from {state}")
                state = "suspended"
            elif event_type == "resumed":
                if state != "suspended":
                    raise AuthorityRegistryError(f"grant {grant_id} generation {generation} cannot resume from {state}")
                state = "active"
            elif event_type == "revoked":
                if state not in {"active", "suspended"}:
                    raise AuthorityRegistryError(f"grant {grant_id} generation {generation} cannot revoke from {state}")
                state = "revoked"
                terminal = True
            else:
                raise AuthorityRegistryError(f"unsupported authority event type: {event_type}")
        start = _time(grant["validity"]["notBefore"], "grant validity.notBefore")
        end = _time(grant["validity"]["notAfter"], "grant validity.notAfter")
        ref = f"{grant_id}@{generation}"
        if evaluation < start:
            inactive.append({"grantRef": ref, "reason": "not-yet-valid"})
        elif evaluation >= end:
            inactive.append({"grantRef": ref, "reason": "expired"})
        elif state == "active":
            active.append(ref)
        else:
            inactive.append({"grantRef": ref, "reason": state})
    return {
        "apiVersion": API_VERSION,
        "kind": "AuthorityRegistryReceipt",
        "registryId": registry["registryId"],
        "registryDigest": digest(registry),
        "evaluationAt": registry["evaluationAt"],
        "activeGrantRefs": sorted(active),
        "inactiveGrants": sorted(inactive, key=lambda item: item["grantRef"]),
        "checks": [
            {"name": "unique-grant-generations", "status": "pass"},
            {"name": "external-lifecycle-actors", "status": "pass"},
            {"name": "no-self-issuance", "status": "pass"},
            {"name": "valid-lifecycle-transitions", "status": "pass"},
            {"name": "revocation-terminal", "status": "pass"},
            {"name": "deterministic-evaluation-time", "status": "pass"},
        ],
        "authority": {"ceiling": "none", "grantMutationApplied": False},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--out-receipt", type=Path, required=True)
    args = parser.parse_args()
    try:
        receipt = close_registry(load_json_strict(args.registry))
        args.out_receipt.parent.mkdir(parents=True, exist_ok=True)
        args.out_receipt.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(len(receipt["activeGrantRefs"]))
        return 0
    except (OSError, json.JSONDecodeError, AuthorityRegistryError) as exc:
        print(f"authority registry closure failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
