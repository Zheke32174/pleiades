#!/usr/bin/env python3
"""Build the deterministic Pleiades lean source archive, SPDX inventory, and receipt."""

from __future__ import annotations

import argparse
import datetime as dt
import gzip
import hashlib
import io
import json
import pathlib
import re
import subprocess
import tarfile
from dataclasses import dataclass

VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?$")
RECEIPT_SCHEMA = "pleiades.lean.source-release/v1"
EXCLUDED_PREFIXES = ("root.x86_64/", "experimental/", "modos/")


@dataclass(frozen=True)
class GitEntry:
    mode: str
    kind: str
    sha: str
    path: str


def run_git(root: pathlib.Path, *args: str, binary: bool = False) -> str | bytes:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        check=False,
        capture_output=True,
        text=not binary,
    )
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace") if binary else result.stderr
        raise SystemExit(f"git {' '.join(args)} failed: {detail.strip()}")
    return result.stdout


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_roots(root: pathlib.Path) -> list[str]:
    path = root / "release" / "source-paths.txt"
    roots = [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if not roots:
        raise SystemExit("release/source-paths.txt must not be empty")
    if roots != sorted(roots) or len(roots) != len(set(roots)):
        raise SystemExit("release/source-paths.txt must be sorted and unique")
    for value in roots:
        pure = pathlib.PurePosixPath(value)
        if value.startswith("/") or ".." in pure.parts or value.endswith("/"):
            raise SystemExit(f"unsafe release root: {value}")
        if value == ".git" or value.startswith(".git/"):
            raise SystemExit(".git cannot be a release root")
    return roots


def resolve_entries(root: pathlib.Path, commit: str, roots: list[str]) -> list[GitEntry]:
    raw = bytes(run_git(root, "ls-tree", "-r", "-z", commit, "--", *roots, binary=True))
    entries: list[GitEntry] = []
    for record in raw.split(b"\0"):
        if not record:
            continue
        metadata, separator, raw_path = record.partition(b"\t")
        if not separator:
            raise SystemExit("unexpected git ls-tree record")
        mode, kind, object_sha = metadata.decode("ascii").split()
        path = raw_path.decode("utf-8")
        if kind != "blob" or mode == "160000":
            raise SystemExit(f"unsupported release entry {mode} {kind}: {path}")
        if path.startswith(EXCLUDED_PREFIXES):
            raise SystemExit(f"excluded path entered release scope: {path}")
        entries.append(GitEntry(mode=mode, kind=kind, sha=object_sha, path=path))
    if not entries:
        raise SystemExit("release roots resolved to no files")
    paths = [entry.path for entry in entries]
    if paths != sorted(paths) or len(paths) != len(set(paths)):
        raise SystemExit("resolved release file list is not sorted and unique")
    for release_root in roots:
        if not any(entry.path == release_root or entry.path.startswith(release_root + "/") for entry in entries):
            raise SystemExit(f"release root missing from exact commit: {release_root}")
    return entries


def spdx_id(path: str) -> str:
    return f"SPDXRef-File-{hashlib.sha256(path.encode('utf-8')).hexdigest()[:24]}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=pathlib.Path, default=pathlib.Path("dist"))
    args = parser.parse_args()

    root = pathlib.Path(__file__).resolve().parents[1]
    version = (root / "VERSION").read_text(encoding="utf-8").strip()
    if not VERSION_RE.fullmatch(version):
        raise SystemExit(f"invalid VERSION: {version}")

    dirty = str(run_git(root, "status", "--porcelain", "--untracked-files=no"))
    if dirty:
        raise SystemExit("tracked working tree is dirty; package only an exact reviewed commit")

    commit = str(run_git(root, "rev-parse", "HEAD")).strip()
    epoch = int(str(run_git(root, "show", "-s", "--format=%ct", commit)).strip())
    created = dt.datetime.fromtimestamp(epoch, tz=dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    roots = read_roots(root)
    entries = resolve_entries(root, commit, roots)
    prefix = f"pleiades-lean-{version}"

    output = args.output if args.output.is_absolute() else root / args.output
    output.mkdir(parents=True, exist_ok=True)
    for child in output.iterdir():
        if child.is_file():
            child.unlink()

    archive_path = output / f"{prefix}.tar.gz"
    file_records: list[dict[str, object]] = []
    with archive_path.open("wb") as raw_output:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw_output, compresslevel=9, mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w|", format=tarfile.PAX_FORMAT) as archive:
                for entry in entries:
                    data = bytes(run_git(root, "cat-file", "blob", entry.sha, binary=True))
                    archive_name = f"{prefix}/{entry.path}"
                    info = tarfile.TarInfo(archive_name)
                    info.mtime = epoch
                    info.uid = 0
                    info.gid = 0
                    info.uname = ""
                    info.gname = ""
                    if entry.mode == "120000":
                        target = data.decode("utf-8")
                        pure_target = pathlib.PurePosixPath(target)
                        if target.startswith("/") or ".." in pure_target.parts:
                            raise SystemExit(f"unsafe release symlink target: {entry.path} -> {target}")
                        info.type = tarfile.SYMTYPE
                        info.mode = 0o777
                        info.linkname = target
                        info.size = 0
                        archive.addfile(info)
                    else:
                        info.type = tarfile.REGTYPE
                        info.mode = 0o755 if entry.mode == "100755" else 0o644
                        info.size = len(data)
                        archive.addfile(info, io.BytesIO(data))
                    file_records.append(
                        {
                            "path": entry.path,
                            "sha256": sha256(data),
                            "size": len(data),
                            "git_mode": entry.mode,
                            "spdx_id": spdx_id(entry.path),
                        }
                    )

    relationships = [
        {
            "spdxElementId": "SPDXRef-DOCUMENT",
            "relationshipType": "DESCRIBES",
            "relatedSpdxElement": "SPDXRef-Package",
        }
    ]
    spdx_files = []
    for record in file_records:
        spdx_files.append(
            {
                "fileName": f"./{record['path']}",
                "SPDXID": record["spdx_id"],
                "checksums": [{"algorithm": "SHA256", "checksumValue": record["sha256"]}],
                "licenseConcluded": "NOASSERTION",
                "copyrightText": "NOASSERTION",
            }
        )
        relationships.append(
            {
                "spdxElementId": "SPDXRef-Package",
                "relationshipType": "CONTAINS",
                "relatedSpdxElement": record["spdx_id"],
            }
        )

    spdx_path = output / f"{prefix}.spdx.json"
    spdx = {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": prefix,
        "documentNamespace": f"https://github.com/Zheke32174/pleiades/sbom/{commit}/lean",
        "creationInfo": {"created": created, "creators": ["Tool: scripts/package_lean_source.py"]},
        "packages": [
            {
                "name": "pleiades-lean",
                "SPDXID": "SPDXRef-Package",
                "versionInfo": version,
                "downloadLocation": "NOASSERTION",
                "filesAnalyzed": True,
                "licenseConcluded": "MIT",
                "licenseDeclared": "MIT",
                "copyrightText": "Copyright (c) Pleiades contributors",
                "externalRefs": [
                    {
                        "referenceCategory": "PACKAGE-MANAGER",
                        "referenceType": "purl",
                        "referenceLocator": f"pkg:github/Zheke32174/pleiades@{commit}?subpath=lean",
                    }
                ],
            }
        ],
        "files": spdx_files,
        "relationships": relationships,
    }
    spdx_path.write_text(json.dumps(spdx, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    archive_hash = sha256(archive_path.read_bytes())
    spdx_hash = sha256(spdx_path.read_bytes())
    scope_hash = sha256((root / "release" / "source-paths.txt").read_bytes())
    receipt_path = output / f"{prefix}.build-receipt.json"
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "repository": "Zheke32174/pleiades",
        "release_component": "lean",
        "version": version,
        "commit": commit,
        "source_date_epoch": epoch,
        "created_from_commit_time": created,
        "scope": {
            "manifest": "release/source-paths.txt",
            "sha256": scope_hash,
            "roots": roots,
            "file_count": len(entries),
        },
        "archive": {"name": archive_path.name, "sha256": archive_hash},
        "sbom": {"name": spdx_path.name, "sha256": spdx_hash, "format": "SPDX-2.3 JSON"},
        "distribution": "reviewed-source",
        "contains_historical_root_runtime": False,
        "contains_experimental_recovery": False,
        "contains_modos_pdk": False,
        "contains_runtime_state": False,
        "contains_event_records": False,
        "contains_credentials": False,
        "contains_signing_keys": False,
        "contains_stage3_or_rootfs": False,
        "contains_container_or_vm_image": False,
        "installs_or_enables_services_during_build": False,
        "deployment_receipt": False,
    }
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    sums = []
    for path in sorted((archive_path, receipt_path, spdx_path), key=lambda item: item.name):
        sums.append(f"{sha256(path.read_bytes())}  {path.name}")
    (output / "SHA256SUMS.txt").write_text("\n".join(sums) + "\n", encoding="utf-8")

    print(f"PACKAGE {archive_path}")
    print(f"SBOM {spdx_path}")
    print(f"RECEIPT {receipt_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
