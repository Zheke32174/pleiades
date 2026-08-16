#!/usr/bin/env python3
"""Validate required operator runbook coverage and public-safety invariants."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

REQUIRED_HEADINGS = [
    "## 1. Aggregate convergence suite",
    "## 2. Private exhaustive-registry closure",
    "## 3. Delegated authority grant issuance and revocation",
    "## 4. Canary deployment",
    "## 5. Rollback after failed postconditions",
    "## 6. Emergency safe mode and recovery quorum",
    "## 7. Public-history rewrite authorization and recovery",
    "## 8. Evidence archival and retention",
    "## 9. Sustained bounded-autonomy observation",
    "## 10. Operator acceptance checklist",
]
REQUIRED_PHRASES = [
    "do not authorize",
    "private key material",
    "exact predecessor digest",
    "issue `github:Zheke32174/pleiades#42`",
    "Repository automation must stop rather than infer consent",
]
FORBIDDEN_PATTERNS = [
    ("pem-private-key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("literal-linux-home", re.compile(r"/home/[A-Za-z0-9._-]+/")),
    ("literal-windows-profile", re.compile(r"(?:[A-Za-z]:\\\\|/mnt/[A-Za-z]/)Users[/\\\\][A-Za-z0-9._ -]+[/\\\\]")),
    ("known-workstation-identity", re.compile(r"fixxia", re.IGNORECASE)),
]


def digest_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def validate(path: Path) -> dict:
    data = path.read_bytes()
    text = data.decode("utf-8")
    errors: list[str] = []
    positions: list[int] = []
    for heading in REQUIRED_HEADINGS:
        position = text.find(heading)
        if position < 0:
            errors.append("missing heading: " + heading)
        else:
            positions.append(position)
    if positions and positions != sorted(positions):
        errors.append("required headings are out of order")
    lowered = text.lower()
    for phrase in REQUIRED_PHRASES:
        if phrase.lower() not in lowered:
            errors.append("missing required phrase: " + phrase)
    for rule, pattern in FORBIDDEN_PATTERNS:
        if pattern.search(text):
            errors.append("forbidden public runbook content: " + rule)
    checklist_items = sum(1 for line in text.splitlines() if line.startswith("- [ ] "))
    if checklist_items < 15:
        errors.append("operator acceptance checklist has fewer than 15 items")
    receipt = {
        "apiVersion": "modos.pleiades/v1alpha1",
        "kind": "OperatorRunbookValidationReceipt",
        "status": "valid" if not errors else "invalid",
        "runbookDigest": digest_bytes(data),
        "requiredSectionCount": len(REQUIRED_HEADINGS),
        "checklistItemCount": checklist_items,
        "errors": sorted(errors),
        "privateMaterialIncluded": False,
        "authority": {"ceiling": "none", "canonicalMutationApplied": False},
    }
    receipt["receiptDigest"] = digest_bytes(json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runbook", type=Path, default=Path("modos/convergence/OPERATOR_RUNBOOKS.md"))
    parser.add_argument("--report", type=Path, default=Path("artifacts/operator-runbook-validation.json"))
    args = parser.parse_args()
    try:
        receipt = validate(args.runbook)
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if receipt["errors"]:
            for error in receipt["errors"]:
                print(f"error: {error}", file=sys.stderr)
            return 1
        print(f"operator runbooks valid: {receipt['receiptDigest']}")
        return 0
    except (OSError, UnicodeDecodeError) as exc:
        print(f"operator runbook validation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
