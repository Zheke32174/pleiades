#!/usr/bin/env python3
"""Synthetic fixtures for the administrative judgment gate."""
from __future__ import annotations

API = "modos.pleiades/v1alpha1"


def sha(ch: str) -> str:
    return "sha256:" + ch * 64


POLICY_RECEIPT = {
    "apiVersion": API,
    "kind": "PolicyDecisionReceipt",
    "requestId": "request:judgment:0001",
    "policyId": "policy:executive:v1",
    "policyDigest": sha("a"),
    "requestDigest": sha("b"),
    "matchedRuleId": "bounded-persistent-ontology",
    "classification": {"riskTier": "bounded-persistent", "reservedPower": False},
    "authorization": {
        "mode": "mixed-quorum",
        "requiredHumanApprovals": 1,
        "machineExecutiveDecisionRequired": True,
        "delegatedAuthorityGrantRequired": True,
        "executorCapability": "ontology.admission.apply",
        "rollbackRequired": True,
    },
    "authority": {
        "decisionAuthority": "classification-only",
        "canonicalMutationApplied": False,
        "policyMutationApplied": False,
    },
}

WORKSPACE_RECEIPT = {
    "apiVersion": API,
    "kind": "WorkspaceDeliberationReceipt",
    "cycleId": "cycle:judgment:0001",
    "mindId": "mind:pleiades",
    "bindings": {
        "proposalDigest": sha("c"),
        "policyReceiptDigest": "",
        "atlasBeliefDigest": sha("d"),
        "forgeStateDigest": sha("e"),
        "cycleDigest": sha("f"),
    },
    "outcome": "approve",
    "scores": {"approve": 6200, "reject": 0, "defer": 700, "request-more-evidence": 0},
    "contributions": [],
    "unresolvedDissentRefs": ["contrib:dissent"],
    "checks": [{"name": "polycentric-principals", "status": "pass"}],
    "authority": {
        "decisionPrincipal": "persistent-mind",
        "executorAuthority": "none",
        "canonicalMutationApplied": False,
    },
}

PREFLIGHT_RECEIPT = {
    "apiVersion": API,
    "kind": "TransitionPreflightReceipt",
    "authorizationId": "transition-authorization:judgment:0001",
    "status": "eligible-for-mandate-construction",
    "evaluatedAt": "2026-07-22T04:00:00Z",
    "bindings": {
        "authorizationCandidateDigest": sha("1"),
        "compilationReceiptDigest": sha("2"),
        "evidenceTrustReceiptDigest": sha("3"),
        "grantDigest": sha("4"),
        "operatorCandidateDigest": sha("5"),
        "planDigest": sha("6"),
        "predecessorDigest": sha("7"),
        "registryDigest": sha("8"),
        "rollbackDigest": sha("7"),
        "targetDigest": sha("9"),
    },
    "decision": {
        "action": "authorize-admission",
        "authorizationMode": "mixed-quorum",
        "decisionType": "canary-admission",
        "domain": "ontology",
        "executorCapability": "ontology.admission.apply",
        "riskTier": "bounded-persistent",
    },
    "blockers": [],
    "checks": [{"name": "trusted-evidence-bound", "status": "pass"}],
    "quorum": {
        "countedApprovers": ["human:steward", "mind:pleiades"],
        "independentAuditors": ["service:audit"],
        "recusedPrincipals": [],
        "rejects": 0,
        "roleApprovals": {"machine-executive": 1, "sovereign-steward": 1},
    },
    "authority": {
        "authorizationApplied": False,
        "ceiling": "none",
        "executionApplied": False,
        "mandateConstructed": False,
        "preflightOnly": True,
        "registryMutationApplied": False,
    },
}

