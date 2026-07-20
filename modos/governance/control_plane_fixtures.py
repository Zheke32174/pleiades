#!/usr/bin/env python3
"""Deterministic fixtures and pinned golden digests for the executive control plane."""
from __future__ import annotations
import hashlib, json

API="modos.pleiades/v1alpha1"
def digest(value):
    return "sha256:"+hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()
def sha(ch): return "sha256:"+ch*64

POLICY={
 "apiVersion":API,"kind":"ExecutivePolicy","policyId":"policy:executive-core-v1","version":"v1alpha1",
 "rules":[
  {"ruleId":"observe","priority":10,"match":{"domains":["ontology","runtime","memory"],"actions":["observe"],"reversibility":["reversible"],"persistence":["ephemeral"],"impacts":["low"]},"decision":{"riskTier":"observe-only","authorizationMode":"delegated-machine-executive","requiredHumanApprovals":0,"machineExecutiveDecisionRequired":True,"delegatedAuthorityGrantRequired":True,"executorCapability":"governance.observe","rollbackRequired":False}},
  {"ruleId":"ontology-bounded","priority":20,"match":{"domains":["ontology"],"actions":["authorize-admission","authorize-rollback"],"reversibility":["reversible"],"persistence":["local-persistent"],"impacts":["low","moderate"]},"decision":{"riskTier":"bounded-persistent","authorizationMode":"delegated-machine-executive","requiredHumanApprovals":0,"machineExecutiveDecisionRequired":True,"delegatedAuthorityGrantRequired":True,"executorCapability":"ontology.snapshot.admit","rollbackRequired":True}},
  {"ruleId":"runtime-high-impact","priority":30,"match":{"domains":["runtime"],"actions":["rollout"],"reversibility":["reversible"],"persistence":["distributed-persistent"],"impacts":["high"]},"decision":{"riskTier":"high-impact","authorizationMode":"mixed-quorum","requiredHumanApprovals":1,"machineExecutiveDecisionRequired":True,"delegatedAuthorityGrantRequired":True,"executorCapability":"runtime.rollout.stage","rollbackRequired":True}}
 ],
 "reservedPowers":{"constitutionalActions":["amend-constitution"],"authorityActions":["expand-own-authority","issue-grant"],"requiredHumanApprovals":2},
 "authority":{"machineMayModifyPolicy":False,"machineMayExpandOwnAuthority":False,"policyDecisionOnly":True}
}
REQUEST={"apiVersion":API,"kind":"ChangeClassificationRequest","requestId":"classify:ontology-admission-0001","mindId":"mind:pleiades","domain":"ontology","action":"authorize-admission","reversibility":"reversible","persistence":"local-persistent","impact":"moderate","evidenceDigest":sha("b"),"requestedAt":"2026-07-20T21:10:00Z"}

GRANT={"apiVersion":API,"authoritySourceRef":"modos/EXECUTIVE_AUTHORITY.md#risk-ladder","autonomyMode":"execute-within-grant","constraints":{"authorityExpansionAllowed":False,"constitutionalMutationAllowed":False,"externalSideEffectsAllowed":False,"maxActionsPerDecision":8,"maxExecutionSeconds":900,"maxObjectsChanged":64,"reversibilityRequired":True,"rollbackRequired":True},"delegation":{"mayDelegate":False,"maySelfExpand":False,"revocable":True},"domains":["ontology"],"grantId":"grant:mind-pleiades:ontology-bounded-v1","issuerRef":"sovereign:pleiades-constitutional-process","kind":"DelegatedAuthorityGrant","permissions":["approve-candidate","reject-candidate","defer-candidate","authorize-admission","authorize-rollback","suspend-executor","revoke-mandate"],"provenance":{"digest":sha("a"),"evidenceRefs":["modos/EXECUTIVE_AUTHORITY.md","github:Zheke32174/pleiades#54"],"issuedAt":"2026-07-20T20:30:00Z"},"riskCeiling":"bounded-persistent","status":"active","subject":{"principalRef":"mind:pleiades","principalType":"mind"},"validity":{"notAfter":"2027-07-20T00:00:00Z","notBefore":"2026-07-20T00:00:00Z"},"generation":1}
REGISTRY={"apiVersion":API,"kind":"AuthorityRegistry","registryId":"authority-registry:pleiades-v1","evaluationAt":"2026-07-20T22:00:00Z","grants":[GRANT],"events":[{"apiVersion":API,"kind":"AuthorityLifecycleEvent","eventId":"authority-event:issue-0001","grantRef":GRANT["grantId"],"grantGeneration":1,"eventType":"issued","effectiveAt":"2026-07-20T20:30:00Z","actor":{"principalRef":"sovereign:pleiades-constitutional-process","principalType":"institution","authoritySourceDigest":sha("c")},"reasonDigest":sha("d")}],"authority":{"registryMayIssueGrants":False,"registryMayAlterConstitution":False,"closureOnly":True}}

