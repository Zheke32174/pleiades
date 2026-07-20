#!/usr/bin/env python3
"""Run the ordered MODOS convergence suite and emit one receipt."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable


class SuiteError(ValueError):
    pass


def _no_duplicate_keys(pairs: Iterable[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise SuiteError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle, object_pairs_hook=_no_duplicate_keys)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def digest(value: Any) -> str:
    return digest_bytes(canonical_bytes(value))


def validate_suite(suite: dict[str, Any]) -> None:
    if suite.get("apiVersion") != "modos.pleiades/v1alpha1" or suite.get("kind") != "ValidationSuite":
        raise SuiteError("unsupported suite envelope")
    commands = suite.get("commands")
    if not isinstance(commands, list) or not commands:
        raise SuiteError("suite commands must be a nonempty array")
    ids: set[str] = set()
    for index, row in enumerate(commands):
        if not isinstance(row, dict):
            raise SuiteError(f"command {index} must be an object")
        command_id = row.get("id")
        argv = row.get("argv")
        if not isinstance(command_id, str) or not command_id:
            raise SuiteError(f"command {index} id is required")
        if command_id in ids:
            raise SuiteError(f"duplicate command id: {command_id}")
        ids.add(command_id)
        if not isinstance(argv, list) or not argv or any(not isinstance(item, str) or not item for item in argv):
            raise SuiteError(f"command {command_id} argv must be a nonempty string array")
        if argv[0] not in {"python", "python3", "bash", "cargo"}:
            raise SuiteError(f"command {command_id} uses an unsupported executable: {argv[0]}")
    if suite.get("authority") != {"ceiling": "none", "canonicalMutationApplied": False}:
        raise SuiteError("suite authority boundary is not exact")


def run_suite(root: Path, suite: dict[str, Any], stop_on_failure: bool) -> dict[str, Any]:
    validate_suite(suite)
    results: list[dict[str, Any]] = []
    env = dict(os.environ)
    env.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    env.setdefault("PYTHONHASHSEED", "0")

    for row in suite["commands"]:
        argv = row["argv"]
        completed = subprocess.run(
            argv,
            cwd=root,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        result = {
            "id": row["id"],
            "category": row["category"],
            "argv": argv,
            "exitCode": completed.returncode,
            "stdoutDigest": digest_bytes(completed.stdout),
            "stderrDigest": digest_bytes(completed.stderr),
            "status": "pass" if completed.returncode == 0 else "fail",
        }
        results.append(result)
        print(f"{result['status']}: {row['id']}")
        if completed.returncode != 0:
            if completed.stdout:
                sys.stdout.buffer.write(completed.stdout[-8192:])
            if completed.stderr:
                sys.stderr.buffer.write(completed.stderr[-8192:])
            if stop_on_failure:
                break

    failures = [row["id"] for row in results if row["status"] == "fail"]
    not_run = [row["id"] for row in suite["commands"][len(results):]]
    receipt = {
        "apiVersion": "modos.pleiades/v1alpha1",
        "kind": "ConvergenceSuiteReceipt",
        "suiteId": suite["suiteId"],
        "suiteDigest": digest(suite),
        "status": "pass" if not failures and not not_run else "fail",
        "commandCount": len(suite["commands"]),
        "executedCount": len(results),
        "results": results,
        "failures": failures,
        "notRun": not_run,
        "authority": {"ceiling": "none", "canonicalMutationApplied": False},
    }
    receipt["receiptDigest"] = digest(receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--suite", type=Path, default=Path("modos/convergence/validation-suite.json"))
    parser.add_argument("--report", type=Path, default=Path("artifacts/convergence-suite-receipt.json"))
    parser.add_argument("--continue-on-failure", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    suite_path = args.suite if args.suite.is_absolute() else root / args.suite
    report_path = args.report if args.report.is_absolute() else root / args.report
    try:
        suite = load(suite_path)
        receipt = run_suite(root, suite, stop_on_failure=not args.continue_on_failure)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"convergence suite {receipt['status']}: {receipt['receiptDigest']}")
        return 0 if receipt["status"] == "pass" else 1
    except (OSError, json.JSONDecodeError, SuiteError) as exc:
        print(f"convergence suite failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
