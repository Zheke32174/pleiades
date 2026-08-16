#!/usr/bin/env python3
"""Fixtures for recurrent executive workspace and emergency recovery authority."""
from __future__ import annotations

API="modos.pleiades/v1alpha1"
def sha(ch): return "sha256:"+ch*64

CYCLE={
 "apiVersion":API,"kind":"ExecutiveWorkspaceCycle","cycleId":"cycle:ontology:0001","mindId":"mind:pleiades",
 "proposalRef":"fixture:eligible-ontology-candidate","proposalDigest":sha("b"),"policyReceiptDigest":sha("c"),"atlasBeliefDigest":sha("d"),"forgeStateDigest":sha("e"),"rounds":3,
 "unresolvedDissentRefs":["dissent:prior:0001"],
 "contributions":[
  {"contributionId":"contrib:proposal","principalRef":"model:planner","role":"proposal","firstPassIndependent":True,"evidenceRefs":["evidence:proposal"],"contentDigest":sha("1"),"confidenceBps":9000,"competenceWeightBps":3500,"recommendation":"approve"},
  {"contributionId":"contrib:risk","principalRef":"model:risk","role":"risk","firstPassIndependent":True,"evidenceRefs":["evidence:risk"],"contentDigest":sha("2"),"confidenceBps":8000,"competenceWeightBps":3000,"recommendation":"approve"},
  {"contributionId":"contrib:policy","principalRef":"service:policy","role":"policy","firstPassIndependent":True,"evidenceRefs":["evidence:policy"],"contentDigest":sha("3"),"confidenceBps":10000,"competenceWeightBps":2500,"recommendation":"approve"},
  {"contributionId":"contrib:dissent","principalRef":"model:dissent","role":"dissent","firstPassIndependent":True,"evidenceRefs":["evidence:dissent"],"contentDigest":sha("4"),"confidenceBps":7000,"competenceWeightBps":1000,"recommendation":"defer"}
 ]
}
EMERGENCY_GRANT={"apiVersion":API,"kind":"EmergencyAuthorityGrant","grantId":"emergency-grant:pleiades:0001","generation":1,"subject":{"principalRef":"mind:pleiades","principalType":"mind"},"allowedActions":["contain","isolate","rollback","preserve-evidence"],"domains":["runtime","network"],"issuedAt":"2026-07-20T22:00:00Z","expiresAt":"2026-07-20T22:45:00Z","constraints":{"constitutionalMutationAllowed":False,"authorityExpansionAllowed":False,"postEventReviewRequired":True,"evidencePreservationRequired":True},"provenanceDigest":sha("5")}
EMERGENCY_REQUEST={"apiVersion":API,"kind":"EmergencyActionRequest","requestId":"emergency-request:0001","principalRef":"mind:pleiades","action":"isolate","targetRef":"node:compromised","requestedAt":"2026-07-20T22:15:00Z","observedThreatDigest":sha("6"),"rationaleDigest":sha("7"),"safeModeRequired":False}
REGISTRY_RECEIPT={"apiVersion":API,"kind":"AuthorityRegistryReceipt","registryId":"authority-registry:pleiades-v1","registryDigest":sha("8"),"evaluationAt":"2026-07-20T22:10:00Z","activeGrantRefs":["emergency-grant:pleiades:0001@1","grant:mind-pleiades:ontology-bounded-v1@1"],"inactiveGrants":[{"grantRef":"grant:revoked@1","reason":"revoked"}],"checks":[{"name":"closed","status":"pass"}],"authority":{"ceiling":"none","grantMutationApplied":False}}
CONTINUITY={"apiVersion":API,"kind":"ContinuityState","availableMindComponents":4,"totalMindComponents":5,"availableNodes":2,"totalNodes":3,"recoveryQuorumRefs":["principal:recovery-a","principal:recovery-b"],"revokedGrantRefs":["grant:revoked@1"],"observedAt":"2026-07-20T22:12:00Z"}
EXPECTED_DIGESTS={"workspaceReceipt":"sha256:14dddaded0bb280e43512c02d2b9f0e7ad083c759a1d6fc39160f9f756ddf86b","emergencyReceipt":"sha256:cd90131c6ae03a9a815f5691c3db892ee54f18f238b5d2dd850f835e7c637de6"}
