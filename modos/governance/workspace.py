#!/usr/bin/env python3
"""Deterministic recurrent executive-workspace arbitration.

The workspace binds differentiated cognitive contributions into one persistent
Mind decision while preserving dissent. It does not execute the decision.
"""
from __future__ import annotations
import argparse, hashlib, json, sys
from pathlib import Path
from typing import Any, Iterable

API_VERSION="modos.pleiades/v1alpha1"

class WorkspaceError(ValueError): pass

def _reject_float(v): raise WorkspaceError(f"floating-point values are forbidden: {v}")
def _reject_constant(v): raise WorkspaceError(f"non-finite JSON constant is forbidden: {v}")
def _pairs(items: Iterable[tuple[str,Any]]):
    out={}
    for k,v in items:
        if k in out: raise WorkspaceError(f"duplicate JSON key is forbidden: {k}")
        out[k]=v
    return out
def load_json_strict(path: Path):
    return json.loads(path.read_text(),parse_float=_reject_float,parse_constant=_reject_constant,object_pairs_hook=_pairs)
def canonical_bytes(v): return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False).encode()
def digest(v): return "sha256:"+hashlib.sha256(canonical_bytes(v)).hexdigest()

def close_cycle(cycle: dict[str,Any]) -> dict[str,Any]:
    if cycle.get("apiVersion")!=API_VERSION or cycle.get("kind")!="ExecutiveWorkspaceCycle":
        raise WorkspaceError("unsupported workspace cycle envelope")
    if not isinstance(cycle.get("mindId"),str) or not cycle["mindId"]:
        raise WorkspaceError("workspace cycle mindId is required")
    if not isinstance(cycle.get("rounds"),int) or cycle["rounds"]<2:
        raise WorkspaceError("executive arbitration requires at least two recurrent rounds")
    for field in ("proposalDigest","policyReceiptDigest","atlasBeliefDigest","forgeStateDigest"):
        value=cycle.get(field)
        if not isinstance(value,str) or not value.startswith("sha256:") or len(value)!=71:
            raise WorkspaceError(f"{field} must be sha256-bound")
    contributions=cycle.get("contributions")
    if not isinstance(contributions,list) or len(contributions)<4:
        raise WorkspaceError("workspace cycle requires at least four contributions")
    ids=set(); principals=set(); roles=set(); scores={"approve":0,"reject":0,"defer":0,"request-more-evidence":0}
    normalized=[]; dissent_ids=[]
    for item in contributions:
        cid=item.get("contributionId"); principal=item.get("principalRef"); role=item.get("role")
        if not isinstance(cid,str) or not cid or cid in ids: raise WorkspaceError("contribution ids must be unique")
        ids.add(cid)
        if not isinstance(principal,str) or not principal: raise WorkspaceError(f"{cid} principalRef is required")
        principals.add(principal)
        if role not in {"proposal","risk","policy","dissent"}: raise WorkspaceError(f"{cid} role is unsupported")
        roles.add(role)
        if item.get("firstPassIndependent") is not True: raise WorkspaceError(f"{cid} must preserve independent first pass")
        refs=item.get("evidenceRefs")
        if not isinstance(refs,list) or not refs or len(set(refs))!=len(refs): raise WorkspaceError(f"{cid} evidenceRefs must be nonempty and unique")
        confidence=item.get("confidenceBps"); competence=item.get("competenceWeightBps")
        if not isinstance(confidence,int) or isinstance(confidence,bool) or not 0<=confidence<=10000:
            raise WorkspaceError(f"{cid} confidenceBps is invalid")
        if not isinstance(competence,int) or isinstance(competence,bool) or not 0<=competence<=10000:
            raise WorkspaceError(f"{cid} competenceWeightBps is invalid")
        recommendation=item.get("recommendation")
        if recommendation not in scores: raise WorkspaceError(f"{cid} recommendation is unsupported")
        effective=min(competence,4000)
        if role=="dissent": effective=max(effective,500); dissent_ids.append(cid)
        weighted=(effective*confidence)//10000
        scores[recommendation]+=weighted
        normalized.append({"contributionId":cid,"principalRef":principal,"role":role,"recommendation":recommendation,"effectiveWeightBps":effective,"weightedScore":weighted,"contentDigest":item.get("contentDigest")})
    if len(principals)<3: raise WorkspaceError("workspace cycle requires at least three distinct principals")
    if not {"proposal","risk","policy","dissent"}.issubset(roles):
        raise WorkspaceError("workspace cycle requires proposal, risk, policy, and dissent roles")
    ordered=sorted(scores.items(),key=lambda kv:(-kv[1],kv[0]))
    top_score=ordered[0][1]
    winners=[name for name,score in ordered if score==top_score]
    outcome="defer" if len(winners)>1 else winners[0]
    if top_score==0: outcome="request-more-evidence"
    unresolved=sorted(set(cycle.get("unresolvedDissentRefs",[])) | {cid for cid in dissent_ids if next(x for x in normalized if x["contributionId"]==cid)["recommendation"]!=outcome})
    return {
      "apiVersion":API_VERSION,"kind":"WorkspaceDeliberationReceipt","cycleId":cycle["cycleId"],"mindId":cycle["mindId"],
      "bindings":{"proposalDigest":cycle["proposalDigest"],"policyReceiptDigest":cycle["policyReceiptDigest"],"atlasBeliefDigest":cycle["atlasBeliefDigest"],"forgeStateDigest":cycle["forgeStateDigest"],"cycleDigest":digest(cycle)},
      "outcome":outcome,"scores":scores,"contributions":sorted(normalized,key=lambda x:x["contributionId"]),"unresolvedDissentRefs":unresolved,
      "checks":[{"name":"polycentric-principals","status":"pass"},{"name":"independent-first-pass","status":"pass"},{"name":"required-roles-present","status":"pass"},{"name":"competence-weight-capped","status":"pass"},{"name":"dissent-preserved","status":"pass"},{"name":"atlas-bound","status":"pass"},{"name":"forge-bound","status":"pass"},{"name":"recurrent-rounds","status":"pass"}],
      "authority":{"decisionPrincipal":"persistent-mind","executorAuthority":"none","canonicalMutationApplied":False}
    }

def main():
    p=argparse.ArgumentParser();p.add_argument("--cycle",type=Path,required=True);p.add_argument("--out-receipt",type=Path,required=True);a=p.parse_args()
    try:
        r=close_cycle(load_json_strict(a.cycle));a.out_receipt.parent.mkdir(parents=True,exist_ok=True);a.out_receipt.write_text(json.dumps(r,indent=2,sort_keys=True)+"\n");print(r["outcome"]);return 0
    except (OSError,json.JSONDecodeError,WorkspaceError) as e:
        print(f"workspace closure failed: {e}",file=sys.stderr);return 1
if __name__=="__main__": raise SystemExit(main())
