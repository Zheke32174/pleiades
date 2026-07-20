#!/usr/bin/env python3
"""Deterministically compile an EcologyRegistry into an ontology snapshot.

The adapter maps registry identities and typed relations into the ontology object
model. It never promotes the result and never treats a public projection as the
exhaustive private ecology.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

try:
    from . import compiler
except ImportError:
    import compiler  # type: ignore

API_VERSION = "modos.pleiades/v1alpha1"
AUTHORITY = {"ceiling": "none", "canonicalMutationApplied": False, "promotionTransactionRequired": True}


class EcologyAdapterError(ValueError):
    pass


def _partition_policy() -> dict[str, Any]:
    return {
        "read": "allow-cached",
        "write": "provisional",
        "merge": "authorized-decision",
        "globalAuthorityRequired": True,
        "conflictVisibility": "workspace",
    }


def _object(
    *,
    kind: str,
    object_id: str,
    name: str,
    spec: dict[str, Any],
    source: str,
    source_value: Any,
    created_at: str,
    visibility: str,
) -> dict[str, Any]:
    return {
        "apiVersion": API_VERSION,
        "kind": kind,
        "metadata": {"id": object_id, "name": name, "generation": 1, "createdAt": created_at},
        "spec": spec,
        "provenance": {
            "source": source,
            "digest": compiler.digest(source_value),
            "trust": "observed",
            "visibility": visibility,
            "lineage": [],
        },
        "partitionPolicy": _partition_policy(),
    }


def _relation(source: str, relation_type: str, target: str, **attributes: Any) -> dict[str, Any]:
    value: dict[str, Any] = {"sourceRef": source, "type": relation_type, "targetRef": target}
    if attributes:
        value["attributes"] = attributes
    return value


def validate_registry_shape(registry: dict[str, Any], schema: dict[str, Any]) -> None:
    Draft202012Validator.check_schema(schema)
    errors = sorted(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(registry),
        key=lambda error: list(error.path),
    )
    if errors:
        rendered = "; ".join(
            "/".join(map(str, error.absolute_path)) + ": " + error.message for error in errors
        )
        raise EcologyAdapterError("registry schema validation failed: " + rendered)
    if registry.get("kind") != "EcologyRegistry":
        raise EcologyAdapterError("registry kind must be EcologyRegistry")


def compile_registry(registry: dict[str, Any], schema: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    validate_registry_shape(registry, schema)
    metadata = registry["metadata"]
    spec = registry["spec"]
    created_at = metadata["observedAt"]
    visibility = metadata["visibility"]
    source = "ecology:" + metadata["name"]
    registry_digest = compiler.digest(registry)

    groups_by_repo: dict[str, dict[str, Any]] = {}
    for group in spec["groups"]:
        for repository in group["repositories"]:
            if repository in groups_by_repo:
                raise EcologyAdapterError(f"repository belongs to multiple groups: {repository}")
            groups_by_repo[repository] = group

    objects: list[dict[str, Any]] = [
        _object(
            kind="Mind",
            object_id="mind:pleiades",
            name="Pleiades persistent mind",
            spec={"persistentOrganization": True, "modelReplaceability": True, "dissentPreserved": True},
            source=source,
            source_value={"registryDigest": registry_digest, "role": "mind-anchor"},
            created_at=created_at,
            visibility=visibility,
        ),
        _object(
            kind="CognitiveWorkspace",
            object_id="workspace:pleiades",
            name="Pleiades shared executive workspace",
            spec={"typedContributions": True, "firstPassIsolation": True, "ecologyBound": True},
            source=source,
            source_value={"registryDigest": registry_digest, "role": "workspace-anchor"},
            created_at=created_at,
            visibility=visibility,
        ),
    ]
    relations: list[dict[str, Any]] = [
        _relation("mind:pleiades", "operates-through", "workspace:pleiades", source="ecology-adapter")
    ]

    for group in sorted(spec["groups"], key=lambda row: row["id"]):
        group_id = "group:" + group["id"]
        objects.append(
            _object(
                kind="CognitiveAssembly",
                object_id=group_id,
                name=group["description"],
                spec={
                    "subsystem": group["subsystem"],
                    "lifecycle": group["lifecycle"],
                    "disposition": group["disposition"],
                    "authorityCeiling": group["authorityCeiling"],
                    "repositoryCount": len(group["repositories"]),
                },
                source=source,
                source_value=group,
                created_at=created_at,
                visibility=visibility,
            )
        )

    for repository in sorted(spec["inventory"]["repositories"]):
        group = groups_by_repo.get(repository)
        if group is None:
            raise EcologyAdapterError(f"repository has no ecology group: {repository}")
        repo_id = "repo:" + repository
        objects.append(
            _object(
                kind="Resource",
                object_id=repo_id,
                name=repository,
                spec={
                    "resourceClass": "repository",
                    "repository": repository,
                    "groupId": group["id"],
                    "subsystem": group["subsystem"],
                    "lifecycle": group["lifecycle"],
                    "disposition": group["disposition"],
                    "authorityCeiling": group["authorityCeiling"],
                },
                source=source,
                source_value={"repository": repository, "group": group},
                created_at=created_at,
                visibility=visibility,
            )
        )
        relations.append(_relation(repo_id, "part-of", "group:" + group["id"], required=True))

    for scope, provider_ref in sorted(spec["canonicalScopes"].items()):
        scope_id = "scope:" + scope
        objects.append(
            _object(
                kind="Resource",
                object_id=scope_id,
                name="Canonical scope " + scope,
                spec={"resourceClass": "canonical-scope", "providerRef": provider_ref},
                source=source,
                source_value={"scope": scope, "providerRef": provider_ref},
                created_at=created_at,
                visibility=visibility,
            )
        )

    for component in sorted(spec["components"], key=lambda row: row["componentId"]):
        component_id = "component:" + component["componentId"]
        objects.append(
            _object(
                kind="Resource",
                object_id=component_id,
                name=component["componentId"],
                spec={"resourceClass": "component", **component},
                source=source,
                source_value=component,
                created_at=created_at,
                visibility=visibility,
            )
        )
        relations.append(_relation(component_id, "part-of", "repo:" + component["repository"], manifestState=component["manifestState"]))

    capability_ids: dict[tuple[str, str], str] = {}
    for capability in sorted(spec["capabilities"], key=lambda row: (row["id"], row["version"])):
        capability_id = f"capability:{capability['id']}@{capability['version']}"
        key = (capability["id"], capability["version"])
        if key in capability_ids:
            raise EcologyAdapterError(f"duplicate capability: {capability_id}")
        capability_ids[key] = capability_id
        objects.append(
            _object(
                kind="Service",
                object_id=capability_id,
                name=capability["id"],
                spec={"serviceClass": "capability", **capability},
                source=source,
                source_value=capability,
                created_at=created_at,
                visibility=visibility,
            )
        )
        relations.append(_relation(capability["providerRef"], "provides-capability", capability_id, status=capability["status"]))

    for row in spec["relations"]:
        target_ref = row["targetRef"]
        if target_ref.startswith("capability:") and "@" not in target_ref:
            matches = [value for (cap_id, _), value in capability_ids.items() if cap_id == target_ref[11:]]
            if len(matches) != 1:
                raise EcologyAdapterError(f"unversioned capability relation is ambiguous: {target_ref}")
            target_ref = matches[0]
        relations.append(
            _relation(
                row["sourceRef"],
                row["type"],
                target_ref,
                scope=row["scope"],
                required=row["required"],
                **({"versionConstraint": row["versionConstraint"]} if "versionConstraint" in row else {}),
            )
        )

    snapshot = compiler.normalize_snapshot(
        {
            "apiVersion": API_VERSION,
            "kind": "OntologySnapshot",
            "schemaVersion": "v1alpha1",
            "mindId": "mind:pleiades",
            "objects": objects,
            "relations": relations,
        }
    )
    snapshot_digest = compiler.snapshot_digest(snapshot)
    receipt = {
        "apiVersion": API_VERSION,
        "kind": "EcologyOntologyCompilationReceipt",
        "registryName": metadata["name"],
        "registryDigest": registry_digest,
        "sourceVisibility": visibility,
        "objectCount": len(snapshot["objects"]),
        "relationCount": len(snapshot["relations"]),
        "resultSnapshotDigest": snapshot_digest,
        "publicScopeIncluded": visibility == "public",
        "privateScopeIncluded": visibility == "private",
        "fullEcologyClosure": False,
        "blockers": ["live-private-exhaustive-registry-not-supplied"],
        "authority": AUTHORITY,
    }
    receipt["receiptDigest"] = compiler.digest(receipt)
    return snapshot, receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--schema", type=Path, required=True)
    parser.add_argument("--out-snapshot", type=Path, required=True)
    parser.add_argument("--out-receipt", type=Path, required=True)
    args = parser.parse_args()
    try:
        registry = compiler.load_json_strict(args.registry)
        schema = compiler.load_json_strict(args.schema)
        snapshot, receipt = compile_registry(registry, schema)
        args.out_snapshot.parent.mkdir(parents=True, exist_ok=True)
        args.out_receipt.parent.mkdir(parents=True, exist_ok=True)
        args.out_snapshot.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        args.out_receipt.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"compiled public ecology: {receipt['objectCount']} objects, {receipt['relationCount']} relations")
        return 0
    except (OSError, json.JSONDecodeError, EcologyAdapterError, compiler.OntologyCompileError) as exc:
        print(f"ecology ontology compilation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
