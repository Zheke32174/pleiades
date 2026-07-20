#!/usr/bin/env python3
"""Generate an empty, schema-valid operator input candidate template."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

API_VERSION = "modos.pleiades/v1alpha1"
INPUT_CLASSIFICATIONS = {
    "privateEcology": "private-reference",
    "observedInventory": "private-reference",
    "nodeInventory": "live-evidence",
    "signingIdentity": "sovereign-decision",
    "historyDecision": "sovereign-decision",
    "authorityGrant": "sovereign-decision",
    "canaryPlan": "live-evidence",
    "observationPlan": "live-evidence",
}
REQUESTED_OUTPUTS = [
    "private-closure-candidate",
    "history-rewrite-decision-record",
    "node-admission-candidate",
    "grant-issuance-proposal",
    "canary-admission-plan",
    "observation-window-plan",
    "next-progression-candidate",
]


def empty_reference(classification: str) -> dict:
    return {
        "supplied": False,
        "classification": classification,
        "artifactRef": None,
        "artifactDigest": None,
        "receiptDigest": None,
        "embeddedPayload": False,
        "privateKeyMaterialIncluded": False,
        "externalSideEffectApplied": False,
    }


def build_template(source_commit: str, created_at: str, candidate_id: str) -> dict:
    return {
        "apiVersion": API_VERSION,
        "kind": "OperatorInputCandidate",
        "candidateId": candidate_id,
        "sourceCommit": source_commit,
        "createdAt": created_at,
        "inputs": {
            input_id: empty_reference(classification)
            for input_id, classification in INPUT_CLASSIFICATIONS.items()
        },
        "decisions": {
            "historyRewrite": "pending",
            "authorizationRef": None,
            "planDigest": None,
        },
        "selections": {
            "canaryNodeId": None,
            "observationWindowSeconds": None,
        },
        "requestedOutputs": list(REQUESTED_OUTPUTS),
        "authority": {
            "ceiling": "none",
            "proposalOnly": True,
            "canonicalMutationApplied": False,
            "liveExecutionApplied": False,
            "historyRewriteApplied": False,
            "grantIssued": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--created-at", required=True)
    parser.add_argument("--candidate-id", default="operator-input-candidate:operator-template-0001")
    parser.add_argument("--out", type=Path, default=Path("artifacts/operator-input-candidate.template.json"))
    args = parser.parse_args()
    candidate = build_template(args.source_commit, args.created_at, args.candidate_id)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(candidate, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
