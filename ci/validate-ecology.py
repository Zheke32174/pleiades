#!/usr/bin/env python3
"""Validate a MODOS ecology registry and prove graph closure.

The validator is intentionally network-independent. A caller may provide an
observed repository inventory exported by a trusted GitHub client to prove
that the checked-in registry still exactly matches the account.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


AUTHORITY_RANK = {
    "none": 0,
    "proposal": 1,
    "local-enforcement": 2,
    "domain-control": 3,
    "steward-only": 4,
}
ARCHIVE_DISPOSITIONS = {"archive-only", "parked"}
MUTATING_SCOPES = {"runtime", "build", "governance", "deployment"}
CYCLE_RELATIONS = {"depends-on", "governed-by", "supersedes", "archive-of"}
AUTHORITY_BEARING_RELATIONS = {"canonical-for", "provides-capability"}


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def repo_from_ref(ref: str) -> str | None:
    return ref[5:] if ref.startswith("repo:") else None


def component_from_ref(ref: str) -> str | None:
    return ref[10:] if ref.startswith("component:") else None


def capability_from_ref(ref: str) -> tuple[str, str | None] | None:
    if not ref.startswith("capability:"):
        return None
    value = ref[11:]
    if "@" in value:
        capability_id, version = value.rsplit("@", 1)
        return capability_id, version
    return value, None


def scope_from_ref(ref: str) -> str | None:
    return ref[6:] if ref.startswith("scope:") else None


def normalize_observed_inventory(value: Any) -> set[str]:
    if isinstance(value, list):
        rows = value
    elif isinstance(value, dict) and isinstance(value.get("repositories"), list):
        rows = value["repositories"]
    elif (
        isinstance(value, dict)
        and isinstance(value.get("spec"), dict)
        and isinstance(value["spec"].get("repositories"), list)
    ):
        rows = value["spec"]["repositories"]
    else:
        raise ValueError(
            "observed inventory must be a list or an object with repositories[]/spec.repositories[]"
        )
    normalized: set[str] = set()
    for row in rows:
        if isinstance(row, str):
            normalized.add(row)
        elif isinstance(row, dict):
            name = row.get("repository_full_name") or row.get("full_name") or row.get("nameWithOwner")
            if not isinstance(name, str):
                raise ValueError(
                    "observed repository object lacks repository_full_name/full_name/nameWithOwner"
                )
            normalized.add(name)
        else:
            raise ValueError("observed repository entry must be a string or object")
    return normalized


def detect_cycle(edges: dict[str, set[str]]) -> list[str] | None:
    state: dict[str, int] = {}
    stack: list[str] = []

    def visit(node: str) -> list[str] | None:
        state[node] = 1
        stack.append(node)
        for target in sorted(edges.get(node, ())):
            if state.get(target, 0) == 0:
                cycle = visit(target)
                if cycle:
                    return cycle
            elif state.get(target) == 1:
                index = stack.index(target)
                return stack[index:] + [target]
        stack.pop()
        state[node] = 2
        return None

    for node in sorted(edges):
        if state.get(node, 0) == 0:
            cycle = visit(node)
            if cycle:
                return cycle
    return None


def validate_semantics(registry: dict[str, Any]) -> tuple[list[str], list[str], dict[str, Any]]:
    errors: list[str] = []
    warnings: list[str] = []
    spec = registry["spec"]
    inventory_list = spec["inventory"]["repositories"]
    inventory = set(inventory_list)

    if spec["inventory"]["expectedCount"] != len(inventory_list):
        errors.append(
            "inventory expectedCount does not equal the number of repositories "
            f"({spec['inventory']['expectedCount']} != {len(inventory_list)})"
        )

    expected_digest = registry["metadata"].get("sourceDigest")
    if expected_digest:
        digest_bytes = ("\n".join(sorted(inventory_list, key=str.lower)) + "\n").encode()
        actual_digest = "sha256:" + hashlib.sha256(digest_bytes).hexdigest()
        if actual_digest != expected_digest:
            errors.append(f"inventory sourceDigest mismatch: {actual_digest} != {expected_digest}")

    group_ids = [group["id"] for group in spec["groups"]]
    duplicate_group_ids = sorted(name for name, count in Counter(group_ids).items() if count > 1)
    if duplicate_group_ids:
        errors.append("duplicate group ids: " + ", ".join(duplicate_group_ids))

    membership: dict[str, list[dict[str, Any]]] = defaultdict(list)
    groups_by_repo: dict[str, dict[str, Any]] = {}
    for group in spec["groups"]:
        for repository in group["repositories"]:
            membership[repository].append(group)
            groups_by_repo[repository] = group

    duplicate_members = sorted(repository for repository, rows in membership.items() if len(rows) > 1)
    if duplicate_members:
        errors.append("repositories in multiple groups: " + ", ".join(duplicate_members))

    missing_members = sorted(inventory - set(membership))
    extra_members = sorted(set(membership) - inventory)
    if missing_members:
        errors.append("inventory repositories without a group: " + ", ".join(missing_members))
    if extra_members:
        errors.append("group repositories absent from inventory: " + ", ".join(extra_members))

    canonical_scopes = spec["canonicalScopes"]
    for scope, provider_ref in canonical_scopes.items():
        provider = repo_from_ref(provider_ref)
        if provider not in inventory:
            errors.append(f"canonical scope {scope} points outside inventory: {provider_ref}")
            continue
        disposition = groups_by_repo[provider]["disposition"]
        if disposition in {"archive-only", "parked", "reference", "delete-candidate"}:
            errors.append(
                f"canonical scope {scope} is assigned to non-live disposition {disposition}: {provider}"
            )

    component_ids = [component["componentId"] for component in spec["components"]]
    duplicate_components = sorted(name for name, count in Counter(component_ids).items() if count > 1)
    if duplicate_components:
        errors.append("duplicate component ids: " + ", ".join(duplicate_components))
    component_index = {component["componentId"]: component for component in spec["components"]}
    component_repositories = {component["repository"] for component in spec["components"]}
    for component in spec["components"]:
        if component["repository"] not in inventory:
            errors.append(
                f"component {component['componentId']} belongs to a repository outside inventory: "
                f"{component['repository']}"
            )
        if component["manifestState"] == "branch-only":
            warnings.append(
                f"component {component['componentId']} is branch-only at "
                f"{component.get('sourceRef', component['repository'])}"
            )

    manifest_required = {
        repository
        for repository, group in groups_by_repo.items()
        if group["disposition"] in {"canonical", "active", "active-supporting"}
    }
    missing_manifests = sorted(manifest_required - component_repositories)
    if missing_manifests:
        warnings.append(
            f"{len(missing_manifests)} live repositories do not yet have a verified component binding: "
            + ", ".join(missing_manifests)
        )

    capability_keys: set[tuple[str, str]] = set()
    capabilities_by_id: dict[str, set[str]] = defaultdict(set)
    for capability in spec["capabilities"]:
        key = (capability["id"], capability["version"])
        if key in capability_keys:
            errors.append(f"duplicate capability declaration: {capability['id']}@{capability['version']}")
        capability_keys.add(key)
        capabilities_by_id[capability["id"]].add(capability["version"])
        provider_ref = capability["providerRef"]
        provider_repo = repo_from_ref(provider_ref)
        provider_component = component_from_ref(provider_ref)
        if provider_repo and provider_repo not in inventory:
            errors.append(f"capability provider outside inventory: {provider_ref}")
        if provider_component and provider_component not in component_index:
            errors.append(f"capability provider component is unknown: {provider_ref}")

    graph_edges: dict[str, set[str]] = defaultdict(set)
    for index, relation in enumerate(spec["relations"]):
        source_ref = relation["sourceRef"]
        target_ref = relation["targetRef"]
        source_repo = repo_from_ref(source_ref)
        target_repo = repo_from_ref(target_ref)
        source_component = component_from_ref(source_ref)
        target_component = component_from_ref(target_ref)
        target_capability = capability_from_ref(target_ref)
        source_scope = scope_from_ref(source_ref)
        target_scope = scope_from_ref(target_ref)

        if source_repo and source_repo not in inventory:
            errors.append(f"relation[{index}] source repository is unknown: {source_ref}")
        if target_repo and target_repo not in inventory:
            errors.append(f"relation[{index}] target repository is unknown: {target_ref}")
        if source_component and source_component not in component_index:
            errors.append(f"relation[{index}] source component is unknown: {source_ref}")
        if target_component and target_component not in component_index:
            errors.append(f"relation[{index}] target component is unknown: {target_ref}")
        if source_scope and source_scope not in canonical_scopes:
            errors.append(f"relation[{index}] source scope is unknown: {source_ref}")
        if target_scope and target_scope not in canonical_scopes:
            errors.append(f"relation[{index}] target scope is unknown: {target_ref}")

        if target_capability:
            capability_id, version = target_capability
            known_versions = capabilities_by_id.get(capability_id, set())
            if not known_versions:
                errors.append(f"relation[{index}] targets unknown capability: {target_ref}")
            elif version is not None and version not in known_versions:
                errors.append(
                    f"relation[{index}] targets unknown capability version: {target_ref}; "
                    f"known={sorted(known_versions)}"
                )

        if source_ref == target_ref and relation["type"] not in {"mirror-of"}:
            errors.append(f"relation[{index}] is an illegal self relation: {source_ref}")

        if source_repo and source_repo in groups_by_repo:
            source_group = groups_by_repo[source_repo]
            if (
                relation["required"]
                and source_group["disposition"] in ARCHIVE_DISPOSITIONS
                and relation["scope"] in MUTATING_SCOPES
            ):
                errors.append(
                    f"relation[{index}] lets {source_group['disposition']} source a required "
                    f"{relation['scope']} edge: {source_repo}"
                )
            if relation["type"] in AUTHORITY_BEARING_RELATIONS:
                rank = AUTHORITY_RANK[source_group["authorityCeiling"]]
                if rank < AUTHORITY_RANK["local-enforcement"]:
                    errors.append(
                        f"relation[{index}] requires authority that group {source_group['id']} "
                        f"does not possess: {source_group['authorityCeiling']}"
                    )

        if relation["type"] in CYCLE_RELATIONS and relation["required"] and source_repo and target_repo:
            graph_edges[source_repo].add(target_repo)

    cycle = detect_cycle(graph_edges)
    if cycle:
        errors.append("required semantic graph contains a cycle: " + " -> ".join(cycle))

    report = {
        "registry": registry["metadata"]["name"],
        "observedAt": registry["metadata"]["observedAt"],
        "inventoryCount": len(inventory),
        "groupCount": len(spec["groups"]),
        "componentBindingCount": len(spec["components"]),
        "verifiedOrBranchManifestCount": len(component_repositories),
        "missingLiveManifestCount": len(missing_manifests),
        "capabilityCount": len(spec["capabilities"]),
        "relationCount": len(spec["relations"]),
        "canonicalScopeCount": len(canonical_scopes),
    }
    return errors, warnings, report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--schema", type=Path, required=True)
    parser.add_argument("--observed-inventory", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    registry = load_json(args.registry)
    schema = load_json(args.schema)
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    schema_errors = sorted(validator.iter_errors(registry), key=lambda error: list(error.path))
    errors = [
        "schema " + "/".join(str(part) for part in error.absolute_path) + ": " + error.message
        for error in schema_errors
    ]
    warnings: list[str] = []
    report: dict[str, Any] = {}

    if not schema_errors:
        semantic_errors, semantic_warnings, report = validate_semantics(registry)
        errors.extend(semantic_errors)
        warnings.extend(semantic_warnings)

    if args.observed_inventory and not schema_errors:
        observed = normalize_observed_inventory(load_json(args.observed_inventory))
        registered = set(registry["spec"]["inventory"]["repositories"])
        missing = sorted(observed - registered)
        stale = sorted(registered - observed)
        if missing:
            errors.append("live repositories missing from registry: " + ", ".join(missing))
        if stale:
            errors.append("registry repositories absent from live inventory: " + ", ".join(stale))
        report["observedInventoryCount"] = len(observed)

    result = {
        "status": "valid" if not errors else "invalid",
        **report,
        "warnings": warnings,
        "errors": errors,
        "validatedAt": datetime.now(timezone.utc).isoformat(),
    }

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    for warning in warnings:
        print(f"warning: {warning}", file=sys.stderr)
    if errors:
        print("ecology closure failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(
        "ecology closed: "
        f"{result['inventoryCount']} repositories, "
        f"{result['groupCount']} groups, "
        f"{result['relationCount']} relations, "
        f"{result['capabilityCount']} capabilities"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
