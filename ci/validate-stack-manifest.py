#!/usr/bin/env python3
"""Validate the exact stacked PR ancestry and blocker ledger."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Iterable

SHA40 = set("0123456789abcdef")


class StackError(ValueError):
    pass


def _no_duplicate_keys(pairs: Iterable[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise StackError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle, object_pairs_hook=_no_duplicate_keys)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_bytes(value)).hexdigest()


def is_sha(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 40 and set(value) <= SHA40


def validate_stack(manifest: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if manifest.get("apiVersion") != "modos.pleiades/v1alpha1" or manifest.get("kind") != "StackManifest":
        raise StackError("unsupported stack manifest envelope")
    rows = manifest.get("pullRequests")
    if not isinstance(rows, list) or not rows:
        raise StackError("pullRequests must be a nonempty array")

    numbers: set[int] = set()
    heads: set[str] = set()
    head_shas: set[str] = set()
    for index, row in enumerate(rows):
        number = row.get("number")
        head_branch = row.get("headBranch")
        head_sha = row.get("headSha")
        if not isinstance(number, int) or isinstance(number, bool) or number < 1:
            errors.append(f"row {index} has invalid PR number")
        elif number in numbers:
            errors.append(f"duplicate PR number: {number}")
        else:
            numbers.add(number)
        if not isinstance(head_branch, str) or not head_branch:
            errors.append(f"row {index} has invalid headBranch")
        elif head_branch in heads:
            errors.append(f"duplicate head branch: {head_branch}")
        else:
            heads.add(head_branch)
        if not is_sha(head_sha):
            errors.append(f"row {index} has invalid headSha")
        elif head_sha in head_shas:
            errors.append(f"duplicate head SHA: {head_sha}")
        else:
            head_shas.add(head_sha)

        if index > 0:
            previous = rows[index - 1]
            if row.get("baseBranch") != previous.get("headBranch"):
                errors.append(f"PR #{number} baseBranch does not match prior headBranch")
            if row.get("baseSha") != previous.get("headSha"):
                errors.append(f"PR #{number} baseSha does not match prior headSha")

    terminal = rows[-1]
    if manifest.get("terminalBranch") != terminal.get("headBranch"):
        errors.append("terminalBranch does not match final PR headBranch")
    if manifest.get("terminalHeadSha") != terminal.get("headSha"):
        errors.append("terminalHeadSha does not match final PR headSha")

    baseline = manifest.get("mainBaseline")
    if not isinstance(baseline, dict):
        errors.append("mainBaseline is required")
    else:
        for field in ("mainHead", "mergeBase", "terminalHead"):
            if not is_sha(baseline.get(field)):
                errors.append(f"mainBaseline.{field} must be an exact Git SHA")
        if baseline.get("terminalHead") != manifest.get("terminalHeadSha"):
            errors.append("mainBaseline terminalHead differs from terminalHeadSha")
        for field in ("terminalAheadBy", "terminalBehindBy"):
            value = baseline.get(field)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                errors.append(f"mainBaseline.{field} must be a nonnegative integer")

    blockers = manifest.get("blockers")
    if not isinstance(blockers, list) or not blockers or any(not isinstance(row, str) or not row for row in blockers):
        errors.append("blockers must be a nonempty string array")
    elif len(blockers) != len(set(blockers)):
        errors.append("blockers must be unique")
    if manifest.get("authority") != {"ceiling": "none", "canonicalMutationApplied": False}:
        errors.append("stack manifest authority boundary is not exact")

    receipt = {
        "apiVersion": "modos.pleiades/v1alpha1",
        "kind": "StackClosureReceipt",
        "status": "valid" if not errors else "invalid",
        "stackId": manifest["stackId"],
        "stackDigest": digest(manifest),
        "pullRequestCount": len(rows),
        "firstPullRequest": rows[0]["number"],
        "lastPullRequest": terminal["number"],
        "terminalBranch": manifest["terminalBranch"],
        "terminalHeadSha": manifest["terminalHeadSha"],
        "mainAheadBy": baseline.get("terminalAheadBy") if isinstance(baseline, dict) else None,
        "mainBehindBy": baseline.get("terminalBehindBy") if isinstance(baseline, dict) else None,
        "blockers": sorted(blockers) if isinstance(blockers, list) else [],
        "errors": sorted(errors),
        "authority": {"ceiling": "none", "canonicalMutationApplied": False},
    }
    receipt["receiptDigest"] = digest(receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=Path("modos/convergence/stack-manifest.json"))
    parser.add_argument("--report", type=Path, default=Path("artifacts/stack-closure-receipt.json"))
    args = parser.parse_args()
    try:
        receipt = validate_stack(load(args.manifest))
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if receipt["errors"]:
            for error in receipt["errors"]:
                print(f"error: {error}", file=sys.stderr)
            return 1
        print(f"stack closed: {receipt['pullRequestCount']} PRs; {receipt['receiptDigest']}")
        return 0
    except (OSError, json.JSONDecodeError, StackError) as exc:
        print(f"stack validation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
