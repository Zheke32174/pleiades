#!/usr/bin/env python3
import hashlib
import json

API = "modos.pleiades/v1alpha1"


def sha(character):
    return "sha256:" + character * 64


REGISTRY = {
    "apiVersion": API,
    "kind": "ConstitutionalGovernanceRegistry",
    "registryId": "constitution-governance:v1",
    "principals": [
        {
            "principalRef": "human:steward-a",
            "principalType": "human",
            "roles": ["constitutional-steward"],
            "status": "active",
            "conflictDomains": [],
            "successorRef": "human:steward-b",
        },
        {
            "principalRef": "human:steward-b",
            "principalType": "human",
            "roles": ["constitutional-steward"],
            "status": "active",
            "conflictDomains": [],
        },
        {
            "principalRef": "mind:pleiades",
            "principalType": "mind",
            "roles": ["machine-executive"],
            "status": "active",
            "conflictDomains": [],
        },
        {
            "principalRef": "institution:audit",
            "principalType": "auditor",
            "roles": ["independent-auditor"],
            "status": "active",
            "conflictDomains": [],
        },
        {
            "principalRef": "institution:appeal",
            "principalType": "appeal",
            "roles": ["appeal-authority"],
            "status": "active",
            "conflictDomains": [],
        },
    ],
    "quorumPolicies": {
        "authority-model": {
            "requiredHumanApprovals": 2,
            "requiredMachineApprovals": 1,
            "requiredIndependentAudits": 1,
            "maximumRejects": 0,
            "minimumTimelockHours": 48,
            "appealWindowHours": 24,
        },
        "ordinary": {
            "requiredHumanApprovals": 1,
            "requiredMachineApprovals": 1,
            "requiredIndependentAudits": 1,
            "maximumRejects": 0,
            "minimumTimelockHours": 24,
            "appealWindowHours": 24,
        },
    },
    "authority": {
        "registryMayActivateAmendment": False,
        "registryMaySelfModify": False,
        "closureOnly": True,
    },
}

PROPOSAL = {
    "apiVersion": API,
    "kind": "ConstitutionalAmendmentProposal",
    "proposalId": "amendment:authority-model:0001",
    "amendmentClass": "authority-model",
    "currentConstitutionDigest": sha("a"),
    "candidateConstitutionDigest": sha("b"),
    "rollbackDigest": sha("a"),
    "rationaleDigest": sha("c"),
    "evidenceRefs": ["evidence:authority-review"],
    "proposedAt": "2026-07-21T00:00:00Z",
    "cancellationDeadline": "2026-07-22T00:00:00Z",
    "activationNotBefore": "2026-07-23T00:00:00Z",
    "supersedesRef": "constitution:v1",
    "authority": {"ceiling": "proposal", "activationApplied": False, "selfApprovalAllowed": False},
}


def digest(value):
    return "sha256:" + hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


DELIBERATION = {
    "apiVersion": API,
    "kind": "ConstitutionalDeliberation",
    "proposalId": PROPOSAL["proposalId"],
    "proposalDigest": digest(PROPOSAL),
    "contributions": [
        {"contributionId": "c:human-a", "principalRef": "human:steward-a", "position": "approve", "firstPassIndependent": True, "conflictDeclared": False, "recused": False, "evidenceDigest": sha("1")},
        {"contributionId": "c:human-b", "principalRef": "human:steward-b", "position": "approve", "firstPassIndependent": True, "conflictDeclared": False, "recused": False, "evidenceDigest": sha("2")},
        {"contributionId": "c:mind", "principalRef": "mind:pleiades", "position": "approve", "firstPassIndependent": True, "conflictDeclared": False, "recused": False, "evidenceDigest": sha("3")},
        {"contributionId": "c:audit", "principalRef": "institution:audit", "position": "audit", "firstPassIndependent": True, "conflictDeclared": False, "recused": False, "evidenceDigest": sha("4")},
        {"contributionId": "c:appeal", "principalRef": "institution:appeal", "position": "appeal", "firstPassIndependent": True, "conflictDeclared": False, "recused": False, "evidenceDigest": sha("5")},
    ],
    "cancellationRequests": [],
}

EVALUATED_AT = "2026-07-23T00:00:01Z"
EXPECTED = "sha256:0a63ac7e352d4d2cf0b3b830e124c4f1ddff9248481e915090bb28a2a1cb4fb6"
