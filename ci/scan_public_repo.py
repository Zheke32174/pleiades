#!/usr/bin/env python3
"""Review the public tree and release-candidate history for configured sensitive patterns."""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import subprocess
import sys
from dataclasses import dataclass

MAX_BLOB_BYTES = 2 * 1024 * 1024
SELF_PATH = "ci/scan_public_repo.py"
ALLOWLIST_PATH = "ci/public-sensitivity-allowlist.json"
ALLOWLIST_SCHEMA = "pleiades.public-sensitivity-allowlist/v1"


@dataclass(frozen=True)
class Rule:
    name: str
    expression: re.Pattern[str]


@dataclass(frozen=True)
class Finding:
    scope: str
    identity: str
    path: str
    line_number: int
    rule: str
    line_sha256: str

    @property
    def allowlist_key(self) -> tuple[str, str, str]:
        return (self.path, self.rule, self.line_sha256)

    def render(self) -> str:
        return (
            f"{self.scope}: {self.identity}:{self.path}:{self.line_number}: "
            f"{self.rule} line_sha256={self.line_sha256}"
        )


def joined(*parts: str) -> str:
    return "".join(parts)


RULES = [
    Rule("private-key-header", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")),
    Rule("github-classic-token", re.compile(re.escape(joined("gh", "p_")) + r"[A-Za-z0-9]{20,}")),
    Rule("github-fine-grained-token", re.compile(re.escape(joined("github", "_pat_")) + r"[A-Za-z0-9_]{20,}")),
    Rule("aws-access-key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    Rule("google-api-key", re.compile(re.escape(joined("AI", "za")) + r"[A-Za-z0-9_-]{24,}")),
    Rule("tailscale-auth-key", re.compile(re.escape(joined("ts", "key-")) + r"[A-Za-z0-9_-]{12,}")),
    Rule(
        "generic-secret-assignment",
        re.compile(
            r"(?i)\b(?:api[_-]?key|access[_-]?token|auth[_-]?token|client[_-]?secret|password|private[_-]?key)\b"
            r"\s*[:=]\s*['\"]?[A-Za-z0-9+/_.=-]{12,}"
        ),
    ),
    Rule("linux-user-home", re.compile(r"(?<![A-Za-z0-9])/(?:home|Users)/[A-Za-z0-9._-]+/")),
    Rule("windows-user-home", re.compile(r"(?i)\b[A-Z]:\\Users\\[A-Za-z0-9._ -]+\\")),
    Rule("tailnet-hostname", re.compile(r"\b[a-z0-9-]+\.[a-z0-9-]+\.ts\.net\b", re.IGNORECASE)),
    Rule(
        "carrier-grade-private-address",
        re.compile(r"\b100\.(?:6[4-9]|[7-9][0-9]|1[01][0-9]|12[0-7])(?:\.[0-9]{1,3}){2}\b"),
    ),
]
RULE_NAMES = {rule.name for rule in RULES}


def git(root: pathlib.Path, *args: str, text: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        check=False,
        capture_output=True,
        text=text,
    )


def decode_text(data: bytes) -> str | None:
    if len(data) > MAX_BLOB_BYTES or b"\0" in data:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def load_allowlist(root: pathlib.Path) -> dict[tuple[str, str, str], str]:
    path = root / ALLOWLIST_PATH
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or document.get("schema") != ALLOWLIST_SCHEMA:
        raise RuntimeError(f"{ALLOWLIST_PATH} must use schema {ALLOWLIST_SCHEMA}")
    entries = document.get("entries")
    if not isinstance(entries, list):
        raise RuntimeError(f"{ALLOWLIST_PATH} entries must be an array")

    allowlist: dict[tuple[str, str, str], str] = {}
    ordered_keys: list[tuple[str, str, str]] = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict) or set(entry) != {"path", "rule", "line_sha256", "reason"}:
            raise RuntimeError(f"{ALLOWLIST_PATH} entry {index} has an invalid shape")
        item_path = entry["path"]
        rule = entry["rule"]
        digest = entry["line_sha256"]
        reason = entry["reason"]
        if not isinstance(item_path, str) or not item_path or item_path.startswith("/") or ".." in pathlib.PurePosixPath(item_path).parts:
            raise RuntimeError(f"{ALLOWLIST_PATH} entry {index} has an unsafe path")
        if rule not in RULE_NAMES:
            raise RuntimeError(f"{ALLOWLIST_PATH} entry {index} names an unknown rule: {rule}")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{12}", digest):
            raise RuntimeError(f"{ALLOWLIST_PATH} entry {index} has an invalid line hash")
        if not isinstance(reason, str) or not reason.strip():
            raise RuntimeError(f"{ALLOWLIST_PATH} entry {index} needs a reason")
        key = (item_path, rule, digest)
        if key in allowlist:
            raise RuntimeError(f"duplicate sensitivity allowlist entry: {key}")
        allowlist[key] = reason.strip()
        ordered_keys.append(key)

    if ordered_keys != sorted(ordered_keys):
        raise RuntimeError(f"{ALLOWLIST_PATH} entries must be sorted by path, rule, and line hash")
    return allowlist


def scan_text(scope: str, identity: str, path: str, text: str) -> list[Finding]:
    if path == SELF_PATH:
        return []
    findings: list[Finding] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        for rule in RULES:
            if rule.expression.search(line):
                findings.append(
                    Finding(
                        scope=scope,
                        identity=identity,
                        path=path,
                        line_number=line_number,
                        rule=rule.name,
                        line_sha256=hashlib.sha256(line.encode("utf-8")).hexdigest()[:12],
                    )
                )
    return findings


def scan_current(root: pathlib.Path) -> list[Finding]:
    listed = git(root, "ls-files", "-s", "-z", text=False)
    if listed.returncode != 0:
        raise RuntimeError(listed.stderr.decode("utf-8", errors="replace"))
    findings: list[Finding] = []
    for record in listed.stdout.split(b"\0"):
        if not record:
            continue
        metadata, separator, raw_path = record.partition(b"\t")
        if not separator:
            raise RuntimeError("unexpected git ls-files record")
        mode, object_sha, stage = metadata.decode("ascii").split()
        path = raw_path.decode("utf-8")
        if stage != "0":
            raise RuntimeError(f"unmerged index entry cannot be scanned: {path}")
        if mode == "160000":
            continue
        content = git(root, "cat-file", "blob", object_sha, text=False)
        if content.returncode != 0:
            raise RuntimeError(
                content.stderr.decode("utf-8", errors="replace").strip()
                or f"cannot read tracked blob {object_sha}: {path}"
            )
        text = decode_text(content.stdout)
        if text is not None:
            findings.extend(scan_text("current", object_sha, path, text))
    return findings


def scan_history(root: pathlib.Path) -> list[Finding]:
    objects = git(root, "rev-list", "--objects", "HEAD")
    if objects.returncode != 0:
        raise RuntimeError(objects.stderr)
    findings: list[Finding] = []
    visited: set[str] = set()
    for line in objects.stdout.splitlines():
        sha, separator, path = line.partition(" ")
        if not separator or not path or sha in visited or path == SELF_PATH:
            continue
        visited.add(sha)
        kind = git(root, "cat-file", "-t", sha)
        size = git(root, "cat-file", "-s", sha)
        if kind.returncode != 0 or kind.stdout.strip() != "blob" or size.returncode != 0:
            continue
        if int(size.stdout.strip()) > MAX_BLOB_BYTES:
            continue
        content = git(root, "cat-file", "blob", sha, text=False)
        if content.returncode != 0:
            continue
        text = decode_text(content.stdout)
        if text is not None:
            findings.extend(scan_text("history", sha, path, text))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--current-only", action="store_true")
    args = parser.parse_args()
    root = pathlib.Path(__file__).resolve().parents[1]
    allowlist = load_allowlist(root)
    findings = scan_current(root)
    if not args.current_only:
        findings.extend(scan_history(root))

    encountered_keys = {finding.allowlist_key for finding in findings}
    stale_keys = sorted(set(allowlist) - encountered_keys)
    unreviewed = sorted(
        {finding.render() for finding in findings if finding.allowlist_key not in allowlist}
    )
    allowed_count = sum(1 for finding in findings if finding.allowlist_key in allowlist)

    if stale_keys:
        print("Sensitivity allowlist contains stale or unexercised entries:", file=sys.stderr)
        for key in stale_keys:
            print(f"  path={key[0]} rule={key[1]} line_sha256={key[2]}", file=sys.stderr)
    if unreviewed:
        print("Public repository sensitivity scan requires review:", file=sys.stderr)
        for finding in unreviewed:
            print(f"  {finding}", file=sys.stderr)
    if stale_keys or unreviewed:
        return 1

    scope = "current tree" if args.current_only else "current tree and history reachable from HEAD"
    print(f"PASS: no unreviewed sensitive patterns found in {scope}")
    print(f"PASS: {allowed_count} exact reviewed synthetic finding occurrence(s) matched the allowlist")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
