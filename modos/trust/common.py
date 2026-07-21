#!/usr/bin/env python3
"""Strict deterministic primitives for operational trust and preflight."""
from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


class TrustError(ValueError):
    pass


def _reject_float(value: str) -> None:
    raise TrustError(f"floating-point values are forbidden: {value}")


def _reject_constant(value: str) -> None:
    raise TrustError(f"non-finite JSON constant is forbidden: {value}")


def _no_duplicate_keys(pairs: Iterable[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise TrustError(f"duplicate JSON key is forbidden: {key}")
        result[key] = value
    return result


def load(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle, parse_float=_reject_float, parse_constant=_reject_constant, object_pairs_hook=_no_duplicate_keys)


def _assert_no_floats(value: Any, location: str = "$") -> None:
    if isinstance(value, float):
        raise TrustError(f"floating-point values are forbidden at {location}")
    if isinstance(value, dict):
        for key, child in value.items():
            _assert_no_floats(child, f"{location}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_no_floats(child, f"{location}[{index}]")


def canonical_bytes(value: Any) -> bytes:
    _assert_no_floats(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_bytes(value)).hexdigest()


def parse_time(value: str, field: str) -> datetime:
    if not isinstance(value, str):
        raise TrustError(f"{field} must be RFC3339")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise TrustError(f"{field} must be RFC3339") from exc
    if parsed.tzinfo is None:
        raise TrustError(f"{field} must include timezone")
    return parsed


def decode_base64(value: str, field: str, expected_bytes: int) -> bytes:
    if not isinstance(value, str):
        raise TrustError(f"{field} must be base64")
    try:
        decoded = base64.b64decode(value, validate=True)
    except (ValueError, base64.binascii.Error) as exc:
        raise TrustError(f"{field} must be canonical base64") from exc
    if len(decoded) != expected_bytes:
        raise TrustError(f"{field} must decode to {expected_bytes} bytes")
    if base64.b64encode(decoded).decode("ascii") != value:
        raise TrustError(f"{field} must use canonical base64 encoding")
    return decoded


def verify_self_digest(value: dict[str, Any], field: str, label: str) -> str:
    claimed = value.get(field)
    if not isinstance(claimed, str):
        raise TrustError(f"{label} is missing {field}")
    unsigned = dict(value)
    unsigned.pop(field, None)
    if digest(unsigned) != claimed:
        raise TrustError(f"{label} {field} does not reproduce")
    return claimed
