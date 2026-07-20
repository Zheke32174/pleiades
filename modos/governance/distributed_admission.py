#!/usr/bin/env python3
"""Deterministic distributed-admission plan closure.

The engine validates a capability-bound, replay-resistant, staged rollout plan.
It emits a closure receipt only. It does not contact nodes or execute rollout.
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
CEILING_ORDER = {"observe-only": 0, "local-enforcement": 1, "distributed-stage": 2}


class DistributedAdmissionError(ValueError):
    pass


def _reject_float(value):
    raise DistributedAdmissionError(f"floating-point values are forbidden: {value}")


def _reject_constant(value):
    raise DistributedAdmissionError(f"non-finite JSON constant is forbidden: {value}")


def _pairs(items: Iterable[tuple[str, Any]]):
    result = {}
    for key, value in items:
        if key in result:
            raise DistributedAdmissionError(f"duplicate JSON key is forbidden: {key}")
        result[key] = value
    return result


def load_json_strict(path: Path):
    return json.loads(path.read_text(), parse_float=_reject_float, parse_constant=_reject_constant, object_pairs_hook=_pairs)


def canonical_bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value):
    return "sha256:" + hashlib.sha256(canonical_bytes(value)).hexdigest()


def _sha(value, field):
    if not isinstance(value, str) or len(value) != 71 or not value.startswith("sha256:"):
        raise DistributedAdmissionError(f"{field} must be sha256-bound")


def _time(value, field):
    if not isinstance(value, str):
        raise DistributedAdmissionError(f"{field} must be RFC3339")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DistributedAdmissionError(f"{field} must be RFC3339") from exc


def close_rollout(registry: dict[str, Any], plan: dict[str, Any], history: list[dict[str, Any]]) -> dict[str, Any]:
    if registry.get("apiVersion") != API_VERSION or registry.get("kind") != "NodeCapabilityRegistry":
        raise DistributedAdmissionError("unsupported node capability registry")
    if registry.get("authority") != {"closureOnly": True, "mayIssueCapabilities": False, "mayExecute": False}:
        raise DistributedAdmissionError("node registry authority boundary is not exact")
    nodes = registry.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        raise DistributedAdmissionError("node registry must be nonempty")
    node_map = {}
    principals = set()
    keys = set()
    for node in nodes:
        node_id = node.get("nodeId")
        if not isinstance(node_id, str) or not node_id or node_id in node_map:
            raise DistributedAdmissionError("node ids must be nonempty and unique")
        node_map[node_id] = node
        for field in ("hardwareDigest", "serviceIdentityDigest", "keyDigest"):
            _sha(node.get(field), f"{node_id}.{field}")
        principal = node.get("servicePrincipalRef")
        if not isinstance(principal, str) or not principal or principal in principals:
            raise DistributedAdmissionError("node service principals must be unique")
        principals.add(principal)
        if node["keyDigest"] in keys:
            raise DistributedAdmissionError("node key identities must be unique")
        keys.add(node["keyDigest"])
        for field in ("capabilities", "writeScopes"):
            values = node.get(field)
            if not isinstance(values, list) or not values or len(set(values)) != len(values) or "*" in values:
                raise DistributedAdmissionError(f"{node_id}.{field} must be bounded and unique")
        if node.get("authorityCeiling") not in CEILING_ORDER:
            raise DistributedAdmissionError(f"{node_id} authority ceiling is unsupported")
        partition = node.get("partitionPolicy")
        if not isinstance(partition, dict) or partition.get("mode") not in {"fail-closed", "limited-local"}:
            raise DistributedAdmissionError(f"{node_id} partition policy is unsupported")
        if not isinstance(partition.get("maxOfflineSeconds"), int) or partition["maxOfflineSeconds"] < 0:
            raise DistributedAdmissionError(f"{node_id} maxOfflineSeconds is invalid")
        if partition["mode"] == "fail-closed" and partition["maxOfflineSeconds"] != 0:
            raise DistributedAdmissionError(f"{node_id} fail-closed partition policy must have zero offline allowance")
        if partition["mode"] == "limited-local" and node["authorityCeiling"] == "distributed-stage":
            raise DistributedAdmissionError(f"{node_id} distributed-stage authority cannot remain active while partitioned")

    if plan.get("apiVersion") != API_VERSION or plan.get("kind") != "DistributedRolloutPlan":
        raise DistributedAdmissionError("unsupported distributed rollout plan")
    for field in ("authorizationReceiptDigest", "mandateDigest", "targetDigest", "predecessorDigest", "rollbackDigest"):
        _sha(plan.get(field), f"plan.{field}")
    if plan["rollbackDigest"] != plan["predecessorDigest"]:
        raise DistributedAdmissionError("rollout rollback digest must equal predecessor digest")
    created = _time(plan.get("createdAt"), "plan createdAt")
    expires = _time(plan.get("expiresAt"), "plan expiresAt")
    if created >= expires:
        raise DistributedAdmissionError("rollout plan validity interval is invalid")
    replay = plan.get("replayNonce")
    idempotency = plan.get("idempotencyKey")
    if not isinstance(replay, str) or len(replay) < 16:
        raise DistributedAdmissionError("replay nonce is too weak")
    if not isinstance(idempotency, str) or len(idempotency) < 16:
        raise DistributedAdmissionError("idempotency key is too weak")
    plan_digest = digest(plan)
    for prior in history:
        if prior.get("replayNonce") == replay:
            if prior.get("planDigest") == plan_digest and prior.get("idempotencyKey") == idempotency:
                return {
                    "apiVersion": API_VERSION,
                    "kind": "DistributedRolloutReceipt",
                    "planId": plan["planId"],
                    "status": "idempotent-replay",
                    "planDigest": plan_digest,
                    "registryDigest": digest(registry),
                    "replayNonce": replay,
                    "idempotencyKey": idempotency,
                    "stageSchedule": prior.get("stageSchedule", []),
                    "rollbackGroups": prior.get("rollbackGroups", []),
                    "checks": [{"name": "exact-idempotent-replay", "status": "pass"}],
                    "authority": {"executionApplied": False, "canonicalMutationApplied": False, "executorDecisionAuthority": "none"},
                }
            raise DistributedAdmissionError("replay nonce was already used by a different rollout")
        if prior.get("idempotencyKey") == idempotency and prior.get("planDigest") != plan_digest:
            raise DistributedAdmissionError("idempotency key collision with a different rollout")

    constraints = plan.get("constraints")
    if not isinstance(constraints, dict) or constraints.get("automaticRollback") is not True or constraints.get("requireCanary") is not True:
        raise DistributedAdmissionError("rollout must require canary and automatic rollback")
    max_parallel = constraints.get("maxParallelNodes")
    if not isinstance(max_parallel, int) or max_parallel < 1:
        raise DistributedAdmissionError("maxParallelNodes must be positive")
    capability = plan.get("executorCapability")
    if not isinstance(capability, str) or not capability or "*" in capability:
        raise DistributedAdmissionError("executorCapability must be bounded")
    required_scope = plan.get("writeScope")
    if not isinstance(required_scope, str) or not required_scope or required_scope == "*":
        raise DistributedAdmissionError("writeScope must be bounded")
    required_ceiling = plan.get("requiredAuthorityCeiling")
    if required_ceiling not in CEILING_ORDER:
        raise DistributedAdmissionError("required authority ceiling is unsupported")
    stages = plan.get("stages")
    if not isinstance(stages, list) or not stages:
        raise DistributedAdmissionError("rollout stages must be nonempty")
    ordered = sorted(stages, key=lambda stage: stage.get("order", -1))
    if [stage.get("order") for stage in ordered] != list(range(1, len(ordered) + 1)):
        raise DistributedAdmissionError("rollout stage order must be contiguous from one")
    if ordered[0].get("canary") is not True:
        raise DistributedAdmissionError("first rollout stage must be canary")
    if any(stage.get("canary") is True for stage in ordered[1:]):
        raise DistributedAdmissionError("only the first rollout stage may be canary")

    scheduled = set()
    stage_schedule = []
    rollback_groups = []
    for stage in ordered:
        stage_id = stage.get("stageId")
        if not isinstance(stage_id, str) or not stage_id:
            raise DistributedAdmissionError("stageId is required")
        _sha(stage.get("healthGateDigest"), f"{stage_id}.healthGateDigest")
        stage_nodes = stage.get("nodeRefs")
        if not isinstance(stage_nodes, list) or not stage_nodes or len(set(stage_nodes)) != len(stage_nodes):
            raise DistributedAdmissionError(f"{stage_id} nodeRefs must be nonempty and unique")
        if len(stage_nodes) > max_parallel and stage.get("canary") is not True:
            raise DistributedAdmissionError(f"{stage_id} exceeds maxParallelNodes")
        for node_id in stage_nodes:
            if node_id in scheduled:
                raise DistributedAdmissionError(f"node {node_id} appears in more than one stage")
            scheduled.add(node_id)
            node = node_map.get(node_id)
            if node is None:
                raise DistributedAdmissionError(f"rollout references unknown node: {node_id}")
            if capability not in node["capabilities"]:
                raise DistributedAdmissionError(f"{node_id} lacks executor capability")
            if "rollback.exact" not in node["capabilities"]:
                raise DistributedAdmissionError(f"{node_id} lacks exact rollback capability")
            if required_scope not in node["writeScopes"]:
                raise DistributedAdmissionError(f"{node_id} lacks required write scope")
            if CEILING_ORDER[node["authorityCeiling"]] < CEILING_ORDER[required_ceiling]:
                raise DistributedAdmissionError(f"{node_id} authority ceiling is insufficient")
        stage_schedule.append({
            "stageId": stage_id,
            "order": stage["order"],
            "canary": stage["canary"],
            "nodeRefs": sorted(stage_nodes),
            "healthGateDigest": stage["healthGateDigest"],
            "advanceOnlyOnHealthPass": True,
        })
        rollback_groups.append({
            "stageId": stage_id,
            "nodeRefs": sorted(stage_nodes),
            "rollbackDigest": plan["rollbackDigest"],
            "coordinated": True,
        })
    if scheduled != set(node_map):
        missing = sorted(set(node_map) - scheduled)
        raise DistributedAdmissionError("rollout does not cover registered target nodes: " + ", ".join(missing))
    return {
        "apiVersion": API_VERSION,
        "kind": "DistributedRolloutReceipt",
        "planId": plan["planId"],
        "status": "closed",
        "planDigest": plan_digest,
        "registryDigest": digest(registry),
        "replayNonce": replay,
        "idempotencyKey": idempotency,
        "stageSchedule": stage_schedule,
        "rollbackGroups": rollback_groups,
        "checks": [
            {"name": "node-identities-bound", "status": "pass"},
            {"name": "capabilities-resolve", "status": "pass"},
            {"name": "write-scopes-bounded", "status": "pass"},
            {"name": "authority-ceilings-bound", "status": "pass"},
            {"name": "canary-first", "status": "pass"},
            {"name": "health-gates-bound", "status": "pass"},
            {"name": "cross-node-rollback-coordinated", "status": "pass"},
            {"name": "partition-autonomy-bounded", "status": "pass"},
            {"name": "replay-nonce-unused", "status": "pass"},
            {"name": "idempotency-key-unused", "status": "pass"},
        ],
        "authority": {"executionApplied": False, "canonicalMutationApplied": False, "executorDecisionAuthority": "none"},
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--history", type=Path, required=True)
    parser.add_argument("--out-receipt", type=Path, required=True)
    args = parser.parse_args()
    try:
        receipt = close_rollout(load_json_strict(args.registry), load_json_strict(args.plan), load_json_strict(args.history))
        args.out_receipt.parent.mkdir(parents=True, exist_ok=True)
        args.out_receipt.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
        print(receipt["status"])
        return 0
    except (OSError, json.JSONDecodeError, DistributedAdmissionError) as exc:
        print(f"distributed admission closure failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
