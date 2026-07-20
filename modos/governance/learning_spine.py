#!/usr/bin/env python3
"""Deterministic Pleiades executive learning-spine closure.

The spine indexes immutable evidence records, preserves corrections and
contradictions, and emits a verified-only feedback manifest. It does not train
models, delete history, or mutate authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

API_VERSION = "modos.pleiades/v1alpha1"
RECORD_KINDS = {"observation", "decision", "mandate", "outcome", "correction", "provenance"}
VISIBILITY_ORDER = {"model-only": 0, "internal": 1, "steward-only": 2, "public": 3}
RETENTION = {"ephemeral": 86400, "operational": 2592000, "evidence": 315360000, "constitutional": -1}


class LearningSpineError(ValueError):
    pass


def _reject_float(value):
    raise LearningSpineError(f"floating-point values are forbidden: {value}")


def _reject_constant(value):
    raise LearningSpineError(f"non-finite JSON constant is forbidden: {value}")


def _pairs(items: Iterable[tuple[str, Any]]):
    result = {}
    for key, value in items:
        if key in result:
            raise LearningSpineError(f"duplicate JSON key is forbidden: {key}")
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
        raise LearningSpineError(f"{field} must be sha256-bound")


def _time(value, field):
    if not isinstance(value, str):
        raise LearningSpineError(f"{field} must be RFC3339")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise LearningSpineError(f"{field} must be RFC3339") from exc


def close_spine(spine: dict[str, Any]) -> dict[str, Any]:
    if spine.get("apiVersion") != API_VERSION or spine.get("kind") != "LearningSpineBatch":
        raise LearningSpineError("unsupported learning spine envelope")
    if spine.get("authority") != {
        "appendOnly": True,
        "historyErasureAllowed": False,
        "trainingApplied": False,
        "authorityMutationApplied": False,
    }:
        raise LearningSpineError("learning spine authority boundary is not exact")
    policy = spine.get("policy")
    if not isinstance(policy, dict):
        raise LearningSpineError("learning spine policy is required")
    if policy.get("verifiedOutcomesOnlyForTraining") is not True or policy.get("preserveCorrections") is not True or policy.get("preserveContradictions") is not True:
        raise LearningSpineError("learning spine policy must preserve evidence and restrict training")
    records = spine.get("records")
    if not isinstance(records, list) or not records:
        raise LearningSpineError("learning spine records must be nonempty")

    by_id = {}
    episodic = {}
    semantic = {}
    correction_edges = []
    provenance_edges = []
    contradiction_map = {}
    feedback = []
    current_claims = {}

    for record in sorted(records, key=lambda item: (item.get("recordedAt", ""), item.get("recordId", ""))):
        record_id = record.get("recordId")
        if not isinstance(record_id, str) or not record_id or record_id in by_id:
            raise LearningSpineError("record ids must be nonempty and unique")
        by_id[record_id] = record
        kind = record.get("recordKind")
        if kind not in RECORD_KINDS:
            raise LearningSpineError(f"{record_id} recordKind is unsupported")
        _time(record.get("recordedAt"), f"{record_id}.recordedAt")
        for field in ("contentDigest", "evidenceDigest"):
            _sha(record.get(field), f"{record_id}.{field}")
        domain = record.get("domain")
        objective = record.get("objective")
        if not isinstance(domain, str) or not domain or not isinstance(objective, str) or not objective:
            raise LearningSpineError(f"{record_id} domain and objective are required")
        visibility = record.get("visibility")
        retention = record.get("retentionClass")
        if visibility not in VISIBILITY_ORDER or retention not in RETENTION:
            raise LearningSpineError(f"{record_id} visibility or retention class is unsupported")
        if kind in {"decision", "mandate", "outcome", "correction", "provenance"} and retention == "ephemeral":
            raise LearningSpineError(f"{record_id} authority/evidence record cannot be ephemeral")
        tags = record.get("semanticTags")
        if not isinstance(tags, list) or not tags or len(set(tags)) != len(tags) or any(not isinstance(tag, str) or not tag or "*" in tag for tag in tags):
            raise LearningSpineError(f"{record_id} semanticTags must be bounded and unique")
        narrative = record.get("narrativeSummary")
        if narrative is not None and (not isinstance(narrative, str) or len(narrative) > 512):
            raise LearningSpineError(f"{record_id} narrative summary is invalid")
        verification = record.get("verification")
        if not isinstance(verification, dict) or verification.get("status") not in {"verified", "unverified", "disputed"} or not isinstance(verification.get("independent"), bool):
            raise LearningSpineError(f"{record_id} verification is invalid")
        source = record.get("source")
        if not isinstance(source, dict) or source.get("sourceType") not in {"human", "mind", "model", "service", "sensor"} or not source.get("principalRef"):
            raise LearningSpineError(f"{record_id} source is invalid")

        episode = f"{domain}|{objective}"
        episodic.setdefault(episode, []).append(record_id)
        for tag in tags:
            semantic.setdefault(tag, []).append(record_id)

        claim_key = record.get("claimKey")
        claim_value = record.get("claimValue")
        if claim_key is not None:
            if not isinstance(claim_key, str) or not claim_key or not isinstance(claim_value, str) or not claim_value:
                raise LearningSpineError(f"{record_id} claimKey and claimValue must be paired")
            if verification["status"] == "verified":
                prior = current_claims.get(claim_key)
                if prior and prior["claimValue"] != claim_value:
                    contradiction_map.setdefault(claim_key, set()).update({prior["recordId"], record_id})
                current_claims[claim_key] = {"recordId": record_id, "claimValue": claim_value}

        relation_refs = record.get("relationRefs", [])
        if not isinstance(relation_refs, list) or len(set(relation_refs)) != len(relation_refs):
            raise LearningSpineError(f"{record_id} relationRefs must be unique")
        if kind == "correction":
            corrected = record.get("correctsRefs")
            if not isinstance(corrected, list) or not corrected:
                raise LearningSpineError(f"{record_id} correction requires correctsRefs")
            for target in corrected:
                correction_edges.append({"correctionRef": record_id, "targetRef": target})
        if kind == "provenance":
            if not relation_refs:
                raise LearningSpineError(f"{record_id} provenance requires relationRefs")
            for target in relation_refs:
                provenance_edges.append({"sourceRef": record_id, "targetRef": target})

        if record.get("trainingEligible") is True:
            if kind != "outcome":
                raise LearningSpineError(f"{record_id} non-outcome cannot be training eligible")
            if verification != {"status": "verified", "independent": True}:
                raise LearningSpineError(f"{record_id} training outcome must be independently verified")
            if source["sourceType"] in {"mind", "model"} and source.get("principalRef") == spine.get("mindId"):
                raise LearningSpineError(f"{record_id} self-generated outcome cannot enter feedback without external source")
            feedback.append({
                "recordId": record_id,
                "contentDigest": record["contentDigest"],
                "evidenceDigest": record["evidenceDigest"],
                "domain": domain,
                "objective": objective,
            })

    for edge in correction_edges + provenance_edges:
        if edge.get("targetRef") not in by_id:
            raise LearningSpineError(f"relation target is missing: {edge.get('targetRef')}")
    contradictions = [
        {"claimKey": key, "recordRefs": sorted(value), "status": "unresolved"}
        for key, value in sorted(contradiction_map.items())
    ]
    corrected_targets = {edge["targetRef"] for edge in correction_edges}
    records_index = []
    for record_id, record in sorted(by_id.items()):
        records_index.append({
            "recordId": record_id,
            "recordKind": record["recordKind"],
            "contentDigest": record["contentDigest"],
            "evidenceDigest": record["evidenceDigest"],
            "visibility": record["visibility"],
            "retentionClass": record["retentionClass"],
            "retentionSeconds": RETENTION[record["retentionClass"]],
            "corrected": record_id in corrected_targets,
            "narrativeSeparated": record.get("narrativeSummary") is not None,
        })
    return {
        "apiVersion": API_VERSION,
        "kind": "LearningSpineIntegrityReceipt",
        "batchId": spine["batchId"],
        "mindId": spine["mindId"],
        "batchDigest": digest(spine),
        "recordsIndex": records_index,
        "episodicIndex": [{"episodeKey": key, "recordRefs": sorted(value)} for key, value in sorted(episodic.items())],
        "semanticIndex": [{"tag": key, "recordRefs": sorted(value)} for key, value in sorted(semantic.items())],
        "correctionEdges": sorted(correction_edges, key=lambda item: (item["targetRef"], item["correctionRef"])),
        "provenanceEdges": sorted(provenance_edges, key=lambda item: (item["targetRef"], item["sourceRef"])),
        "contradictions": contradictions,
        "feedbackManifest": {"verifiedOutcomeRecords": sorted(feedback, key=lambda item: item["recordId"]), "trainingApplied": False},
        "checks": [
            {"name": "append-only-history", "status": "pass"},
            {"name": "episodic-index-closed", "status": "pass"},
            {"name": "semantic-index-closed", "status": "pass"},
            {"name": "evidence-narrative-separated", "status": "pass"},
            {"name": "retention-policy-bound", "status": "pass"},
            {"name": "contradictions-preserved", "status": "pass"},
            {"name": "corrections-preserve-history", "status": "pass"},
            {"name": "feedback-verified-only", "status": "pass"},
            {"name": "blind-self-training-forbidden", "status": "pass"},
        ],
        "authority": {
            "canonicalMutationApplied": False,
            "historyErasureApplied": False,
            "trainingApplied": False,
            "authorityMutationApplied": False,
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--out-receipt", type=Path, required=True)
    args = parser.parse_args()
    try:
        receipt = close_spine(load_json_strict(args.batch))
        args.out_receipt.parent.mkdir(parents=True, exist_ok=True)
        args.out_receipt.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
        print(len(receipt["recordsIndex"]))
        return 0
    except (OSError, json.JSONDecodeError, LearningSpineError) as exc:
        print(f"learning spine closure failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
