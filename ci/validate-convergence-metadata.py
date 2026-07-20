#!/usr/bin/env python3
"""Validate convergence metadata across contracts, PRs, runtime, and mainline reconciliation."""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Iterable


class MetadataError(ValueError):
    pass


def _pairs(items: Iterable[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in items:
        if key in result:
            raise MetadataError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle, object_pairs_hook=_pairs)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_bytes(value)).hexdigest()


def expand_family_paths(root: Path, family: dict[str, Any]) -> set[str]:
    rows: set[str] = set()
    for path in family.get("paths", []):
        if not isinstance(path, str) or not path:
            raise MetadataError(f"family {family.get('familyId')} contains an invalid path")
        rows.add(path)
    all_contracts = [path.relative_to(root).as_posix() for path in (root / "modos" / "contracts").glob("*.schema.json")]
    for pattern in family.get("pathPatterns", []):
        matches = {path for path in all_contracts if fnmatch.fnmatch(path, pattern)}
        if not matches:
            raise MetadataError(f"family {family.get('familyId')} pattern matched no contracts: {pattern}")
        rows.update(matches)
    return rows


def validate(root: Path) -> dict[str, Any]:
    governance = load(root / "modos" / "convergence" / "contract-governance.json")
    inventory = load(root / "modos" / "convergence" / "github-pr-inventory.json")
    stack = load(root / "modos" / "convergence" / "stack-manifest.json")
    collision = load(root / "modos" / "convergence" / "mainline-collision-map.json")
    runtime = load(root / "modos" / "convergence" / "runtime-matrix.json")
    errors: list[str] = []

    if governance.get("kind") != "ContractGovernanceMatrix":
        errors.append("unsupported contract governance matrix")
    assigned: dict[str, list[str]] = {}
    family_rows = governance.get("families")
    if not isinstance(family_rows, list) or not family_rows:
        errors.append("contract families must be nonempty")
        family_rows = []
    for family in family_rows:
        family_id = family.get("familyId")
        if not isinstance(family_id, str) or not family_id:
            errors.append("contract family id is invalid")
            continue
        if family.get("owner") != "@Zheke32174":
            errors.append(f"contract family {family_id} has unexpected review owner")
        if family.get("currentVersion") != "v1alpha1":
            errors.append(f"contract family {family_id} currentVersion is unsupported")
        if not isinstance(family.get("authorityClass"), str) or not family["authorityClass"]:
            errors.append(f"contract family {family_id} authorityClass is required")
        try:
            for path in expand_family_paths(root, family):
                assigned.setdefault(path, []).append(family_id)
        except MetadataError as exc:
            errors.append(str(exc))

    contract_paths = sorted(path.relative_to(root).as_posix() for path in (root / "modos" / "contracts").glob("*.schema.json"))
    for path in contract_paths:
        owners = assigned.get(path, [])
        if not owners:
            errors.append(f"contract is not assigned to a governance family: {path}")
        elif len(owners) > 1:
            errors.append(f"contract is assigned to multiple governance families: {path}: {', '.join(owners)}")
    for path in sorted(set(assigned) - set(contract_paths)):
        errors.append(f"contract governance references a missing contract: {path}")

    compatibility = governance.get("compatibilityPolicy", {})
    for field in ("newRequiredField", "enumNarrowing", "authorityCeilingIncrease", "schemaIdChange", "unknownFutureVersion"):
        if field not in compatibility:
            errors.append(f"compatibility policy is missing {field}")
    if governance.get("authority") != {"ceiling": "none", "mayChangeContracts": False, "mayPromoteContracts": False}:
        errors.append("contract governance authority boundary is not exact")

    if inventory.get("kind") != "GitHubPullRequestInventory" or inventory.get("repository") != stack.get("repository"):
        errors.append("PR inventory does not describe the stack repository")
    live_rows = {row.get("number"): row for row in inventory.get("pullRequests", []) if isinstance(row, dict)}
    stack_rows = stack.get("pullRequests", [])
    for row in stack_rows:
        number = row.get("number")
        observed = live_rows.get(number)
        if observed is None:
            errors.append(f"stack PR #{number} is missing from GitHub inventory")
            continue
        comparisons = {
            "baseBranch": row.get("baseBranch"),
            "headBranch": row.get("headBranch"),
            "headSha": row.get("headSha"),
        }
        if row.get("baseSha") is not None:
            comparisons["baseSha"] = row.get("baseSha")
        for field, expected in comparisons.items():
            if observed.get(field) != expected:
                errors.append(f"stack PR #{number} {field} differs from GitHub inventory")
        if observed.get("state") != "open" or observed.get("draft") is not True or observed.get("mergeable") is not True:
            errors.append(f"stack PR #{number} is not open, draft, and mergeable")
    if set(live_rows) != {row.get("number") for row in stack_rows}:
        errors.append("PR inventory and stack manifest contain different PR number sets")
    if inventory.get("authority") != {"ceiling": "none", "mayMutatePullRequests": False}:
        errors.append("PR inventory authority boundary is not exact")

    baseline = stack.get("mainBaseline", {})
    if collision.get("mainHead") != baseline.get("mainHead"):
        errors.append("collision map mainHead differs from stack baseline")
    if collision.get("stackHeadBeforeConvergence") != stack.get("terminalHeadSha"):
        errors.append("collision map stack head differs from stack terminal head")
    if collision.get("mergeBase") != baseline.get("mergeBase"):
        errors.append("collision map merge base differs from stack baseline")
    if collision.get("remainingConflicts") != []:
        errors.append("collision map retains unresolved conflicts")
    strategy = collision.get("mergeStrategy", {})
    if strategy.get("type") != "two-parent-content-converged-merge" or strategy.get("rewriteHistory") is not False:
        errors.append("collision map merge strategy is unsupported")

    if runtime.get("kind") != "ValidationRuntimeMatrix":
        errors.append("unsupported runtime matrix")
    supported = runtime.get("supported", [])
    if len(supported) != 1 or supported[0].get("runtime") != "cpython" or supported[0].get("version") != "3.12":
        errors.append("runtime matrix must identify CPython 3.12 as the supported validator")
    if runtime.get("environment", {}).get("networkRequiredDuringValidation") is not False:
        errors.append("validation runtime must not require network access")

    receipt = {
        "apiVersion": "modos.pleiades/v1alpha1",
        "kind": "ConvergenceMetadataReceipt",
        "status": "valid" if not errors else "invalid",
        "contractGovernanceDigest": digest(governance),
        "pullRequestInventoryDigest": digest(inventory),
        "stackManifestDigest": digest(stack),
        "collisionMapDigest": digest(collision),
        "runtimeMatrixDigest": digest(runtime),
        "contractCount": len(contract_paths),
        "familyCount": len(family_rows),
        "pullRequestCount": len(stack_rows),
        "errors": sorted(errors),
        "authority": {"ceiling": "none", "canonicalMutationApplied": False},
    }
    receipt["receiptDigest"] = digest(receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--report", type=Path, default=Path("artifacts/convergence-metadata-receipt.json"))
    args = parser.parse_args()
    try:
        receipt = validate(args.root.resolve())
        report = args.report if args.report.is_absolute() else args.root.resolve() / args.report
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if receipt["errors"]:
            for error in receipt["errors"]:
                print(f"error: {error}", file=sys.stderr)
            return 1
        print(f"convergence metadata valid: {receipt['receiptDigest']}")
        return 0
    except (OSError, json.JSONDecodeError, MetadataError) as exc:
        print(f"convergence metadata validation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
