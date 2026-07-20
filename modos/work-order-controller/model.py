"""Shared types and invariants for the durable work-order reference controller."""
from __future__ import annotations
import hashlib, json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

RISK_ORDER={"observe":0,"operate":1,"reversible":2,"confirmed":3,"external-sovereign":4}
TERMINAL={"rejected","succeeded","failed","rolled-back","canceled","expired","recovery-failed"}
TRANSITIONS={
 "draft":{"validating","rejected","canceled"},
 "validating":{"admitted","rejected","canceled"},
 "admitted":{"queued","preparing","canceled"},
 "queued":{"preparing","canceling","canceled"},
 "preparing":{"running","blocked","quarantined","canceling","failed"},
 "running":{"paused","awaiting-approval","blocked","quarantined","canceling","verifying","failed"},
 "paused":{"running","canceling","canceled"},
 "awaiting-approval":{"running","canceling","failed"},
 "blocked":{"running","canceling","failed"},
 "quarantined":{"canceling","failed"},
 "canceling":{"canceled","rolling-back","recovery-failed"},
 "verifying":{"running","succeeded","rolling-back","failed"},
 "rolling-back":{"rolled-back","recovery-failed"},
}
class ControllerError(RuntimeError):pass
class InvalidRequest(ControllerError):pass
class IdempotencyConflict(ControllerError):pass
class InvalidTransition(ControllerError):pass
class NotFound(ControllerError):pass

def utc_now():return datetime.now(timezone.utc).isoformat().replace("+00:00","Z")
def canonical_bytes(value:Any)->bytes:
 return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode()
def digest(value:Any)->str:return "sha256:"+hashlib.sha256(canonical_bytes(value)).hexdigest()
@dataclass(frozen=True)
class Capability:
 capability_id:str; version:str; operations:tuple[str,...]; maximum_risk:str
 canonical_write:bool=False; arbitrary_shell:bool=False; external_irreversible_effect:bool=False
