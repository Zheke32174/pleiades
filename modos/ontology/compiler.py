#!/usr/bin/env python3
"""Deterministic, proposal-only ontology snapshot compiler.

This module does not promote or admit ontology state. It transforms one exact
snapshot plus one authority-free ChangeProposal into a candidate snapshot,
semantic diff, and closure receipt suitable for later governed review.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable

COMPILER_NAME = "pleiades-ontology-compiler"
COMPILER_VERSION = "0.1.0"
CANONICALIZATION = "pleiades-canonical-json-v1"
API_VERSION = "modos.pleiades/v1alpha1"
SUPPORTED_FAMILIES = {
    "Node",
    "Resource",
    "Device",
    "Workload",
    "Service",
    "Model",
    "Mind",
    "Agent",
    "CognitiveAssembly",
    "CognitiveWorkspace",
}
DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


class OntologyCompileError(ValueError):
    """Raised when deterministic compilation or closure fails."""


def _reject_float(value: str) -> None:
    raise OntologyCompileError(f"floating-point values are forbidden: {value}")


def _reject_constant(value: str) -> None:
    raise OntologyCompileError(f"non-finite JSON constant is forbidden: {value}")


def _no_duplicate_keys(pairs: Iterable[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise OntologyCompileError(f"duplicate JSON key is forbidden: {key}")
        result[key] = value
    return result


def load_json_strict(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(
            handle,
            parse_float=_reject_float,
            parse_constant=_reject_constant,
            object_pairs_hook=_no_duplicate_keys,
        )


def _assert_no_floats(value: Any, location: str = "$") -> None:
    if isinstance(value, float):
        raise OntologyCompileError(f"floating-point values are forbidden at {location}")
    if isinstance(value, dict):
        for key, child in value.items():
            _assert_no_floats(child, f"{location}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_no_floats(child, f"{location}[{index}]")


def canonical_bytes(value: Any) -> bytes:
    _assert_no_floats(value)
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_bytes(value)).hexdigest()


def _relation_key(relation: dict[str, Any]) -> tuple[str, str, str, bytes]:
    attributes = relation.get("attributes", {})
    return (
        relation["sourceRef"],
        relation["type"],
        relation["targetRef"],
        canonical_bytes(attributes),
    )


def normalize_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    candidate = copy.deepcopy(snapshot)
    if candidate.get("apiVersion") != API_VERSION:
        raise OntologyCompileError("snapshot apiVersion is unsupported")
    if candidate.get("kind") != "OntologySnapshot":
        raise OntologyCompileError("snapshot kind must be OntologySnapshot")
    if not isinstance(candidate.get("schemaVersion"), str) or not candidate["schemaVersion"]:
        raise OntologyCompileError("snapshot schemaVersion is required")
    if not isinstance(candidate.get("mindId"), str) or not candidate["mindId"]:
        raise OntologyCompileError("snapshot mindId is required")
    objects = candidate.get("objects")
    relations = candidate.get("relations")
    if not isinstance(objects, list) or not isinstance(relations, list):
        raise OntologyCompileError("snapshot objects and relations must be arrays")
    candidate["objects"] = sorted(objects, key=lambda item: item.get("metadata", {}).get("id", ""))
    candidate["relations"] = sorted(relations, key=_relation_key)
    validate_closure(candidate)
    return candidate


def snapshot_digest(snapshot: dict[str, Any]) -> str:
    return digest(normalize_snapshot(snapshot))


def _validate_object(obj: dict[str, Any]) -> None:
    required = {"apiVersion", "kind", "metadata", "spec", "provenance", "partitionPolicy"}
    if not isinstance(obj, dict) or not required.issubset(obj):
        raise OntologyCompileError("domain object is missing required envelope fields")
    if obj["apiVersion"] != API_VERSION:
        raise OntologyCompileError("domain object apiVersion is unsupported")
    if obj["kind"] not in SUPPORTED_FAMILIES:
        raise OntologyCompileError(f"unsupported domain object family: {obj['kind']}")
    metadata = obj["metadata"]
    if not isinstance(metadata, dict):
        raise OntologyCompileError("domain object metadata must be an object")
    for field in ("id", "name", "generation", "createdAt"):
        if field not in metadata:
            raise OntologyCompileError(f"domain object metadata.{field} is required")
    if not isinstance(metadata["id"], str) or not metadata["id"]:
        raise OntologyCompileError("domain object metadata.id must be nonempty")
    if not isinstance(metadata["generation"], int) or isinstance(metadata["generation"], bool) or metadata["generation"] < 1:
        raise OntologyCompileError("domain object generation must be a positive integer")
    provenance = obj["provenance"]
    if not isinstance(provenance, dict) or provenance.get("trust") not in {"untrusted", "observed", "verified", "canonical"}:
        raise OntologyCompileError("domain object provenance.trust is invalid")
    provenance_digest = provenance.get("digest")
    if not isinstance(provenance_digest, str) or not DIGEST_RE.fullmatch(provenance_digest):
        raise OntologyCompileError("domain object provenance.digest must be lowercase sha256")
    partition = obj["partitionPolicy"]
    if not isinstance(partition, dict):
        raise OntologyCompileError("domain object partitionPolicy must be an object")
    if obj["kind"] == "Model":
        spec = obj.get("spec", {})
        if spec.get("isWholeMind") is True or spec.get("mindRole") == "whole-mind":
            raise OntologyCompileError("Model cannot declare itself the whole Mind")


def validate_closure(snapshot: dict[str, Any]) -> list[dict[str, str]]:
    objects = snapshot.get("objects", [])
    relations = snapshot.get("relations", [])
    ids: dict[str, dict[str, Any]] = {}
    for obj in objects:
        _validate_object(obj)
        object_id = obj["metadata"]["id"]
        if object_id in ids:
            raise OntologyCompileError(f"duplicate object id: {object_id}")
        ids[object_id] = obj
    relation_keys: set[tuple[str, str, str, bytes]] = set()
    for relation in relations:
        if not isinstance(relation, dict):
            raise OntologyCompileError("relation must be an object")
        required = {"sourceRef", "type", "targetRef"}
        if not required.issubset(relation):
            raise OntologyCompileError("relation requires sourceRef, type, and targetRef")
        if relation["sourceRef"] not in ids:
            raise OntologyCompileError(f"dangling relation source: {relation['sourceRef']}")
        if relation["targetRef"] not in ids:
            raise OntologyCompileError(f"dangling relation target: {relation['targetRef']}")
        key = _relation_key(relation)
        if key in relation_keys:
            raise OntologyCompileError(
                f"duplicate relation: {relation['sourceRef']} {relation['type']} {relation['targetRef']}"
            )
        relation_keys.add(key)
    return [
        {"name": "unique-object-identities", "status": "pass"},
        {"name": "supported-object-families", "status": "pass"},
        {"name": "closed-relation-endpoints", "status": "pass"},
        {"name": "unique-relations", "status": "pass"},
        {"name": "polycentric-mind-boundary", "status": "pass"},
    ]


def _ensure_proposal_authority(proposal: dict[str, Any]) -> None:
    exact = {
        "ceiling": "none",
        "canonicalMutation": "forbidden",
        "promotionTransactionRequired": True,
        "selfPromotionAllowed": False,
    }
    if proposal.get("authority") != exact:
        raise OntologyCompileError("proposal authority boundary is not exact")


def _ensure_candidate_not_promoted(obj: dict[str, Any]) -> None:
    if obj["provenance"].get("trust") == "canonical":
        raise OntologyCompileError("proposal cannot create or update an object as canonical")
    if obj["partitionPolicy"].get("write") == "authoritative":
        raise OntologyCompileError("proposal cannot create or update authoritative partition writes")


def _semantic_diff(
    source: dict[str, Any], result: dict[str, Any]
) -> dict[str, list[Any]]:
    before = {obj["metadata"]["id"]: obj for obj in source["objects"]}
    after = {obj["metadata"]["id"]: obj for obj in result["objects"]}
    added = sorted(set(after) - set(before))
    deleted = sorted(set(before) - set(after))
    updated = sorted(
        object_id
        for object_id in set(before) & set(after)
        if canonical_bytes(before[object_id]) != canonical_bytes(after[object_id])
    )
    before_rel = {_relation_key(relation): relation for relation in source["relations"]}
    after_rel = {_relation_key(relation): relation for relation in result["relations"]}
    relation_added = [after_rel[key] for key in sorted(set(after_rel) - set(before_rel))]
    relation_removed = [before_rel[key] for key in sorted(set(before_rel) - set(after_rel))]
    return {
        "objectsAdded": added,
        "objectsUpdated": updated,
        "objectsDeleted": deleted,
        "relationsAdded": relation_added,
        "relationsRemoved": relation_removed,
    }


def compile_proposal(
    snapshot: dict[str, Any], proposal: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    source = normalize_snapshot(snapshot)
    source_digest = digest(source)
    _ensure_proposal_authority(proposal)
    if proposal.get("apiVersion") != API_VERSION or proposal.get("kind") != "ChangeProposal":
        raise OntologyCompileError("unsupported proposal envelope")
    if proposal.get("sourceSnapshotDigest") != source_digest:
        raise OntologyCompileError("proposal sourceSnapshotDigest does not match the exact source snapshot")
    if proposal.get("targetSchemaVersion") != source["schemaVersion"]:
        raise OntologyCompileError("proposal targetSchemaVersion does not match snapshot schemaVersion")
    if proposal.get("mindId") != source["mindId"]:
        raise OntologyCompileError("proposal mindId does not match snapshot mindId")
    family = proposal.get("objectFamily")
    if family not in SUPPORTED_FAMILIES:
        raise OntologyCompileError("proposal objectFamily is unsupported")
    operations = proposal.get("operations")
    if not isinstance(operations, list) or not operations:
        raise OntologyCompileError("proposal operations must be a nonempty array")

    result = copy.deepcopy(source)
    objects = {obj["metadata"]["id"]: obj for obj in result["objects"]}
    relations = {_relation_key(relation): relation for relation in result["relations"]}
    seen_operations: set[bytes] = set()

    for index, operation in enumerate(operations):
        operation_identity = canonical_bytes(operation)
        if operation_identity in seen_operations:
            raise OntologyCompileError(f"operation {index} duplicates an earlier operation")
        seen_operations.add(operation_identity)
        op = operation.get("op")
        object_id = operation.get("objectId")
        if not isinstance(object_id, str) or not object_id:
            raise OntologyCompileError(f"operation {index} objectId is required")
        if op == "create":
            if object_id in objects:
                raise OntologyCompileError(f"operation {index} create collides with existing object")
            candidate = copy.deepcopy(operation.get("payload"))
            if not isinstance(candidate, dict):
                raise OntologyCompileError(f"operation {index} create requires full object payload")
            _validate_object(candidate)
            _ensure_candidate_not_promoted(candidate)
            if candidate["metadata"]["id"] != object_id or candidate["kind"] != family:
                raise OntologyCompileError(f"operation {index} create identity or family mismatch")
            objects[object_id] = candidate
        elif op == "update":
            existing = objects.get(object_id)
            if existing is None:
                raise OntologyCompileError(f"operation {index} update target does not exist")
            candidate = copy.deepcopy(operation.get("payload"))
            if not isinstance(candidate, dict):
                raise OntologyCompileError(f"operation {index} update requires full replacement payload")
            _validate_object(candidate)
            _ensure_candidate_not_promoted(candidate)
            if existing["kind"] != family or candidate["kind"] != family:
                raise OntologyCompileError(f"operation {index} update family mismatch")
            if candidate["metadata"]["id"] != object_id:
                raise OntologyCompileError(f"operation {index} update cannot change object identity")
            if candidate["metadata"]["generation"] != existing["metadata"]["generation"] + 1:
                raise OntologyCompileError(f"operation {index} update generation must advance exactly once")
            objects[object_id] = candidate
        elif op == "delete":
            existing = objects.get(object_id)
            if existing is None:
                raise OntologyCompileError(f"operation {index} delete target does not exist")
            if existing["kind"] != family:
                raise OntologyCompileError(f"operation {index} delete family mismatch")
            del objects[object_id]
        elif op in {"link", "unlink"}:
            relation_type = operation.get("relationType")
            target_ref = operation.get("targetRef")
            if not isinstance(relation_type, str) or not relation_type:
                raise OntologyCompileError(f"operation {index} relationType is required")
            if not isinstance(target_ref, str) or not target_ref:
                raise OntologyCompileError(f"operation {index} targetRef is required")
            source_object = objects.get(object_id)
            if source_object is None or source_object["kind"] != family:
                raise OntologyCompileError(f"operation {index} relation source is absent or wrong family")
            if target_ref not in objects:
                raise OntologyCompileError(f"operation {index} relation target does not exist")
            relation = {"sourceRef": object_id, "type": relation_type, "targetRef": target_ref}
            key = _relation_key(relation)
            if op == "link":
                if key in relations:
                    raise OntologyCompileError(f"operation {index} relation already exists")
                relations[key] = relation
            else:
                if key not in relations:
                    raise OntologyCompileError(f"operation {index} unlink relation does not exist")
                del relations[key]
        else:
            raise OntologyCompileError(f"operation {index} has unsupported op: {op}")

    result["objects"] = list(objects.values())
    result["relations"] = list(relations.values())
    result = normalize_snapshot(result)
    checks = validate_closure(result)
    result_digest = digest(result)
    semantic_diff = _semantic_diff(source, result)
    receipt = {
        "apiVersion": API_VERSION,
        "kind": "OntologyClosureReceipt",
        "compiler": {
            "name": COMPILER_NAME,
            "version": COMPILER_VERSION,
            "canonicalization": CANONICALIZATION,
        },
        "proposalId": proposal.get("proposalId"),
        "proposalDigest": digest(proposal),
        "mindId": source["mindId"],
        "schemaVersion": source["schemaVersion"],
        "sourceSnapshotDigest": source_digest,
        "resultSnapshotDigest": result_digest,
        "closureStatus": "closed",
        "counts": {
            "sourceObjects": len(source["objects"]),
            "resultObjects": len(result["objects"]),
            "sourceRelations": len(source["relations"]),
            "resultRelations": len(result["relations"]),
        },
        "semanticDiff": semantic_diff,
        "checks": checks
        + [
            {"name": "source-digest-bound", "status": "pass"},
            {"name": "authority-monotonicity", "status": "pass"},
            {"name": "proposal-only-no-promotion", "status": "pass"},
        ],
        "authority": {
            "ceiling": "none",
            "canonicalMutationApplied": False,
            "promotionTransactionRequired": True,
            "promotionState": "eligible-for-review",
        },
    }
    return result, receipt


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--proposal", type=Path, required=True)
    parser.add_argument("--out-snapshot", type=Path, required=True)
    parser.add_argument("--out-receipt", type=Path, required=True)
    args = parser.parse_args()
    try:
        snapshot = load_json_strict(args.snapshot)
        proposal = load_json_strict(args.proposal)
        result, receipt = compile_proposal(snapshot, proposal)
        _write_json(args.out_snapshot, result)
        _write_json(args.out_receipt, receipt)
        print(receipt["resultSnapshotDigest"])
        return 0
    except (OSError, json.JSONDecodeError, OntologyCompileError) as exc:
        print(f"ontology compilation failed: {exc}", file=__import__("sys").stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