CASE = {
    "apiVersion": API,
    "kind": "AdministrativeJudgmentCase",
    "judgmentId": "judgment:ontology:0001",
    "mindId": "mind:pleiades",
    "domain": "ontology",
    "action": "authorize-admission",
    "evaluatedAt": "2026-07-22T04:05:00Z",
    "bindings": {
        "policyReceiptDigest": "",
        "workspaceReceiptDigest": "",
        "transitionPreflightReceiptDigest": "",
        "proposalDigest": sha("c"),
        "atlasBeliefDigest": sha("d"),
        "forgeStateDigest": sha("e"),
        "evidenceSetDigest": sha("0"),
    },
    "validTime": {"from": "2026-07-22T04:00:00Z", "until": "2026-07-22T05:00:00Z"},
    "transactionTime": {
        "recordedAt": "2026-07-22T04:04:00Z",
        "knowledgeCutoffAt": "2026-07-22T04:03:00Z",
        "supersedesReceiptDigest": None,
    },
    "requiredAssumptionRefs": ["assumption:target-reversible", "assumption:evidence-current"],
    "assumptions": [
        {
            "assumptionId": "assumption:evidence-current",
            "status": "active",
            "dependsOn": [],
            "evidenceRefs": ["evidence:trust-receipt"],
            "confidenceBps": 9800,
            "contentDigest": sha("a"),
            "validFrom": "2026-07-22T03:30:00Z",
            "validUntil": "2026-07-22T04:30:00Z",
            "recordedAt": "2026-07-22T03:31:00Z",
        },
        {
            "assumptionId": "assumption:target-reversible",
            "status": "active",
            "dependsOn": ["assumption:evidence-current"],
            "evidenceRefs": ["evidence:rollback-rehearsal"],
            "confidenceBps": 9700,
            "contentDigest": sha("b"),
            "validFrom": "2026-07-22T03:45:00Z",
            "validUntil": "2026-07-22T04:25:00Z",
            "recordedAt": "2026-07-22T03:46:00Z",
        },
        {
            "assumptionId": "assumption:executor-healthy",
            "status": "active",
            "dependsOn": [],
            "evidenceRefs": ["evidence:executor-health"],
            "confidenceBps": 9600,
            "contentDigest": sha("c"),
            "validFrom": "2026-07-22T04:00:00Z",
            "validUntil": "2026-07-22T04:10:00Z",
            "recordedAt": "2026-07-22T04:00:30Z",
        },
    ],
    "nogoods": [
        {
            "nogoodId": "nogood:reversible-and-irreversible",
            "assumptionRefs": ["assumption:target-reversible", "assumption:executor-healthy"],
        }
    ],
    "riskBudget": {
        "maximumSelectiveRiskBps": 500,
        "minimumCoverageBps": 7000,
        "maximumCalibrationErrorBps": 300,
        "maximumDistributionShiftBps": 400,
        "minimumCalibrationSamples": 500,
    },
    "riskCertificate": {
        "certificateId": "risk-certificate:ontology:0001",
        "method": "conformal-risk-control",
        "sampleSize": 5000,
        "coverageBps": 8200,
        "riskUpperBoundBps": 320,
        "expectedCalibrationErrorBps": 120,
        "distributionShiftBps": 180,
        "scoreThresholdBps": 7600,
        "generatedAt": "2026-07-22T03:00:00Z",
        "validUntil": "2026-07-22T04:20:00Z",
        "evidenceDigest": sha("d"),
    },
    "runtimeAssurance": {
        "monitorId": "monitor:ontology:0001",
        "monitorPrincipalRef": "service:runtime-assurance",
        "monitorIndependent": True,
        "fallbackControllerRef": "service:ontology-safe-fallback",
        "fallbackReady": True,
        "observedAt": "2026-07-22T04:04:30Z",
        "validUntil": "2026-07-22T04:07:00Z",
        "hazardScoreBps": 1800,
        "takeoverThresholdBps": 3500,
        "invariants": [
            {"invariantId": "rollback-exact", "status": "pass", "evidenceDigest": sha("e")},
            {"invariantId": "write-scope-bounded", "status": "pass", "evidenceDigest": sha("f")},
            {"invariantId": "executor-identity-current", "status": "pass", "evidenceDigest": sha("1")},
        ],
    },
    "authority": {
        "judgmentOnly": True,
        "executionApplied": False,
        "mandateConstructed": False,
        "policyMutationApplied": False,
        "authorityMutationApplied": False,
        "selfExpansionAllowed": False,
    },
}

EXPECTED_RECEIPT_DIGEST = "sha256:97ab8e066f814974527aba058146718ab496a9a9cec17570bd40b4f26b719d1b"
