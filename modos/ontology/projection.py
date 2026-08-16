#!/usr/bin/env python3
"""Build a deterministic, non-authoritative read projection from a closed snapshot."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from compiler import (  # noqa: E402
    API_VERSION,
    OntologyCompileError,
    canonical_bytes,
    digest,
    load_json_strict,
    normalize_snapshot,
    snapshot_digest,
)

PROJECTION_VERSION = "v1alpha1"


class ProjectionError(OntologyCompileError):
    """Raised when a projection would not remain bound and non-authoritative."""


def _require_closed_receipt(receipt: dict[str, Any], expected_snapshot_digest: str) -> None:
    if receipt.get("apiVersion") != API_VERSION or receipt.get("kind") != "OntologyClosureReceipt":
        raise ProjectionError("unsupported closure receipt envelope")
    if receipt.get("closureStatus") != "closed":
        raise ProjectionError("projection requires a closed ontology receipt")
    if receipt.get("resultSnapshotDigest") != expected_snapshot_digest:
        raise ProjectionError("closure receipt does not bind the exact projected snapshot")
    authority = receipt.get("authority")
    if authority != {
        "ceiling": "none",
        "canonicalMutationApplied": False,
        "promotionTransactionRequired": True,
        "promotionState": "eligible-for-review",
    }:
        raise ProjectionError("closure receipt authority boundary is not exact")


def build_projection_bundle(
    snapshot: dict[str, Any], receipt: dict[str, Any]
) -> dict[str, Any]:
    normalized = normalize_snapshot(snapshot)
    exact_snapshot_digest = snapshot_digest(normalized)
    _require_closed_receipt(receipt, exact_snapshot_digest)
    receipt_digest = digest(receipt)
    object_rows = []
    for obj in normalized["objects"]:
        metadata = obj["metadata"]
        object_rows.append(
            {
                "snapshotDigest": exact_snapshot_digest,
                "objectId": metadata["id"],
                "kind": obj["kind"],
                "generation": metadata["generation"],
                "payload": obj,
            }
        )
    relation_rows = []
    for relation in normalized["relations"]:
        relation_rows.append(
            {
                "snapshotDigest": exact_snapshot_digest,
                "sourceRef": relation["sourceRef"],
                "type": relation["type"],
                "targetRef": relation["targetRef"],
                "attributes": relation.get("attributes", {}),
            }
        )
    bundle = {
        "apiVersion": API_VERSION,
        "kind": "OntologyProjectionBundle",
        "projectionVersion": PROJECTION_VERSION,
        "source": {
            "snapshotDigest": exact_snapshot_digest,
            "closureReceiptDigest": receipt_digest,
            "mindId": normalized["mindId"],
            "schemaVersion": normalized["schemaVersion"],
        },
        "authority": {
            "ceiling": "none",
            "canonical": False,
            "writeBackAllowed": False,
        },
        "snapshotRow": {
            "snapshotDigest": exact_snapshot_digest,
            "mindId": normalized["mindId"],
            "schemaVersion": normalized["schemaVersion"],
            "sourceSnapshotDigest": receipt["sourceSnapshotDigest"],
            "closureReceiptDigest": receipt_digest,
            "payload": normalized,
        },
        "objectRows": object_rows,
        "relationRows": relation_rows,
    }
    return bundle


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        bundle = build_projection_bundle(
            load_json_strict(args.snapshot), load_json_strict(args.receipt)
        )
        _write_json(args.out, bundle)
        print(digest(bundle))
        return 0
    except (OSError, json.JSONDecodeError, ProjectionError, OntologyCompileError) as exc:
        print(f"ontology projection failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
