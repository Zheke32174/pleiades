#!/usr/bin/env python3
"""Scan public tree/history for identity-bearing paths without logging content."""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable


class ScanError(ValueError):
    pass


def _no_duplicate_keys(pairs: Iterable[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ScanError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle, object_pairs_hook=_no_duplicate_keys)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_bytes(value)).hexdigest()


def line_hashes(line: bytes) -> set[str]:
    variants = {line, line.rstrip(b"\r\n"), line.strip()}
    return {hashlib.sha256(value).hexdigest() for value in variants}


def text_lines(data: bytes) -> list[bytes] | None:
    if b"\x00" in data[:8192]:
        return None
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return None
    return data.splitlines(keepends=True)


def is_allowed(policy: dict[str, Any], path: str, rule: str, decoded_line: str) -> bool:
    for row in policy.get("allowlist", []):
        if row.get("rule") != rule:
            continue
        if not fnmatch.fnmatch(path, row.get("path", "")):
            continue
        literal = row.get("literal")
        if isinstance(literal, str) and literal in decoded_line:
            return True
    return False


def scan_blob(policy: dict[str, Any], path: str, data: bytes, blob_sha: str | None) -> list[dict[str, Any]]:
    lines = text_lines(data)
    if lines is None:
        return []
    known = set(policy["knownLineHashPrefixes"])
    prefix_length = policy["outputPolicy"]["hashPrefixLength"]
    compiled = [(row["id"], re.compile(row["pattern"])) for row in policy["rules"]]
    findings: list[dict[str, Any]] = []
    seen: set[tuple[int, str, str]] = set()

    for number, line in enumerate(lines, 1):
        hashes = line_hashes(line)
        decoded = line.decode("utf-8", errors="replace")
        for full_hash in hashes:
            prefix = full_hash[:prefix_length]
            if prefix in known:
                key = (number, "known-sensitive-line-hash", prefix)
                if key not in seen:
                    findings.append({
                        "path": path,
                        "blobSha": blob_sha,
                        "lineNumber": number,
                        "rule": "known-sensitive-line-hash",
                        "lineHashPrefix": prefix,
                    })
                    seen.add(key)
        for rule_id, pattern in compiled:
            if not pattern.search(decoded) or is_allowed(policy, path, rule_id, decoded):
                continue
            prefix = min(hashes)[:prefix_length]
            key = (number, rule_id, prefix)
            if key not in seen:
                findings.append({
                    "path": path,
                    "blobSha": blob_sha,
                    "lineNumber": number,
                    "rule": rule_id,
                    "lineHashPrefix": prefix,
                })
                seen.add(key)
    return findings


def run_git(root: Path, *args: str) -> bytes:
    completed = subprocess.run(["git", *args], cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if completed.returncode != 0:
        raise ScanError(completed.stderr.decode("utf-8", errors="replace").strip() or "git command failed")
    return completed.stdout


def scan_current(root: Path, policy: dict[str, Any]) -> list[dict[str, Any]]:
    paths = run_git(root, "ls-files", "-z").split(b"\x00")
    findings: list[dict[str, Any]] = []
    for raw_path in paths:
        if not raw_path:
            continue
        path = raw_path.decode("utf-8", errors="surrogateescape")
        file_path = root / path
        if not file_path.is_file():
            continue
        try:
            findings.extend(scan_blob(policy, path, file_path.read_bytes(), None))
        except OSError as exc:
            raise ScanError(f"cannot read {path}: {exc}") from exc
    return findings


def scan_history(root: Path, policy: dict[str, Any]) -> list[dict[str, Any]]:
    rows = run_git(root, "rev-list", "--objects", "--all").decode("utf-8", errors="replace").splitlines()
    findings: list[dict[str, Any]] = []
    scanned: set[str] = set()
    for row in rows:
        parts = row.split(" ", 1)
        object_sha = parts[0]
        path = parts[1] if len(parts) == 2 else "<unpathed>"
        if object_sha in scanned:
            continue
        object_type = run_git(root, "cat-file", "-t", object_sha).decode().strip()
        if object_type != "blob":
            continue
        scanned.add(object_sha)
        data = run_git(root, "cat-file", "blob", object_sha)
        findings.extend(scan_blob(policy, path, data, object_sha))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--policy", type=Path, default=Path("ci/public-history-sensitivity.json"))
    parser.add_argument("--mode", choices=["current", "history", "all"], default="current")
    parser.add_argument("--report", type=Path, default=Path("artifacts/public-history-scan.json"))
    args = parser.parse_args()
    root = args.root.resolve()
    policy_path = args.policy if args.policy.is_absolute() else root / args.policy
    report_path = args.report if args.report.is_absolute() else root / args.report
    try:
        policy = load(policy_path)
        if policy.get("authority") != {"ceiling": "none", "historyRewriteAuthorized": False}:
            raise ScanError("sensitivity policy authority boundary is not exact")
        findings: list[dict[str, Any]] = []
        if args.mode in {"current", "all"}:
            findings.extend({"scope": "current-tree", **row} for row in scan_current(root, policy))
        if args.mode in {"history", "all"}:
            findings.extend({"scope": "reachable-history", **row} for row in scan_history(root, policy))
        findings = sorted(findings, key=lambda row: (row["scope"], row["path"], row["blobSha"] or "", row["lineNumber"], row["rule"]))
        receipt = {
            "apiVersion": "modos.pleiades/v1alpha1",
            "kind": "PublicHistorySensitivityReceipt",
            "policyId": policy["policyId"],
            "policyDigest": digest(policy),
            "mode": args.mode,
            "status": "clear" if not findings else "blocked",
            "findingCount": len(findings),
            "findings": findings,
            "contentDisclosed": False,
            "historyRewriteAuthorized": False,
            "authority": {"ceiling": "none", "canonicalMutationApplied": False},
        }
        receipt["receiptDigest"] = digest(receipt)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"public history scan {receipt['status']}: {receipt['findingCount']} findings; {receipt['receiptDigest']}")
        return 0 if not findings else 2
    except (OSError, json.JSONDecodeError, ScanError) as exc:
        print(f"public history scan failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