MANDATE={"apiVersion":API,"authority":{"executionOnly":True,"mayAlterPlan":False,"mayChangeTarget":False,"mayExpandAuthority":False},"candidateDigest":sha("b"),"candidateRef":"fixture:eligible-ontology-candidate","constraints":{"automaticRollbackOnFailure":True,"maxAttempts":2,"networkScope":[],"reversible":True,"timeoutSeconds":600,"writeScope":["ontology:admitted-snapshot"]},"decisionDigest":"sha256:43732c70508f764d79b91753c37c8c85c29b74dfa15ba16425f31b3f3cf088f8","decisionRef":"decision:ontology-candidate-0001","executor":{"capabilityRef":"capability:ontology.snapshot.admit@v1alpha1","decisionAuthority":"none","principalRef":"service:ontology-admission-executor"},"expiresAt":"2026-07-21T21:00:00Z","kind":"AdmissionMandate","mandateId":"mandate:ontology-candidate-0001","postconditions":["target-digest-installed","closure-receipt-retained","predecessor-remains-recoverable"],"stateTransition":{"predecessorDigest":sha("1"),"rollbackDigest":sha("1"),"targetDigest":sha("b")}}
AUTHORIZATION={"apiVersion":API,"authority":{"authorityExpansionApplied":False,"constitutionalMutationApplied":False,"decisionPrincipal":"delegated-mind","executionStillPending":True,"executorDecisionAuthority":"none"},"bindings":{"decisionDigest":MANDATE["decisionDigest"],"grantId":GRANT["grantId"],"mandateDigest":digest(MANDATE),"mindId":"mind:pleiades","predecessorDigest":sha("1"),"proposalDigest":sha("b"),"rollbackDigest":sha("1"),"targetDigest":sha("b")},"checks":[{"name":"all","status":"pass"}],"decisionId":"decision:ontology-candidate-0001","kind":"ExecutiveAuthorizationReceipt","mandateId":MANDATE["mandateId"],"status":"authorized"}
SUCCESS_ATTEMPT={"apiVersion":API,"kind":"ExecutionAttempt","attemptId":"attempt:ontology-admission-0001","mandateId":MANDATE["mandateId"],"mandateDigest":digest(MANDATE),"authorizationReceiptDigest":digest(AUTHORIZATION),"executorRef":"service:ontology-admission-executor","startedAt":"2026-07-20T22:05:00Z","completedAt":"2026-07-20T22:06:00Z","observedTargetDigest":sha("b"),"preconditions":[{"name":"predecessor-present","status":"pass","evidenceDigest":sha("2")}],"postconditions":[{"name":"target-digest-installed","status":"pass","evidenceDigest":sha("3")},{"name":"predecessor-recoverable","status":"pass","evidenceDigest":sha("4")}],"resourceUsage":{"wallSeconds":60,"toolCalls":4,"writeOperations":1},"rollback":{"attempted":False,"succeeded":False,"restoredDigest":sha("1"),"evidenceDigest":sha("5")}}
ROLLBACK_ATTEMPT=json.loads(json.dumps(SUCCESS_ATTEMPT))
ROLLBACK_ATTEMPT.update({"attemptId":"attempt:ontology-admission-0002","observedTargetDigest":sha("e")})
ROLLBACK_ATTEMPT["postconditions"][0]["status"]="fail"
ROLLBACK_ATTEMPT["rollback"]={"attempted":True,"succeeded":True,"restoredDigest":sha("1"),"evidenceDigest":sha("6")}

PROFILE={"apiVersion":API,"kind":"CompetenceProfile","profileId":"competence:mind-pleiades:ontology-admit","principalRef":"mind:pleiades","domain":"ontology","action":"authorize-admission","riskTier":"bounded-persistent","generation":1,"counts":{"succeeded":0,"failed":0,"rolledBack":0,"policyViolations":0},"competenceScoreBps":5000,"evidenceRefs":[],"authority":{"selfScored":False,"grantMutationApplied":False}}
OUTCOMES=[{"apiVersion":API,"kind":"OutcomeEvidence","outcomeId":f"outcome:ontology:{i:04d}","principalRef":"mind:pleiades","verifierRef":"service:outcome-verifier","domain":"ontology","action":"authorize-admission","riskTier":"bounded-persistent","result":"succeeded","confidenceBps":9000,"executionReceiptDigest":"sha256:"+format(i,"064x"),"evidenceDigest":"sha256:"+format(i+100,"064x"),"verifiedAt":f"2026-07-21T22:{i:02d}:00Z","verification":{"status":"verified","independent":True}} for i in range(1,11)]

EXPECTED_DIGESTS={
 "policyReceipt":"sha256:cb41524700f41f2bf8f89a0f0a82f9e4fed9a87d565717dc4c93e669fca853ce",
 "authorityRegistryReceipt":"sha256:50a562db5e22b64977941f788b323141bee164e0c2b8bdfdabad66c8bd82cef0",
 "successExecutionReceipt":"sha256:f3788ffa6eb872e57ee84cc4f5789aab2fa46941c08eea49bdfa87341911792f",
 "successRollbackReceipt":"sha256:65a00001fb6403ac3ebbaf02db09fb6439a6ad0703991964f9c24f412a1f938b",
 "rollbackExecutionReceipt":"sha256:943b203375c4ec27ba21c1423bc9b2fd81f5dcb94a51b67a82c9b005b99e25e3",
 "rollbackEvidenceReceipt":"sha256:0847fe371c3a68360bf2e2037d759a0a8b7b5179ba963422320b63dd6d750f7d",
 "competenceProfile":"sha256:dfa96debe77610bbc838c73ca3c9ba4bd519ebe51ea4a8e1b0160f013ff6a648",
 "competenceReceipt":"sha256:99e1c371a9097fb8863a83808cb3ea49de6fcab7126acbe2361ecc1d59808386"
}
