#!/usr/bin/env python3
API = "modos.pleiades/v1alpha1"


def sha(character):
    return "sha256:" + character * 64


REGISTRY = {
    "apiVersion": API,
    "kind": "NodeCapabilityRegistry",
    "registryId": "nodes:pleiades-rollout-v1",
    "observedAt": "2026-07-20T23:00:00Z",
    "nodes": [
        {
            "nodeId": "node:canary",
            "hardwareDigest": sha("1"),
            "servicePrincipalRef": "service:admit-canary",
            "serviceIdentityDigest": sha("2"),
            "keyDigest": sha("3"),
            "capabilities": ["ontology.snapshot.admit", "rollback.exact"],
            "writeScopes": ["ontology:admitted-snapshot"],
            "authorityCeiling": "distributed-stage",
            "partitionPolicy": {"mode": "fail-closed", "maxOfflineSeconds": 0},
        },
        {
            "nodeId": "node:secondary",
            "hardwareDigest": sha("4"),
            "servicePrincipalRef": "service:admit-secondary",
            "serviceIdentityDigest": sha("5"),
            "keyDigest": sha("6"),
            "capabilities": ["ontology.snapshot.admit", "rollback.exact"],
            "writeScopes": ["ontology:admitted-snapshot"],
            "authorityCeiling": "distributed-stage",
            "partitionPolicy": {"mode": "fail-closed", "maxOfflineSeconds": 0},
        },
    ],
    "authority": {"closureOnly": True, "mayIssueCapabilities": False, "mayExecute": False},
}

PLAN = {
    "apiVersion": API,
    "kind": "DistributedRolloutPlan",
    "planId": "rollout:ontology:0001",
    "authorizationReceiptDigest": sha("7"),
    "mandateDigest": sha("8"),
    "targetDigest": sha("b"),
    "predecessorDigest": sha("a"),
    "rollbackDigest": sha("a"),
    "replayNonce": "nonce-ontology-0001",
    "idempotencyKey": "idempotency-ontology-0001",
    "createdAt": "2026-07-20T23:05:00Z",
    "expiresAt": "2026-07-21T00:05:00Z",
    "executorCapability": "ontology.snapshot.admit",
    "requiredAuthorityCeiling": "distributed-stage",
    "writeScope": "ontology:admitted-snapshot",
    "constraints": {"requireCanary": True, "automaticRollback": True, "maxParallelNodes": 1},
    "stages": [
        {
            "stageId": "stage:canary",
            "order": 1,
            "canary": True,
            "nodeRefs": ["node:canary"],
            "healthGateDigest": sha("c"),
        },
        {
            "stageId": "stage:secondary",
            "order": 2,
            "canary": False,
            "nodeRefs": ["node:secondary"],
            "healthGateDigest": sha("d"),
        },
    ],
}

HISTORY = []
EXPECTED = "sha256:f22a9c19321b94f9860b7f5fd694bbbe0908350f64632826c76364d6256984ed"
