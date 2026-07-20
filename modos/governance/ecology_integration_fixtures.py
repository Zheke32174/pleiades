#!/usr/bin/env python3
API = "modos.pleiades/v1alpha1"


def sha(character):
    return "sha256:" + character * 64


CANDIDATE = {
    "apiVersion": API,
    "kind": "EcologyIntegrationCandidate",
    "candidateId": "ecology-integration:0001",
    "bindings": {
        "publicEcologyDigest": sha("1"),
        "privateEcologyDigest": sha("2"),
        "executiveAuthorityDigest": sha("3"),
        "workspaceReceiptDigest": sha("4"),
        "learningSpineReceiptDigest": sha("5"),
        "distributedAdmissionReceiptDigest": sha("6"),
    },
    "relations": [
        {"sourceRef": "executive-authority", "targetRef": "public-ecology", "type": "governed-by"},
        {"sourceRef": "executive-authority", "targetRef": "private-ecology", "type": "governed-by"},
        {"sourceRef": "service-joints", "targetRef": "executive-workspace", "type": "contributes-to"},
        {"sourceRef": "learning-spine", "targetRef": "executive-workspace", "type": "evidence-for"},
        {"sourceRef": "distributed-admission", "targetRef": "executive-authority", "type": "requires-authorization"},
    ],
    "ontologyClosure": {
        "receiptDigest": sha("7"),
        "snapshotDigest": sha("8"),
        "sourceManifestDigest": sha("9"),
        "sourceScopes": ["public", "private"],
        "seedOnly": False,
        "objectCount": 120,
        "relationCount": 240,
        "verifiedAgainstLivePrivateRegistry": False,
    },
    "serviceLearningJoints": [
        {
            "serviceRef": "service:telemetry",
            "structuredOutputs": ["observation", "decision", "evidence", "outcome", "correction", "provenance"],
            "blindSelfTrainingAllowed": False,
            "provenanceDigest": sha("a"),
        },
        {
            "serviceRef": "service:policy",
            "structuredOutputs": ["observation", "decision", "evidence", "outcome", "correction", "provenance"],
            "blindSelfTrainingAllowed": False,
            "provenanceDigest": sha("b"),
        },
        {
            "serviceRef": "service:admission",
            "structuredOutputs": ["observation", "decision", "evidence", "outcome", "correction", "provenance"],
            "blindSelfTrainingAllowed": False,
            "provenanceDigest": sha("c"),
        },
    ],
    "simulation": {
        "candidateDigest": sha("d"),
        "simulationDigest": sha("e"),
        "counterfactualDigest": sha("f"),
        "scenarioCount": 64,
        "deterministicReplay": True,
        "realMutationApplied": False,
        "predictedSuccessBps": 8400,
    },
    "calibration": {"observedSuccessBps": 8200, "maximumCalibrationErrorBps": 500},
    "improvementEvaluation": {
        "userFacing": True,
        "machineMetrics": [
            {"metric": "recovery-seconds", "before": 900, "after": 300, "betterWhen": "lower"},
            {"metric": "closure-pass-rate-bps", "before": 7000, "after": 9500, "betterWhen": "higher"},
        ],
        "stewardVerification": {"status": "verified", "independent": True},
        "ordinaryPersonEvaluation": {"blinded": True, "trials": 10, "preferenceRateBps": 7000},
    },
    "promotionCriteria": {
        "machineMeasurable": True,
        "stewardVerifiable": True,
        "ordinaryPersonNoticeableWhenApplicable": True,
    },
    "treaties": [
        {
            "treatyId": "treaty:external-agent:0001",
            "localPrincipalRef": "mind:pleiades",
            "remotePrincipalRef": "agent:external-reviewer",
            "scopes": ["evidence.exchange", "proposal.review"],
            "reciprocal": True,
            "revocable": True,
            "constitutionalDelegationAllowed": False,
            "replayNonce": "treaty-nonce-0000001",
            "treatyDigest": sha("0"),
        }
    ],
    "authority": {
        "readinessOnly": True,
        "liveMutationApplied": False,
        "treatyActivationApplied": False,
        "trainingApplied": False,
    },
}

EXPECTED = "sha256:e1708df21a1ae26afae98313395a839512bc0408a63a6e27f6284df3547e7b99"
