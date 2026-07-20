#!/usr/bin/env python3
"""Build a reproducible, secret-free MODOS validation package."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
import subprocess
import sys
import tarfile
from pathlib import Path
from typing import Any

INCLUDE_ROOTS = (
    Path("MODOS_COMPONENT.yaml"),
    Path("requirements-modos.txt"),
    Path("ci"),
    Path("modos/contracts"),
    Path("modos/ecology"),
    Path("modos/ontology"),
    Path("modos/governance"),
    Path("modos/convergence"),
    Path("modos/EXECUTIVE_AUTHORITY.md"),
    Path("modos/ECOLOGY_PROGRESSION_100.md"),
    Path("modos/ECOLOGY_PROGRESSION_200.md"),
)
EXCLUDED_PARTS = {"__pycache__", ".pytest_cache", "artifacts", "target", ".git"}
ALLOWED_SUFFIXES = {".py", ".json", ".md", ".sql", ".txt", ".yaml", ".yml", ".toml", ".proto"}


class PackageError(ValueError):
    pass


def sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def source_commit(root: Path, explicit: str | None) -> str:
    if explicit:
        if len(explicit) != 40 or any(ch not in "0123456789abcdef" for ch in explicit):
            raise PackageError("source commit must be a lowercase 40-character Git SHA")
        return explicit
    completed = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if completed.returncode != 0:
        raise PackageError("cannot resolve source commit")
    value = completed.stdout.decode().strip()
    if len(value) != 40:
        raise PackageError("resolved source commit is invalid")
    return value


def selected_files(root: Path) -> list[Path]:
    rows: set[Path] = set()
    for item in INCLUDE_ROOTS:
        absolute = root / item
        if absolute.is_file():
            rows.add(item)
            continue
        if not absolute.is_dir():
            continue
        for path in absolute.rglob("*"):
            if not path.is_file():
                continue
            relative = path.relative_to(root)
            if any(part in EXCLUDED_PARTS for part in relative.parts):
                continue
            if path.suffix not in ALLOWED_SUFFIXES and path.name not in {"CODEOWNERS"}:
                continue
            rows.add(relative)
    return sorted(rows, key=lambda row: row.as_posix())


def normalized_info(path: str, size: int) -> tarfile.TarInfo:
    info = tarfile.TarInfo(path)
    info.size = size
    info.mtime = 0
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    info.mode = 0o755 if path.endswith(".py") else 0o644
    return info


def build(root: Path, output: Path, commit: str) -> dict[str, Any]:
    files = selected_files(root)
    if not files:
        raise PackageError("no package files selected")
    entries: list[dict[str, Any]] = []
    payloads: list[tuple[str, bytes]] = []
    for relative in files:
        data = (root / relative).read_bytes()
        path = relative.as_posix()
        payloads.append((path, data))
        entries.append({"path": path, "bytes": len(data), "digest": sha256_bytes(data)})

    manifest = {
        "apiVersion": "modos.pleiades/v1alpha1",
        "kind": "ValidationPackageManifest",
        "sourceCommit": commit,
        "pythonCompatibility": ">=3.12,<3.13",
        "networkResolutionAllowed": False,
        "privateMaterialIncluded": False,
        "fileCount": len(entries),
        "files": entries,
        "authority": {"ceiling": "none", "canonicalMutationApplied": False},
    }
    manifest["manifestDigest"] = sha256_bytes(canonical_bytes(manifest))
    manifest_bytes = json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    payloads.append(("PACKAGE_MANIFEST.json", manifest_bytes))

    output.parent.mkdir(parents=True, exist_ok=True)
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w", format=tarfile.PAX_FORMAT) as archive:
        for path, data in sorted(payloads):
            archive.addfile(normalized_info(path, len(data)), io.BytesIO(data))
    with output.open("wb") as handle:
        with gzip.GzipFile(filename="", mode="wb", fileobj=handle, mtime=0, compresslevel=9) as gz:
            gz.write(raw.getvalue())

    package_bytes = output.read_bytes()
    receipt = {
        "apiVersion": "modos.pleiades/v1alpha1",
        "kind": "ValidationPackageReceipt",
        "sourceCommit": commit,
        "manifestDigest": manifest["manifestDigest"],
        "packageDigest": sha256_bytes(package_bytes),
        "packageBytes": len(package_bytes),
        "fileCount": len(entries),
        "reproducibleMetadata": True,
        "networkResolutionAllowed": False,
        "privateMaterialIncluded": False,
        "authority": {"ceiling": "none", "canonicalMutationApplied": False},
    }
    receipt["receiptDigest"] = sha256_bytes(canonical_bytes(receipt))
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, default=Path("artifacts/pleiades-modos-validation.tar.gz"))
    parser.add_argument("--receipt", type=Path, default=Path("artifacts/validation-package-receipt.json"))
    parser.add_argument("--source-commit")
    args = parser.parse_args()
    root = args.root.resolve()
    output = args.output if args.output.is_absolute() else root / args.output
    receipt_path = args.receipt if args.receipt.is_absolute() else root / args.receipt
    try:
        receipt = build(root, output, source_commit(root, args.source_commit or os.environ.get("GITHUB_SHA")))
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"validation package built: {receipt['packageDigest']}")
        return 0
    except (OSError, PackageError) as exc:
        print(f"validation package build failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
