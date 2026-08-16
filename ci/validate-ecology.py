#!/usr/bin/env python3
"""Validate a MODOS ecology registry and emit deterministic closure evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator, FormatChecker

AUTHORITY_RANK = {"none": 0, "proposal": 1, "local-enforcement": 2, "domain-control": 3, "steward-only": 4}
ARCHIVE_DISPOSITIONS = {"archive-only", "parked"}
MUTATING_SCOPES = {"runtime", "build", "governance", "deployment"}
CYCLE_RELATIONS = {"depends-on", "governed-by", "supersedes", "archive-of"}
AUTHORITY_BEARING_RELATIONS = {"canonical-for", "provides-capability"}


class EcologyValidationError(ValueError):
    pass


def _no_duplicate_keys(pairs: Iterable[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise EcologyValidationError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle, object_pairs_hook=_no_duplicate_keys)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_bytes(value)).hexdigest()


def repo_from_ref(ref: str) -> str | None:
    return ref[5:] if ref.startswith("repo:") else None


def component_from_ref(ref: str) -> str | None:
    return ref[10:] if ref.startswith("component:") else None


def capability_from_ref(ref: str) -> tuple[str, str | None] | None:
    if not ref.startswith("capability:"):
        return None
    value = ref[11:]
    if "@" in value:
        return tuple(value.rsplit("@", 1))  # type: ignore[return-value]
    return value, None


def scope_from_ref(ref: str) -> str | None:
    return ref[6:] if ref.startswith("scope:") else None


def normalize_observed_inventory(value: Any) -> set[str]:
    if isinstance(value, list):
        rows = value
    elif isinstance(value, dict) and isinstance(value.get("repositories"), list):
        rows = value["repositories"]
    elif isinstance(value, dict) and isinstance(value.get("spec"), dict) and isinstance(value["spec"].get("repositories"), list):
        rows = value["spec"]["repositories"]
    else:
        raise EcologyValidationError("observed inventory must be a list or object containing repositories[]")
    normalized: set[str] = set()
    for row in rows:
        if isinstance(row, str):
            normalized.add(row)
        elif isinstance(row, dict):
            name = row.get("repository_full_name") or row.get("full_name") or row.get("nameWithOwner")
            if not isinstance(name, str):
                raise EcologyValidationError("observed repository object lacks a full-name field")
            normalized.add(name)
        else:
            raise EcologyValidationError("observed repository entry must be a string or object")
    return normalized


def detect_cycle(edges: dict[str, set[str]]) -> list[str] | None:
    state: dict[str, int] = {}
    stack: list[str] = []

    def visit(node: str) -> list[str] | None:
        state[node] = 1
        stack.append(node)
        for target in sorted(edges.get(node, ())):
            if state.get(target, 0) == 0:
                found = visit(target)
                if found:
                    return found
            elif state.get(target) == 1:
                index = stack.index(target)
                return stack[index:] + [target]
        stack.pop()
        state[node] = 2
        return None

    for node in sorted(edges):
        if state.get(node, 0) == 0:
            found = visit(node)
            if found:
                return found
    return None


def validate_semantics(registry: dict[str, Any]) -> tuple[list[str], list[str], dict[str, Any]]:
    errors: list[str] = []
    warnings: list[str] = []
    spec = registry["spec"]
    inventory_list = spec["inventory"]["repositories"]
    inventory = set(inventory_list)

    if spec["inventory"]["expectedCount"] != len(inventory_list):
        errors.append("inventory expectedCount does not equal repositories length")
    if len(inventory) != len(inventory_list):
        errors.append("inventory contains duplicate repositories")

    expected_digest = registry["metadata"].get("sourceDigest")
    if expected_digest:
        inventory_bytes = ("\n".join(sorted(inventory_list, key=str.lower)) + "\n").encode()
        actual_digest = "sha256:" + hashlib.sha256(inventory_bytes).hexdigest()
        if actual_digest != expected_digest:
            errors.append(f"inventory sourceDigest mismatch: {actual_digest} != {expected_digest}")

    groups = spec["groups"]
    group_ids = [group["id"] for group in groups]
    duplicates = sorted(name for name, count in Counter(group_ids).items() if count > 1)
    if duplicates:
        errors.append("duplicate group ids: " + ", ".join(duplicates))

    membership: dict[str, list[dict[str, Any]]] = defaultdict(list)
    groups_by_repo: dict[str, dict[str, Any]] = {}
    for group in groups:
        for repository in group["repositories"]:
            membership[repository].append(group)
            groups_by_repo[repository] = group
    duplicate_members = sorted(repo for repo, rows in membership.items() if len(rows) > 1)
    if duplicate_members:
        errors.append("repositories in multiple groups: " + ", ".join(duplicate_members))
    missing_members = sorted(inventory - set(membership))
    extra_members = sorted(set(membership) - inventory)
    if missing_members:
        errors.append("inventory repositories without a group: " + ", ".join(missing_members))
    if extra_members:
        errors.append("group repositories absent from inventory: " + ", ".join(extra_members))

    scopes = spec["canonicalScopes"]
    for scope, provider_ref in scopes.items():
        provider = repo_from_ref(provider_ref)
        if provider not in inventory:
            errors.append(f"canonical scope {scope} points outside inventory: {provider_ref}")
        elif groups_by_repo[provider]["disposition"] in {"archive-only", "parked", "reference", "delete-candidate"}:
            errors.append(f"canonical scope {scope} uses a non-live provider: {provider}")

    components = spec["components"]
    component_ids = [row["componentId"] for row in components]
    duplicate_components = sorted(name for name, count in Counter(component_ids).items() if count > 1)
    if duplicate_components:
        errors.append("duplicate component ids: " + ", ".join(duplicate_components))
    component_index = {row["componentId"]: row for row in components}
    component_repositories = {row["repository"] for row in components}
    for row in components:
        if row["repository"] not in inventory:
            errors.append(f"component {row['componentId']} belongs outside inventory")
        if row["manifestState"] == "branch-only":
            warnings.append(f"component {row['componentId']} is branch-only")
    live_repositories = {repo for repo, group in groups_by_repo.items() if group["disposition"] in {"canonical", "active", "active-supporting"}}
    missing_manifests = sorted(live_repositories - component_repositories)
    if missing_manifests:
        warnings.append("live repositories without component bindings: " + ", ".join(missing_manifests))

    capability_keys: set[tuple[str, str]] = set()
    capabilities_by_id: dict[str, set[str]] = defaultdict(set)
    for row in spec["capabilities"]:
        key = (row["id"], row["version"])
        if key in capability_keys:
            errors.append(f"duplicate capability declaration: {row['id']}@{row['version']}")
        capability_keys.add(key)
        capabilities_by_id[row["id"]].add(row["version"])
        provider_repo = repo_from_ref(row["providerRef"])
        provider_component = component_from_ref(row["providerRef"])
        if provider_repo and provider_repo not in inventory:
            errors.append(f"capability provider outside inventory: {row['providerRef']}")
        if provider_component and provider_component not in component_index:
            errors.append(f"unknown capability provider component: {row['providerRef']}")

    graph_edges: dict[str, set[str]] = defaultdict(set)
    for index, relation in enumerate(spec["relations"]):
        source_ref, target_ref = relation["sourceRef"], relation["targetRef"]
        source_repo, target_repo = repo_from_ref(source_ref), repo_from_ref(target_ref)
        source_component, target_component = component_from_ref(source_ref), component_from_ref(target_ref)
        source_scope, target_scope = scope_from_ref(source_ref), scope_from_ref(target_ref)
        target_capability = capability_from_ref(target_ref)

        if source_repo and source_repo not in inventory:
            errors.append(f"relation[{index}] unknown source repository: {source_ref}")
        if target_repo and target_repo not in inventory:
            errors.append(f"relation[{index}] unknown target repository: {target_ref}")
        if source_component and source_component not in component_index:
            errors.append(f"relation[{index}] unknown source component: {source_ref}")
        if target_component and target_component not in component_index:
            errors.append(f"relation[{index}] unknown target component: {target_ref}")
        if source_scope and source_scope not in scopes:
            errors.append(f"relation[{index}] unknown source scope: {source_ref}")
        if target_scope and target_scope not in scopes:
            errors.append(f"relation[{index}] unknown target scope: {target_ref}")
        if target_capability:
            capability_id, version = target_capability
            known_versions = capabilities_by_id.get(capability_id, set())
            if not known_versions or (version is not None and version not in known_versions):
                errors.append(f"relation[{index}] targets unknown capability: {target_ref}")
        if source_ref == target_ref and relation["type"] != "mirror-of":
            errors.append(f"relation[{index}] illegal self relation: {source_ref}")

        if source_repo and source_repo in groups_by_repo:
            source_group = groups_by_repo[source_repo]
            if relation["required"] and source_group["disposition"] in ARCHIVE_DISPOSITIONS and relation["scope"] in MUTATING_SCOPES:
                errors.append(f"relation[{index}] lets archived source carry required {relation['scope']} authority")
            if relation["type"] in AUTHORITY_BEARING_RELATIONS and AUTHORITY_RANK[source_group["authorityCeiling"]] < AUTHORITY_RANK["local-enforcement"]:
                errors.append(f"relation[{index}] exceeds authority ceiling of group {source_group['id']}")
        if relation["type"] in CYCLE_RELATIONS and relation["required"] and source_repo and target_repo:
            graph_edges[source_repo].add(target_repo)

    cycle = detect_cycle(graph_edges)
    if cycle:
        errors.append("required semantic graph contains a cycle: " + " -> ".join(cycle))

    report = {
        "registry": registry["metadata"]["name"],
        "registryDigest": digest(registry),
        "inventoryCount": len(inventory),
        "groupCount": len(groups),
        "componentBindingCount": len(components),
        "missingLiveManifestCount": len(missing_manifests),
        "capabilityCount": len(spec["capabilities"]),
        "relationCount": len(spec["relations"]),
        "canonicalScopeCount": len(scopes),
    }
    return errors, warnings, report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--schema", type=Path, required=True)
    parser.add_argument("--observed-inventory", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    try:
        registry = load_json(args.registry)
        schema = load_json(args.schema)
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        schema_errors = sorted(validator.iter_errors(registry), key=lambda error: list(error.path))
        errors = ["schema " + "/".join(map(str, error.absolute_path)) + ": " + error.message for error in schema_errors]
        warnings: list[str] = []
        report: dict[str, Any] = {"registryDigest": digest(registry)}
        if not schema_errors:
            semantic_errors, semantic_warnings, report = validate_semantics(registry)
            errors.extend(semantic_errors)
            warnings.extend(semantic_warnings)
        if args.observed_inventory and not schema_errors:
            observed = normalize_observed_inventory(load_json(args.observed_inventory))
            registered = set(registry["spec"]["inventory"]["repositories"])
            missing, stale = sorted(observed - registered), sorted(registered - observed)
            if missing:
                errors.append("live repositories missing from registry: " + ", ".join(missing))
            if stale:
                errors.append("registry repositories absent from live inventory: " + ", ".join(stale))
            report["observedInventoryCount"] = len(observed)
        result = {
            "apiVersion": "modos.pleiades/v1alpha1",
            "kind": "EcologyClosureReceipt",
            "status": "valid" if not errors else "invalid",
            **report,
            "warnings": sorted(warnings),
            "errors": sorted(errors),
            "authority": {"ceiling": "none", "canonicalMutationApplied": False},
        }
        result["receiptDigest"] = digest(result)
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        for warning in warnings:
            print(f"warning: {warning}", file=sys.stderr)
        if errors:
            for error in errors:
                print(f"error: {error}", file=sys.stderr)
            return 1
        print(f"ecology closed: {result['inventoryCount']} repositories; receipt {result['receiptDigest']}")
        return 0
    except (OSError, json.JSONDecodeError, EcologyValidationError, ValueError) as exc:
        print(f"ecology validation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
