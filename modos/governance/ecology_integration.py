#!/usr/bin/env python3
"""Deterministic full-ecology integration readiness gate.

The gate binds executive authority, ecology closure, service learning joints,
simulation, calibration, human-noticeable evaluation, promotion criteria, and
external treaties. It does not claim live-loop completion.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Iterable

API_VERSION = "modos.pleiades/v1alpha1"


class IntegrationReadinessError(ValueError):
    pass


def _reject_float(value):
    raise IntegrationReadinessError(f"floating-point values are forbidden: {value}")


def _reject_constant(value):
    raise IntegrationReadinessError(f"non-finite JSON constant is forbidden: {value}")


def _pairs(items: Iterable[tuple[str, Any]]):
    result = {}
    for key, value in items:
        if key in result:
            raise IntegrationReadinessError(f"duplicate JSON key is forbidden: {key}")
        result[key] = value
    return result


def load_json_strict(path: Path):
    return json.loads(path.read_text(), parse_float=_reject_float, parse_constant=_reject_constant, object_pairs_hook=_pairs)


def canonical_bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value):
    return "sha256:" + hashlib.sha256(canonical_bytes(value)).hexdigest()


def _sha(value, field):
    if not isinstance(value, str) or len(value) != 71 or not value.startswith("sha256:"):
        raise IntegrationReadinessError(f"{field} must be sha256-bound")


def evaluate(candidate: dict[str, Any]) -> dict[str, Any]:
    if candidate.get("apiVersion") != API_VERSION or candidate.get("kind") != "EcologyIntegrationCandidate":
        raise IntegrationReadinessError("unsupported ecology integration candidate")
    if candidate.get("authority") != {
        "readinessOnly": True,
        "liveMutationApplied": False,
        "treatyActivationApplied": False,
        "trainingApplied": False,
    }:
        raise IntegrationReadinessError("integration authority boundary is not exact")

    bindings = candidate.get("bindings")
    if not isinstance(bindings, dict):
        raise IntegrationReadinessError("integration bindings are required")
    for field in (
        "publicEcologyDigest",
        "privateEcologyDigest",
        "executiveAuthorityDigest",
        "workspaceReceiptDigest",
        "learningSpineReceiptDigest",
        "distributedAdmissionReceiptDigest",
    ):
        _sha(bindings.get(field), f"bindings.{field}")

    required_relations = {
        ("executive-authority", "public-ecology", "governed-by"),
        ("executive-authority", "private-ecology", "governed-by"),
        ("service-joints", "executive-workspace", "contributes-to"),
        ("learning-spine", "executive-workspace", "evidence-for"),
        ("distributed-admission", "executive-authority", "requires-authorization"),
    }
    relations = candidate.get("relations")
    if not isinstance(relations, list):
        raise IntegrationReadinessError("integration relations are required")
    actual_relations = set()
    for relation in relations:
        triple = (relation.get("sourceRef"), relation.get("targetRef"), relation.get("type"))
        if None in triple:
            raise IntegrationReadinessError("integration relation is incomplete")
        actual_relations.add(triple)
    if required_relations - actual_relations:
        raise IntegrationReadinessError("integration relations are incomplete")

    ontology = candidate.get("ontologyClosure")
    if not isinstance(ontology, dict):
        raise IntegrationReadinessError("ontology closure is required")
    for field in ("receiptDigest", "snapshotDigest", "sourceManifestDigest"):
        _sha(ontology.get(field), f"ontologyClosure.{field}")
    scopes = ontology.get("sourceScopes")
    if not isinstance(scopes, list) or not {"public", "private"}.issubset(scopes):
        raise IntegrationReadinessError("full ontology closure must bind public and private scopes")
    if ontology.get("seedOnly") is True:
        raise IntegrationReadinessError("seed-only ontology cannot satisfy full ecology readiness")
    if not isinstance(ontology.get("objectCount"), int) or ontology["objectCount"] < 20:
        raise IntegrationReadinessError("full ontology object count is insufficient")
    if not isinstance(ontology.get("relationCount"), int) or ontology["relationCount"] < 10:
        raise IntegrationReadinessError("full ontology relation count is insufficient")
    if ontology.get("verifiedAgainstLivePrivateRegistry") is not True:
        ontology_ready = False
        ontology_blocker = "full private registry compile receipt is not live-verified"
    else:
        ontology_ready = True
        ontology_blocker = None

    joints = candidate.get("serviceLearningJoints")
    if not isinstance(joints, list) or len(joints) < 3:
        raise IntegrationReadinessError("at least three service learning joints are required")
    joint_ids = set()
    required_outputs = {"observation", "decision", "evidence", "outcome", "correction", "provenance"}
    for joint in joints:
        service_ref = joint.get("serviceRef")
        if not isinstance(service_ref, str) or not service_ref or service_ref in joint_ids:
            raise IntegrationReadinessError("service joint identities must be unique")
        joint_ids.add(service_ref)
        outputs = joint.get("structuredOutputs")
        if not isinstance(outputs, list) or not required_outputs.issubset(outputs):
            raise IntegrationReadinessError(f"{service_ref} learning joint output surface is incomplete")
        if joint.get("blindSelfTrainingAllowed") is not False:
            raise IntegrationReadinessError(f"{service_ref} cannot allow blind self-training")
        _sha(joint.get("provenanceDigest"), f"{service_ref}.provenanceDigest")

    simulation = candidate.get("simulation")
    if not isinstance(simulation, dict):
        raise IntegrationReadinessError("simulation evaluation is required")
    for field in ("candidateDigest", "simulationDigest", "counterfactualDigest"):
        _sha(simulation.get(field), f"simulation.{field}")
    if not isinstance(simulation.get("scenarioCount"), int) or simulation["scenarioCount"] < 10:
        raise IntegrationReadinessError("simulation requires at least ten scenarios")
    if simulation.get("deterministicReplay") is not True or simulation.get("realMutationApplied") is not False:
        raise IntegrationReadinessError("simulation must be replayable and non-mutating")
    simulated_score = simulation.get("predictedSuccessBps")
    if not isinstance(simulated_score, int) or not 0 <= simulated_score <= 10000:
        raise IntegrationReadinessError("predictedSuccessBps is invalid")

    calibration = candidate.get("calibration")
    if not isinstance(calibration, dict):
        raise IntegrationReadinessError("simulation-real calibration is required")
    observed_score = calibration.get("observedSuccessBps")
    maximum_error = calibration.get("maximumCalibrationErrorBps")
    if not isinstance(observed_score, int) or not 0 <= observed_score <= 10000 or not isinstance(maximum_error, int) or maximum_error < 0:
        raise IntegrationReadinessError("calibration values are invalid")
    calibration_error = abs(simulated_score - observed_score)
    if calibration_error > maximum_error:
        raise IntegrationReadinessError("simulation calibration error exceeds policy")

    evaluation = candidate.get("improvementEvaluation")
    if not isinstance(evaluation, dict):
        raise IntegrationReadinessError("improvement evaluation is required")
    metrics = evaluation.get("machineMetrics")
    if not isinstance(metrics, list) or not metrics:
        raise IntegrationReadinessError("machine metrics are required")
    improved = 0
    for metric in metrics:
        if not isinstance(metric.get("before"), int) or not isinstance(metric.get("after"), int):
            raise IntegrationReadinessError("machine metric values must be integers")
        direction = metric.get("betterWhen")
        if direction == "higher" and metric["after"] > metric["before"]:
            improved += 1
        elif direction == "lower" and metric["after"] < metric["before"]:
            improved += 1
        elif direction not in {"higher", "lower"}:
            raise IntegrationReadinessError("machine metric direction is unsupported")
    if improved != len(metrics):
        raise IntegrationReadinessError("every required machine metric must improve")
    if evaluation.get("stewardVerification") != {"status": "verified", "independent": True}:
        raise IntegrationReadinessError("steward verification is incomplete")
    ordinary = evaluation.get("ordinaryPersonEvaluation")
    if evaluation.get("userFacing") is True:
        if not isinstance(ordinary, dict) or ordinary.get("blinded") is not True or ordinary.get("trials", 0) < 5 or ordinary.get("preferenceRateBps", 0) < 6000:
            raise IntegrationReadinessError("user-facing change lacks ordinary-person noticeable evidence")
        ordinary_status = "pass"
    else:
        ordinary_status = "not-applicable"

    if candidate.get("promotionCriteria") != {
        "machineMeasurable": True,
        "stewardVerifiable": True,
        "ordinaryPersonNoticeableWhenApplicable": True,
    }:
        raise IntegrationReadinessError("three-part promotion criteria are not exact")

    treaties = candidate.get("treaties")
    if not isinstance(treaties, list) or not treaties:
        raise IntegrationReadinessError("at least one external treaty is required")
    treaty_ids = set()
    for treaty in treaties:
        treaty_id = treaty.get("treatyId")
        if not isinstance(treaty_id, str) or not treaty_id or treaty_id in treaty_ids:
            raise IntegrationReadinessError("treaty ids must be unique")
        treaty_ids.add(treaty_id)
        if treaty.get("localPrincipalRef") != "mind:pleiades":
            raise IntegrationReadinessError(f"{treaty_id} local principal must be mind:pleiades")
        if not treaty.get("remotePrincipalRef") or treaty.get("remotePrincipalRef") == "mind:pleiades":
            raise IntegrationReadinessError(f"{treaty_id} remote principal is invalid")
        treaty_scopes = treaty.get("scopes")
        if not isinstance(treaty_scopes, list) or not treaty_scopes or "*" in treaty_scopes:
            raise IntegrationReadinessError(f"{treaty_id} treaty scopes must be bounded")
        if treaty.get("reciprocal") is not True or treaty.get("revocable") is not True:
            raise IntegrationReadinessError(f"{treaty_id} treaty must be reciprocal and revocable")
        if treaty.get("constitutionalDelegationAllowed") is not False:
            raise IntegrationReadinessError(f"{treaty_id} cannot delegate constitutional authority")
        if not isinstance(treaty.get("replayNonce"), str) or len(treaty["replayNonce"]) < 16:
            raise IntegrationReadinessError(f"{treaty_id} replay nonce is too weak")
        _sha(treaty.get("treatyDigest"), f"{treaty_id}.treatyDigest")

    blockers = []
    if not ontology_ready:
        blockers.append(ontology_blocker)
    blockers.extend([
        "live admission-observation-rollback loop not executed",
        "sustained bounded autonomous operation not demonstrated",
    ])
    return {
        "apiVersion": API_VERSION,
        "kind": "EcologyIntegrationReadinessReceipt",
        "candidateId": candidate["candidateId"],
        "status": "repository-ready-live-blocked",
        "candidateDigest": digest(candidate),
        "ontologyReady": ontology_ready,
        "serviceJointRefs": sorted(joint_ids),
        "simulation": {
            "scenarioCount": simulation["scenarioCount"],
            "predictedSuccessBps": simulated_score,
            "observedSuccessBps": observed_score,
            "calibrationErrorBps": calibration_error,
            "maximumCalibrationErrorBps": maximum_error,
        },
        "improvement": {
            "machineMetricsPassed": improved,
            "stewardVerification": "pass",
            "ordinaryPersonEvaluation": ordinary_status,
        },
        "treatyRefs": sorted(treaty_ids),
        "blockers": blockers,
        "checks": [
            {"name": "ecology-authority-bound", "status": "pass"},
            {"name": "public-private-scopes-declared", "status": "pass"},
            {"name": "service-learning-joints-closed", "status": "pass"},
            {"name": "predictive-simulation-bound", "status": "pass"},
            {"name": "simulation-real-calibration-bound", "status": "pass"},
            {"name": "ordinary-person-evaluation-bound", "status": "pass"},
            {"name": "three-part-promotion-criteria-bound", "status": "pass"},
            {"name": "external-treaties-bounded", "status": "pass"},
        ],
        "authority": {
            "liveMutationApplied": False,
            "treatyActivationApplied": False,
            "trainingApplied": False,
            "canonicalMutationApplied": False,
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--out-receipt", type=Path, required=True)
    args = parser.parse_args()
    try:
        receipt = evaluate(load_json_strict(args.candidate))
        args.out_receipt.parent.mkdir(parents=True, exist_ok=True)
        args.out_receipt.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
        print(receipt["status"])
        return 0
    except (OSError, json.JSONDecodeError, IntegrationReadinessError) as exc:
        print(f"ecology integration readiness failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
