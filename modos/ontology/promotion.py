#!/usr/bin/env python3
"""Deterministic, non-authoritative ontology promotion evidence gate.

This module verifies that a candidate snapshot, closure receipt, source manifest,
and promotion candidate are bound to the same immutable evidence set. It emits a
gate report only. It cannot sign, approve, admit, deploy, or mutate canonical
state.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable

try:
    from . import compiler
except ImportError:  # direct script execution
    import compiler  # type: ignore

API_VERSION = "modos.pleiades/v1alpha1"
DIGEST_RE = re.compile(r"^sha256:(?!0{64}$)[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")


class PromotionEvidenceError(ValueError):
    """Raised when immutable promotion evidence is inconsistent or malformed."""


def _reject_float(value: str) -> None:
    raise PromotionEvidenceError(f"floating-point values are forbidden: {value}")


def _reject_constant(value: str) -> None:
    raise PromotionEvidenceError(f"non-finite JSON constant is forbidden: {value}")


def _no_duplicate_keys(pairs: Iterable[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise PromotionEvidenceError(f"duplicate JSON key is forbidden: {key}")
        result[key] = value
    return result


def load_json_strict(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(
            handle,
            parse_float=_reject_float,
            parse_constant=_reject_constant,
            object_pairs_hook=_no_duplicate_keys,
        )


def canonical_bytes(value: Any) -> bytes:
    return compiler.canonical_bytes(value)


def digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_bytes(value)).hexdigest()


def _require_digest(value: Any, field: str) -> str:
    if not isinstance(value, str) or not DIGEST_RE.fullmatch(value):
        raise PromotionEvidenceError(f"{field} must be a non-placeholder lowercase sha256 digest")
    return value


def _require_exact_authority(value: Any, expected: dict[str, Any], field: str) -> None:
    if value != expected:
        raise PromotionEvidenceError(f"{field} authority boundary is not exact")


def _validate_source_manifest(manifest: dict[str, Any]) -> None:
    if manifest.get("apiVersion") != API_VERSION or manifest.get("kind") != "OntologySourceManifest":
        raise PromotionEvidenceError("unsupported source manifest envelope")
    if not COMMIT_RE.fullmatch(str(manifest.get("commitSha", ""))):
        raise PromotionEvidenceError("source manifest commitSha must be an exact lowercase Git SHA")
    _require_exact_authority(
        manifest.get("authority"),
        {"ceiling": "none", "pathAuthority": "evidence-only", "selfPromotionAllowed": False},
        "source manifest",
    )
    subject = manifest.get("subject")
    if not isinstance(subject, dict):
        raise PromotionEvidenceError("source manifest subject is required")
    for field in ("sourceSnapshotDigest", "candidateSnapshotDigest", "closureReceiptDigest"):
        _require_digest(subject.get(field), f"source manifest subject.{field}")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise PromotionEvidenceError("source manifest artifacts must be a nonempty array")
    identities: set[str] = set()
    locators: set[str] = set()
    roles: set[str] = set()
    for index, artifact in enumerate(artifacts):
        if not isinstance(artifact, dict):
            raise PromotionEvidenceError(f"source artifact {index} must be an object")
        artifact_id = artifact.get("artifactId")
        locator = artifact.get("locator")
        role = artifact.get("role")
        if not isinstance(artifact_id, str) or not artifact_id:
            raise PromotionEvidenceError(f"source artifact {index} artifactId is required")
        if artifact_id in identities:
            raise PromotionEvidenceError(f"duplicate source artifact id: {artifact_id}")
        identities.add(artifact_id)
        if not isinstance(locator, str) or not locator:
            raise PromotionEvidenceError(f"source artifact {index} locator is required")
        if locator in locators:
            raise PromotionEvidenceError(f"duplicate source artifact locator: {locator}")
        locators.add(locator)
        if not isinstance(role, str) or not role:
            raise PromotionEvidenceError(f"source artifact {index} role is required")
        roles.add(role)
        _require_digest(artifact.get("digest"), f"source artifact {artifact_id}.digest")
        if not isinstance(artifact.get("bytes"), int) or isinstance(artifact.get("bytes"), bool) or artifact["bytes"] < 1:
            raise PromotionEvidenceError(f"source artifact {artifact_id}.bytes must be positive")
    required_roles = {"source-snapshot", "change-proposal", "candidate-snapshot", "closure-receipt", "compiler", "contract"}
    missing = sorted(required_roles - roles)
    if missing:
        raise PromotionEvidenceError(f"source manifest is missing required artifact roles: {', '.join(missing)}")


def _validate_candidate(candidate: dict[str, Any]) -> None:
    if candidate.get("apiVersion") != API_VERSION or candidate.get("kind") != "OntologyPromotionCandidate":
        raise PromotionEvidenceError("unsupported promotion candidate envelope")
    if not COMMIT_RE.fullmatch(str(candidate.get("commitSha", ""))):
        raise PromotionEvidenceError("promotion candidate commitSha must be an exact lowercase Git SHA")
    for field in (
        "sourceSnapshotDigest",
        "candidateSnapshotDigest",
        "closureReceiptDigest",
        "sourceManifestDigest",
        "semanticDiffDigest",
    ):
        _require_digest(candidate.get(field), f"promotion candidate {field}")
    evidence = candidate.get("evidenceRefs")
    if not isinstance(evidence, list) or len(evidence) < 2 or len(set(evidence)) != len(evidence):
        raise PromotionEvidenceError("promotion candidate requires at least two unique evidenceRefs")
    governance = candidate.get("governanceEvidence")
    if not isinstance(governance, list) or not governance:
        raise PromotionEvidenceError("promotion candidate governanceEvidence must be nonempty")
    governance_identities: set[tuple[str, str]] = set()
    for index, evidence_item in enumerate(governance):
        if not isinstance(evidence_item, dict):
            raise PromotionEvidenceError(f"governance evidence {index} must be an object")
        evidence_type = evidence_item.get("type")
        locator = evidence_item.get("locator")
        identity = (str(evidence_type), str(locator))
        if identity in governance_identities:
            raise PromotionEvidenceError(f"duplicate governance evidence: {evidence_type} {locator}")
        governance_identities.add(identity)
        _require_digest(evidence_item.get("digest"), f"governance evidence {index}.digest")
    blockers = candidate.get("blockingIssues")
    if not isinstance(blockers, list) or len(set(blockers)) != len(blockers):
        raise PromotionEvidenceError("promotion candidate blockingIssues must be a unique array")
    review_policy = candidate.get("reviewPolicy")
    if not isinstance(review_policy, dict) or review_policy.get("requiredApprovals", 0) < 1:
        raise PromotionEvidenceError("promotion candidate reviewPolicy requires at least one approval")
    for flag in ("codeownersRequired", "rulesetReviewRequired", "signedPromotionTransactionRequired"):
        if review_policy.get(flag) is not True:
            raise PromotionEvidenceError(f"promotion candidate reviewPolicy.{flag} must be true")
    if not isinstance(review_policy.get("artifactAttestationRequired"), bool):
        raise PromotionEvidenceError("promotion candidate reviewPolicy.artifactAttestationRequired must be boolean")
    _require_exact_authority(
        candidate.get("authority"),
        {
            "ceiling": "none",
            "canonicalMutation": "forbidden",
            "admissionExecutor": "external-steward",
            "selfAdmissionAllowed": False,
        },
        "promotion candidate",
    )


def evaluate_promotion_candidate(
    snapshot: dict[str, Any],
    receipt: dict[str, Any],
    manifest: dict[str, Any],
    candidate: dict[str, Any],
) -> dict[str, Any]:
    """Return a deterministic gate report without applying promotion authority."""
    snapshot = compiler.normalize_snapshot(snapshot)
    receipt = copy.deepcopy(receipt)
    manifest = copy.deepcopy(manifest)
    candidate = copy.deepcopy(candidate)
    _validate_source_manifest(manifest)
    _validate_candidate(candidate)

    snapshot_digest = compiler.snapshot_digest(snapshot)
    receipt_digest = digest(receipt)
    manifest_digest = digest(manifest)
    semantic_diff = receipt.get("semanticDiff")
    if not isinstance(semantic_diff, dict):
        raise PromotionEvidenceError("closure receipt semanticDiff is required")
    semantic_diff_digest = digest(semantic_diff)

    if receipt.get("apiVersion") != API_VERSION or receipt.get("kind") != "OntologyClosureReceipt":
        raise PromotionEvidenceError("unsupported closure receipt envelope")
    if receipt.get("closureStatus") != "closed":
        raise PromotionEvidenceError("closure receipt must be closed")
    checks = receipt.get("checks")
    if not isinstance(checks, list) or not checks or any(check.get("status") != "pass" for check in checks):
        raise PromotionEvidenceError("every closure receipt check must pass")
    _require_exact_authority(
        receipt.get("authority"),
        {
            "ceiling": "none",
            "canonicalMutationApplied": False,
            "promotionTransactionRequired": True,
            "promotionState": "eligible-for-review",
        },
        "closure receipt",
    )

    exact_bindings = {
        "repository": candidate["repository"],
        "branch": candidate["branch"],
        "commitSha": candidate["commitSha"],
        "mindId": candidate["mindId"],
        "schemaVersion": candidate["schemaVersion"],
        "sourceSnapshotDigest": candidate["sourceSnapshotDigest"],
        "candidateSnapshotDigest": candidate["candidateSnapshotDigest"],
        "closureReceiptDigest": candidate["closureReceiptDigest"],
        "sourceManifestDigest": candidate["sourceManifestDigest"],
        "semanticDiffDigest": candidate["semanticDiffDigest"],
    }

    comparisons = {
        "candidate-snapshot-digest-bound": snapshot_digest == candidate["candidateSnapshotDigest"] == receipt.get("resultSnapshotDigest") == manifest["subject"]["candidateSnapshotDigest"],
        "source-snapshot-digest-bound": candidate["sourceSnapshotDigest"] == receipt.get("sourceSnapshotDigest") == manifest["subject"]["sourceSnapshotDigest"],
        "closure-receipt-digest-bound": receipt_digest == candidate["closureReceiptDigest"] == manifest["subject"]["closureReceiptDigest"],
        "source-manifest-digest-bound": manifest_digest == candidate["sourceManifestDigest"],
        "semantic-diff-digest-bound": semantic_diff_digest == candidate["semanticDiffDigest"],
        "repository-branch-commit-bound": (
            candidate["repository"] == manifest["repository"]
            and candidate["branch"] == manifest["branch"]
            and candidate["commitSha"] == manifest["commitSha"]
        ),
        "mind-schema-bound": (
            candidate["mindId"] == manifest["mindId"] == receipt.get("mindId") == snapshot.get("mindId")
            and candidate["schemaVersion"] == manifest["schemaVersion"] == receipt.get("schemaVersion") == snapshot.get("schemaVersion")
        ),
        "codeowners-evidence-present": any(
            evidence.get("type") == "codeowners" and evidence.get("locator") == ".github/CODEOWNERS"
            for evidence in candidate["governanceEvidence"]
        ),
        "no-unresolved-blocking-issues": not candidate["blockingIssues"],
    }

    failed = [name for name, passed in comparisons.items() if not passed]
    hard_binding_failures = [name for name in failed if name != "no-unresolved-blocking-issues"]
    if hard_binding_failures:
        raise PromotionEvidenceError("promotion evidence binding failed: " + ", ".join(hard_binding_failures))

    blockers = sorted(candidate["blockingIssues"])
    status = "blocked" if blockers else "eligible-for-steward-review"
    gate_checks = []
    for name, passed in comparisons.items():
        gate_checks.append(
            {
                "name": name,
                "status": "pass" if passed else "blocked",
                **({"detail": "; ".join(blockers)} if name == "no-unresolved-blocking-issues" and blockers else {}),
            }
        )
    gate_checks.extend(
        [
            {"name": "closure-receipt-closed", "status": "pass"},
            {"name": "all-closure-checks-pass", "status": "pass"},
            {"name": "authority-remains-none", "status": "pass"},
            {"name": "signed-promotion-transaction-still-required", "status": "pass"},
        ]
    )
    return {
        "apiVersion": API_VERSION,
        "kind": "OntologyPromotionGateReport",
        "candidateId": candidate["candidateId"],
        "status": status,
        "bindings": exact_bindings,
        "checks": gate_checks,
        "blockers": blockers,
        "authority": {
            "ceiling": "none",
            "canonicalMutationApplied": False,
            "promotionTransactionRequired": True,
        },
    }


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--out-report", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = evaluate_promotion_candidate(
            load_json_strict(args.snapshot),
            load_json_strict(args.receipt),
            load_json_strict(args.manifest),
            load_json_strict(args.candidate),
        )
        _write_json(args.out_report, report)
        print(report["status"])
        return 0
    except (OSError, json.JSONDecodeError, compiler.OntologyCompileError, PromotionEvidenceError) as exc:
        print(f"promotion evidence validation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
