#!/usr/bin/env python3
"""Deterministic emergency-containment and recovery authority verifier.

The verifier authorizes only short-lived containment or recovery actions already
covered by an emergency grant. It does not perform the action.
"""
from __future__ import annotations
import argparse, hashlib, json, sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

API_VERSION="modos.pleiades/v1alpha1"
ALLOWED={"contain","isolate","rollback","preserve-evidence"}

class EmergencyError(ValueError): pass
def _reject_float(v): raise EmergencyError(f"floating-point values are forbidden: {v}")
def _reject_constant(v): raise EmergencyError(f"non-finite JSON constant is forbidden: {v}")
def _pairs(items: Iterable[tuple[str,Any]]):
    out={}
    for k,v in items:
        if k in out: raise EmergencyError(f"duplicate JSON key is forbidden: {k}")
        out[k]=v
    return out
def load_json_strict(path: Path):
    return json.loads(path.read_text(),parse_float=_reject_float,parse_constant=_reject_constant,object_pairs_hook=_pairs)
def canonical_bytes(v): return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False).encode()
def digest(v): return "sha256:"+hashlib.sha256(canonical_bytes(v)).hexdigest()
def _time(v,field):
    if not isinstance(v,str): raise EmergencyError(f"{field} must be RFC3339")
    try:return datetime.fromisoformat(v.replace("Z","+00:00"))
    except ValueError as e: raise EmergencyError(f"{field} must be RFC3339") from e

def evaluate_emergency(grant:dict[str,Any],request:dict[str,Any],registry_receipt:dict[str,Any],continuity:dict[str,Any])->dict[str,Any]:
    if grant.get("apiVersion")!=API_VERSION or grant.get("kind")!="EmergencyAuthorityGrant": raise EmergencyError("unsupported emergency grant")
    if request.get("apiVersion")!=API_VERSION or request.get("kind")!="EmergencyActionRequest": raise EmergencyError("unsupported emergency request")
    if registry_receipt.get("kind")!="AuthorityRegistryReceipt": raise EmergencyError("authority registry receipt is required")
    if continuity.get("apiVersion")!=API_VERSION or continuity.get("kind")!="ContinuityState": raise EmergencyError("continuity state is required")
    issued=_time(grant.get("issuedAt"),"grant issuedAt");expires=_time(grant.get("expiresAt"),"grant expiresAt");requested=_time(request.get("requestedAt"),"request requestedAt")
    if expires-issued>timedelta(hours=1) or issued>=expires: raise EmergencyError("emergency grant must be positive and no longer than one hour")
    if not issued<=requested<expires: raise EmergencyError("emergency request is outside grant validity")
    allowed=grant.get("allowedActions")
    if not isinstance(allowed,list) or not allowed or not set(allowed).issubset(ALLOWED) or "*" in allowed: raise EmergencyError("emergency grant actions must be bounded containment powers")
    action=request.get("action")
    if action not in allowed: raise EmergencyError("emergency action is outside grant")
    if grant.get("constraints")!={"constitutionalMutationAllowed":False,"authorityExpansionAllowed":False,"postEventReviewRequired":True,"evidencePreservationRequired":True}:
        raise EmergencyError("emergency grant constraints are not exact")
    ref=f"{grant['grantId']}@{grant['generation']}"
    if ref not in registry_receipt.get("activeGrantRefs",[]): raise EmergencyError("emergency grant is not active")
    if ref in continuity.get("revokedGrantRefs",[]): raise EmergencyError("revoked grant cannot be rehydrated")
    if request.get("principalRef")!=grant.get("subject",{}).get("principalRef"): raise EmergencyError("emergency request principal mismatch")
    total_components=continuity.get("totalMindComponents");available_components=continuity.get("availableMindComponents")
    total_nodes=continuity.get("totalNodes");available_nodes=continuity.get("availableNodes")
    if any(not isinstance(x,int) or x<0 for x in (total_components,available_components,total_nodes,available_nodes)):
        raise EmergencyError("continuity counts are invalid")
    if available_components>total_components or available_nodes>total_nodes: raise EmergencyError("continuity available counts exceed totals")
    degraded=available_components*2<total_components or available_nodes*2<total_nodes
    quorum=continuity.get("recoveryQuorumRefs")
    if degraded and (not isinstance(quorum,list) or len(set(quorum))<2): raise EmergencyError("degraded recovery requires at least two quorum principals")
    safe_mode=degraded or request.get("safeModeRequired") is True
    restored=[g for g in registry_receipt.get("activeGrantRefs",[]) if g not in set(continuity.get("revokedGrantRefs",[]))]
    return {
      "apiVersion":API_VERSION,"kind":"EmergencyRecoveryReceipt","requestId":request["requestId"],"grantRef":ref,
      "status":"safe-mode-authorized" if safe_mode else "containment-authorized","action":action,"expiresAt":grant["expiresAt"],
      "continuity":{"safeMode":safe_mode,"availableMindComponents":available_components,"totalMindComponents":total_components,"availableNodes":available_nodes,"totalNodes":total_nodes,"recoveryQuorumRefs":sorted(quorum),"rehydratableGrantRefs":sorted(restored)},
      "checks":[{"name":"short-lived-grant","status":"pass"},{"name":"containment-only","status":"pass"},{"name":"constitution-protected","status":"pass"},{"name":"authority-expansion-forbidden","status":"pass"},{"name":"post-event-review-required","status":"pass"},{"name":"active-grant-bound","status":"pass"},{"name":"revoked-grants-not-restored","status":"pass"},{"name":"recovery-quorum-bound","status":"pass"}],
      "obligations":{"postEventReviewRequired":True,"evidencePreservationRequired":True,"automaticExpiry":True},
      "authority":{"ceiling":"emergency-containment","canonicalMutationApplied":False,"grantMutationApplied":False,"executionStillPending":True}
    }

def main():
    p=argparse.ArgumentParser();p.add_argument("--grant",type=Path,required=True);p.add_argument("--request",type=Path,required=True);p.add_argument("--registry",type=Path,required=True);p.add_argument("--continuity",type=Path,required=True);p.add_argument("--out-receipt",type=Path,required=True);a=p.parse_args()
    try:
        r=evaluate_emergency(*(load_json_strict(x) for x in (a.grant,a.request,a.registry,a.continuity)));a.out_receipt.parent.mkdir(parents=True,exist_ok=True);a.out_receipt.write_text(json.dumps(r,indent=2,sort_keys=True)+"\n");print(r["status"]);return 0
    except (OSError,json.JSONDecodeError,EmergencyError) as e:
        print(f"emergency recovery validation failed: {e}",file=sys.stderr);return 1
if __name__=="__main__": raise SystemExit(main())
