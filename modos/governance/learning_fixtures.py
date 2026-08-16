#!/usr/bin/env python3
API = "modos.pleiades/v1alpha1"


def sha(character):
    return "sha256:" + character * 64


def record(record_id, kind, domain, objective, tag, content, evidence, source_type="service", principal="service:evidence", verified="verified", independent=True, **extra):
    value = {
        "recordId": record_id,
        "recordKind": kind,
        "recordedAt": extra.pop("recordedAt", "2026-07-21T00:00:00Z"),
        "domain": domain,
        "objective": objective,
        "semanticTags": [tag],
        "contentDigest": sha(content),
        "evidenceDigest": sha(evidence),
        "visibility": extra.pop("visibility", "internal"),
        "retentionClass": extra.pop("retentionClass", "evidence"),
        "verification": {"status": verified, "independent": independent},
        "source": {"sourceType": source_type, "principalRef": principal},
        "relationRefs": extra.pop("relationRefs", []),
        "trainingEligible": extra.pop("trainingEligible", False),
    }
    value.update(extra)
    return value


RECORDS = [
    record(
        "record:observation", "observation", "ontology", "admit-snapshot", "telemetry", "1", "a",
        recordedAt="2026-07-21T00:00:01Z", claimKey="ontology.health", claimValue="healthy",
        narrativeSummary="Initial observed health.",
    ),
    record("record:decision", "decision", "ontology", "admit-snapshot", "decision", "2", "b", recordedAt="2026-07-21T00:00:02Z"),
    record(
        "record:mandate", "mandate", "ontology", "admit-snapshot", "mandate", "3", "c",
        recordedAt="2026-07-21T00:00:03Z", relationRefs=["record:decision"],
    ),
    record(
        "record:outcome", "outcome", "ontology", "admit-snapshot", "outcome", "4", "d",
        recordedAt="2026-07-21T00:00:04Z", trainingEligible=True,
        source_type="service", principal="service:outcome-verifier",
        claimKey="ontology.health", claimValue="degraded",
    ),
    record(
        "record:correction", "correction", "ontology", "admit-snapshot", "correction", "5", "e",
        recordedAt="2026-07-21T00:00:05Z", correctsRefs=["record:observation"],
        claimKey="ontology.health", claimValue="degraded",
    ),
    record(
        "record:provenance", "provenance", "ontology", "admit-snapshot", "provenance", "6", "f",
        recordedAt="2026-07-21T00:00:06Z", relationRefs=["record:outcome"],
    ),
]

BATCH = {
    "apiVersion": API,
    "kind": "LearningSpineBatch",
    "batchId": "learning-batch:0001",
    "mindId": "mind:pleiades",
    "policy": {
        "verifiedOutcomesOnlyForTraining": True,
        "preserveCorrections": True,
        "preserveContradictions": True,
    },
    "records": RECORDS,
    "authority": {
        "appendOnly": True,
        "historyErasureAllowed": False,
        "trainingApplied": False,
        "authorityMutationApplied": False,
    },
}

EXPECTED = "sha256:4940ed5f0d073dc9760d74f4c3eef0e096e34394792ad75516b30214981531a6"
