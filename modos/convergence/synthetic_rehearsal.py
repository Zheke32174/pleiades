#!/usr/bin/env python3
"""Run a deterministic, non-live end-to-end Pleiades rehearsal.

The rehearsal compiles public and synthetic-private ecology scopes, closes a
canary-first rollout, reports a failed canary with exact rollback, ingests
independently verified outcomes, and updates competence without mutating any
grant or constitutional authority.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ONTOLOGY = ROOT / "modos" / "ontology"
GOVERNANCE = ROOT / "modos" / "governance"
for path in (ONTOLOGY, GOVERNANCE):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import compiler  # type: ignore  # noqa: E402
import ecology_adapter  # type: ignore  # noqa: E402
import distributed_admission  # type: ignore  # noqa: E402
import distributed_fixtures  # type: ignore  # noqa: E402
import execution  # type: ignore  # noqa: E402
import control_plane_fixtures  # type: ignore  # noqa: E402
import learning_spine  # type: ignore  # noqa: E402
import competence  # type: ignore  # noqa: E402

API = "modos.pleiades/v1alpha1"


class RehearsalError(ValueError):
    pass


def sha(character: str) -> str:
    return "sha256:" + character * 64


def inventory_digest(repositories: list[str]) -> str:
    value = ("\n".join(sorted(repositories, key=str.lower)) + "\n").encode("utf-8")
    return "sha256:" + hashlib.sha256(value).hexdigest()


def synthetic_private_registry() -> dict[str, Any]:
    repositories = ["SyntheticLab/private-runtime", "SyntheticLab/private-spine"]
    return {
        "apiVersion": API,
        "kind": "EcologyRegistry",
        "metadata": {
            "name": "synthetic-private-ecology",
            "owner": "SyntheticLab",
            "observedAt": "2026-07-20T22:00:00Z",
            "visibility": "private",
            "source": "Synthetic fixture containing no real private identities",
            "sourceDigest": inventory_digest(repositories),
            "notes": "Rehearsal-only private scope. Never substitute for Undergrowth.",
        },
        "spec": {
            "precedence": [
                "Promoted Pleiades constitution and public contracts",
                "Synthetic rehearsal private registry",
                "Synthetic component manifests",
            ],
            "inventory": {"expectedCount": 2, "repositories": repositories},
            "groups": [
                {
                    "id": "synthetic-private-governance",
                    "description": "Synthetic private governance spine",
                    "lifecycle": "canonical",
                    "disposition": "canonical",
                    "subsystem": "private-governance",
                    "authorityCeiling": "domain-control",
                    "repositories": ["SyntheticLab/private-spine"],
                },
                {
                    "id": "synthetic-private-runtime",
                    "description": "Synthetic private runtime substrate",
                    "lifecycle": "operational",
                    "disposition": "active",
                    "subsystem": "private-runtime",
                    "authorityCeiling": "local-enforcement",
                    "repositories": ["SyntheticLab/private-runtime"],
                },
            ],
            "canonicalScopes": {
                "synthetic-private-ecology": "repo:SyntheticLab/private-spine",
                "synthetic-private-runtime": "repo:SyntheticLab/private-runtime",
            },
            "components": [
                {
                    "componentId": "synthetic-private-spine",
                    "repository": "SyntheticLab/private-spine",
                    "manifestPath": "MODOS_COMPONENT.yaml",
                    "manifestState": "present",
                },
                {
                    "componentId": "synthetic-private-node",
                    "repository": "SyntheticLab/private-runtime",
                    "manifestPath": "MODOS_COMPONENT.yaml",
                    "manifestState": "present",
                },
            ],
            "capabilities": [
                {
                    "id": "synthetic.private.ecology.close",
                    "version": "v1alpha1",
                    "providerRef": "repo:SyntheticLab/private-spine",
                    "status": "canonical",
                },
                {
                    "id": "synthetic.private.runtime.observe",
                    "version": "v1alpha1",
                    "providerRef": "repo:SyntheticLab/private-runtime",
                    "status": "operational",
                },
            ],
            "relations": [
                {
                    "type": "canonical-for",
                    "sourceRef": "repo:SyntheticLab/private-spine",
                    "targetRef": "scope:synthetic-private-ecology",
                    "scope": "governance",
                    "required": True,
                },
                {
                    "type": "canonical-for",
                    "sourceRef": "repo:SyntheticLab/private-runtime",
                    "targetRef": "scope:synthetic-private-runtime",
                    "scope": "runtime",
                    "required": True,
                },
                {
                    "type": "governed-by",
                    "sourceRef": "repo:SyntheticLab/private-runtime",
                    "targetRef": "repo:SyntheticLab/private-spine",
                    "scope": "governance",
                    "required": True,
                },
            ],
            "invariants": {
                "completeInventory": True,
                "uniqueMembership": True,
                "singleCanonicalProvider": True,
                "archiveIsolation": True,
                "authorityMonotonicity": True,
                "noDanglingRequiredRelations": True,
            },
            "exceptions": [],
        },
    }


def merge_snapshots(public: dict[str, Any], private: dict[str, Any]) -> dict[str, Any]:
    objects: dict[str, dict[str, Any]] = {}
    for source_name, snapshot in (("public", public), ("synthetic-private", private)):
        for obj in snapshot["objects"]:
            object_id = obj["metadata"]["id"]
            if object_id in {"mind:pleiades", "workspace:pleiades"} and source_name == "synthetic-private":
                continue
            if object_id in objects:
                raise RehearsalError(f"duplicate merged object identity: {object_id}")
            objects[object_id] = obj

    relations: dict[tuple[str, str, str, bytes], dict[str, Any]] = {}
    for snapshot in (public, private):
        for relation in snapshot["relations"]:
            if relation["sourceRef"] == "mind:pleiades" and relation["targetRef"] == "workspace:pleiades":
                key = (
                    relation["sourceRef"],
                    relation["type"],
                    relation["targetRef"],
                    compiler.canonical_bytes(relation.get("attributes", {})),
                )
                relations.setdefault(key, relation)
                continue
            key = (
                relation["sourceRef"],
                relation["type"],
                relation["targetRef"],
                compiler.canonical_bytes(relation.get("attributes", {})),
            )
            if key in relations:
                raise RehearsalError("duplicate merged relation")
            relations[key] = relation

    return compiler.normalize_snapshot(
        {
            "apiVersion": API,
            "kind": "OntologySnapshot",
            "schemaVersion": "v1alpha1",
            "mindId": "mind:pleiades",
            "objects": list(objects.values()),
            "relations": list(relations.values()),
        }
    )


def outcome_records(execution_receipt: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    evidence: list[dict[str, Any]] = []
    memory: list[dict[str, Any]] = []
    execution_digest = competence.digest(execution_receipt)
    for index in range(1, 11):
        outcome_id = f"outcome:synthetic-rollback:{index:04d}"
        content_digest = "sha256:" + format(index + 400, "064x")
        evidence_digest = "sha256:" + format(index + 500, "064x")
        evidence.append(
            {
                "apiVersion": API,
                "kind": "OutcomeEvidence",
                "outcomeId": outcome_id,
                "principalRef": "mind:pleiades",
                "verifierRef": "service:synthetic-outcome-verifier",
                "domain": "ontology",
                "action": "authorize-admission",
                "riskTier": "bounded-persistent",
                "result": "rolled-back",
                "confidenceBps": 9500,
                "executionReceiptDigest": execution_digest,
                "evidenceDigest": evidence_digest,
                "verifiedAt": f"2026-07-21T23:{index:02d}:00Z",
                "verification": {"status": "verified", "independent": True},
            }
        )
        memory.append(
            {
                "recordId": outcome_id,
                "recordKind": "outcome",
                "recordedAt": f"2026-07-21T23:{index:02d}:00Z",
                "contentDigest": content_digest,
                "evidenceDigest": evidence_digest,
                "domain": "ontology",
                "objective": "rehearse-safe-rollback",
                "visibility": "internal",
                "retentionClass": "evidence",
                "semanticTags": ["synthetic-rehearsal", "rollback", "verified-outcome"],
                "verification": {"status": "verified", "independent": True},
                "source": {"sourceType": "service", "principalRef": "service:synthetic-outcome-verifier"},
                "trainingEligible": True,
                "relationRefs": [],
                "narrativeSummary": "Synthetic canary failure was rolled back to the exact predecessor.",
            }
        )
    return evidence, memory


def run_rehearsal(public_registry: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    private_registry = synthetic_private_registry()
    public_snapshot, public_receipt = ecology_adapter.compile_registry(public_registry, schema)
    private_snapshot, private_receipt = ecology_adapter.compile_registry(private_registry, schema)
    merged = merge_snapshots(public_snapshot, private_snapshot)

    rollout_receipt = distributed_admission.close_rollout(
        copy.deepcopy(distributed_fixtures.REGISTRY),
        copy.deepcopy(distributed_fixtures.PLAN),
        [],
    )
    replay_receipt = distributed_admission.close_rollout(
        copy.deepcopy(distributed_fixtures.REGISTRY),
        copy.deepcopy(distributed_fixtures.PLAN),
        [
            {
                "replayNonce": rollout_receipt["replayNonce"],
                "idempotencyKey": rollout_receipt["idempotencyKey"],
                "planDigest": rollout_receipt["planDigest"],
                "stageSchedule": rollout_receipt["stageSchedule"],
                "rollbackGroups": rollout_receipt["rollbackGroups"],
            }
        ],
    )

    execution_receipt, rollback_receipt = execution.evaluate_execution(
        copy.deepcopy(control_plane_fixtures.AUTHORIZATION),
        copy.deepcopy(control_plane_fixtures.MANDATE),
        copy.deepcopy(control_plane_fixtures.ROLLBACK_ATTEMPT),
    )
    if execution_receipt["status"] != "rolled-back" or rollback_receipt["status"] != "succeeded":
        raise RehearsalError("synthetic failed canary did not restore the exact predecessor")

    outcomes, memory_records = outcome_records(execution_receipt)
    learning_batch = {
        "apiVersion": API,
        "kind": "LearningSpineBatch",
        "batchId": "learning:synthetic-rehearsal-0001",
        "mindId": "mind:pleiades",
        "policy": {
            "verifiedOutcomesOnlyForTraining": True,
            "preserveCorrections": True,
            "preserveContradictions": True,
        },
        "records": memory_records,
        "authority": {
            "appendOnly": True,
            "historyErasureAllowed": False,
            "trainingApplied": False,
            "authorityMutationApplied": False,
        },
    }
    learning_receipt = learning_spine.close_spine(learning_batch)
    profile, competence_receipt = competence.update_competence(
        copy.deepcopy(control_plane_fixtures.PROFILE),
        outcomes,
        control_plane_fixtures.GRANT["grantId"],
    )

    authority_mutation = any(
        (
            rollout_receipt["authority"].get("canonicalMutationApplied"),
            execution_receipt["authority"].get("authorityExpanded"),
            learning_receipt["authority"].get("authorityMutationApplied"),
            competence_receipt["authority"].get("grantMutationApplied"),
            profile["authority"].get("grantMutationApplied"),
        )
    )
    if authority_mutation:
        raise RehearsalError("synthetic rehearsal applied forbidden authority mutation")
    if competence_receipt["recommendation"]["proposal"] is not None:
        raise RehearsalError("rollback-only rehearsal must not propose authority growth")

    receipt = {
        "apiVersion": API,
        "kind": "SyntheticEndToEndRehearsalReceipt",
        "status": "pass",
        "scope": "synthetic-two-scope",
        "publicRegistryDigest": compiler.digest(public_registry),
        "syntheticPrivateRegistryDigest": compiler.digest(private_registry),
        "publicCompilationReceiptDigest": compiler.digest(public_receipt),
        "privateCompilationReceiptDigest": compiler.digest(private_receipt),
        "mergedSnapshotDigest": compiler.snapshot_digest(merged),
        "mergedObjectCount": len(merged["objects"]),
        "mergedRelationCount": len(merged["relations"]),
        "rolloutReceiptDigest": distributed_admission.digest(rollout_receipt),
        "idempotentReplayReceiptDigest": distributed_admission.digest(replay_receipt),
        "executionReceiptDigest": execution.digest(execution_receipt),
        "rollbackReceiptDigest": execution.digest(rollback_receipt),
        "learningReceiptDigest": learning_spine.digest(learning_receipt),
        "competenceProfileDigest": competence.digest(profile),
        "competenceReceiptDigest": competence.digest(competence_receipt),
        "feedbackRecordCount": len(learning_receipt["feedbackManifest"]["verifiedOutcomeRecords"]),
        "competenceRecommendation": competence_receipt["recommendation"]["action"],
        "checks": [
            {"name": "public-ecology-compiled", "status": "pass"},
            {"name": "synthetic-private-ecology-compiled", "status": "pass"},
            {"name": "two-scope-ontology-closed", "status": "pass"},
            {"name": "canary-first-rollout-closed", "status": "pass"},
            {"name": "exact-idempotent-replay", "status": "pass"},
            {"name": "failed-canary-rolled-back", "status": "pass"},
            {"name": "verified-outcomes-ingested", "status": "pass"},
            {"name": "competence-updated", "status": "pass"},
            {"name": "authority-not-expanded", "status": "pass"},
        ],
        "livePrivateEcologySupplied": False,
        "liveExecutionApplied": False,
        "trainingApplied": False,
        "grantMutationApplied": False,
        "constitutionalMutationApplied": False,
        "remainingBlockers": [
            "live-private-exhaustive-registry-not-supplied",
            "live-substrate-loop-not-authorized-or-executed",
            "sustained-autonomy-evidence-not-observed",
        ],
        "authority": {"ceiling": "none", "canonicalMutationApplied": False},
    }
    receipt["receiptDigest"] = compiler.digest(receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--public-registry", type=Path, default=ROOT / "modos" / "ecology" / "public-ecology.json")
    parser.add_argument("--schema", type=Path, default=ROOT / "modos" / "contracts" / "ecology-registry.schema.json")
    parser.add_argument("--report", type=Path, default=ROOT / "artifacts" / "synthetic-rehearsal-receipt.json")
    args = parser.parse_args()
    try:
        receipt = run_rehearsal(compiler.load_json_strict(args.public_registry), compiler.load_json_strict(args.schema))
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"synthetic rehearsal {receipt['status']}: {receipt['receiptDigest']}")
        return 0
    except (
        OSError,
        json.JSONDecodeError,
        RehearsalError,
        compiler.OntologyCompileError,
        ecology_adapter.EcologyAdapterError,
        distributed_admission.DistributedAdmissionError,
        execution.ExecutionEvidenceError,
        learning_spine.LearningSpineError,
        competence.CompetenceError,
    ) as exc:
        print(f"synthetic rehearsal failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
