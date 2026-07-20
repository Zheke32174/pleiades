#!/usr/bin/env python3
"""Validate and inventory every MODOS JSON Schema contract."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator


class CatalogError(ValueError):
    pass


def _no_duplicate_keys(pairs: Iterable[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CatalogError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle, object_pairs_hook=_no_duplicate_keys)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_bytes(value)).hexdigest()


def walk_refs(value: Any) -> list[str]:
    refs: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "$ref" and isinstance(child, str):
                refs.append(child)
            else:
                refs.extend(walk_refs(child))
    elif isinstance(value, list):
        for child in value:
            refs.extend(walk_refs(child))
    return refs


def validate_catalog(root: Path) -> dict[str, Any]:
    contract_dir = root / "modos" / "contracts"
    paths = sorted(contract_dir.glob("*.schema.json"))
    if not paths:
        raise CatalogError("no contract schemas found")

    entries: list[dict[str, Any]] = []
    ids: dict[str, str] = {}
    documents: dict[str, Any] = {}
    errors: list[str] = []

    for path in paths:
        relative = path.relative_to(root).as_posix()
        try:
            schema = load(path)
            if not isinstance(schema, dict):
                raise CatalogError("schema root must be an object")
            Draft202012Validator.check_schema(schema)
            schema_id = schema.get("$id")
            dialect = schema.get("$schema")
            if not isinstance(schema_id, str) or not schema_id:
                raise CatalogError("schema requires a nonempty $id")
            if dialect != "https://json-schema.org/draft/2020-12/schema":
                raise CatalogError("schema must use Draft 2020-12")
            if schema_id in ids:
                raise CatalogError(f"duplicate $id also used by {ids[schema_id]}")
            ids[schema_id] = relative
            documents[relative] = schema
            entries.append(
                {
                    "path": relative,
                    "schemaId": schema_id,
                    "title": schema.get("title", path.stem),
                    "digest": digest(schema),
                    "definitionCount": len(schema.get("$defs", {})) if isinstance(schema.get("$defs", {}), dict) else 0,
                    "referenceCount": len(walk_refs(schema)),
                }
            )
        except Exception as exc:  # catalog must report all malformed contracts
            errors.append(f"{relative}: {exc}")

    known_ids = set(ids)
    for relative, schema in documents.items():
        for ref in walk_refs(schema):
            if ref.startswith("#"):
                continue
            base = ref.split("#", 1)[0]
            if base.startswith("https://pleiades.local/") and base not in known_ids:
                errors.append(f"{relative}: unresolved local schema reference {ref}")

    catalog = {
        "apiVersion": "modos.pleiades/v1alpha1",
        "kind": "ContractCatalogReceipt",
        "status": "valid" if not errors else "invalid",
        "contractCount": len(entries),
        "contracts": sorted(entries, key=lambda row: row["path"]),
        "errors": sorted(errors),
        "authority": {"ceiling": "none", "canonicalMutationApplied": False},
    }
    catalog["catalogDigest"] = digest(catalog)
    return catalog


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    try:
        receipt = validate_catalog(args.root)
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if receipt["errors"]:
            for error in receipt["errors"]:
                print(f"error: {error}", file=sys.stderr)
            return 1
        print(f"contract catalog valid: {receipt['contractCount']} schemas; {receipt['catalogDigest']}")
        return 0
    except (OSError, json.JSONDecodeError, CatalogError) as exc:
        print(f"contract catalog validation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
