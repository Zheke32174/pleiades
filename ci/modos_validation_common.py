"""Shared helpers for MODOS contract validators."""
from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def contains_float(value: Any) -> bool:
    if isinstance(value, float):
        return True
    if isinstance(value, dict):
        return any(contains_float(item) for item in value.values())
    if isinstance(value, list):
        return any(contains_float(item) for item in value)
    return False


def sha256_id(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def ingress_batch_digest(instance: dict[str, Any]) -> str:
    material = copy.deepcopy(instance)
    material["integrity"]["batchDigest"] = ""
    if "signature" in material["proof"]:
        material["proof"]["signature"] = ""
    return sha256_id(canonical_json_bytes(material))
