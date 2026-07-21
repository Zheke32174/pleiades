#!/usr/bin/env python3
"""Verify operator evidence authenticity, scope, freshness, and revocation.

The verifier establishes trust in opaque references. It does not authorize a
decision, issue a grant, construct a mandate, contact a node, or mutate state.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from datetime import timedelta
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from jsonschema import Draft202012Validator, FormatChecker

try:
    from .common import TrustError, canonical_bytes, decode_base64, digest, load, parse_time
except ImportError:
    from common import TrustError, canonical_bytes, decode_base64, digest, load, parse_time  # type: ignore

API_VERSION = "modos.pleiades/v1alpha1"
AUTHORITY = {"ceiling": "none", "trustEvaluationOnly": True, "authorizationApplied": False, "executionApplied": False, "registryMutationApplied": False}


def validate_schema(value: Any, schema: dict[str, Any], label: str) -> None:
    Draft202012Validator.check_schema(schema)
    errors = sorted(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(value), key=lambda error: list(error.absolute_path))
    if errors:
        rendered = "; ".join(("/".join(map(str, error.absolute_path)) or "$") + ": " + error.message for error in errors)
        raise TrustError(f"{label} schema validation failed: {rendered}")


def validate_registry(registry: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    if registry.get("apiVersion") != API_VERSION or registry.get("kind") != "OperationalAuthorityRegistry":
        raise TrustError("unsupported operational authority registry")
    if registry.get("authority") != {"ceiling": "none", "closureOnly": True, "mayIssueAuthority": False, "mayExecute": False, "maySelfModify": False}:
        raise TrustError("operational authority registry boundary is not exact")

    principals: dict[str, Any] = {}
    for principal in registry.get("principals", []):
        ref = principal["principalRef"]
        if ref in principals:
            raise TrustError(f"duplicate principalRef: {ref}")
        if len(set(principal["roles"])) != len(principal["roles"]):
            raise TrustError(f"principal roles must be unique: {ref}")
        for field in ("evidenceInputs", "decisionTypes", "executorCapabilities", "conflictDomains"):
            if len(set(principal[field])) != len(principal[field]):
                raise TrustError(f"principal {field} must be unique: {ref}")
        principals[ref] = principal

    keys: dict[str, Any] = {}
    for key in registry.get("keys", []):
        ref = key["keyRef"]
        if ref in keys:
            raise TrustError(f"duplicate keyRef: {ref}")
        if key["principalRef"] not in principals:
            raise TrustError(f"key principal does not resolve: {ref}")
        if parse_time(key["validFrom"], f"{ref}.validFrom") >= parse_time(key["validUntil"], f"{ref}.validUntil"):
            raise TrustError(f"key validity ordering is invalid: {ref}")
        raw = decode_base64(key["publicKeyBase64"], f"{ref}.publicKeyBase64", 32)
        if "sha256:" + hashlib.sha256(raw).hexdigest() != key["publicKeyDigest"]:
            raise TrustError(f"public key digest mismatch: {ref}")
        keys[ref] = key

    policies: dict[str, Any] = {}
    for policy in registry.get("evidencePolicies", []):
        input_id = policy["inputId"]
        if input_id in policies:
            raise TrustError(f"duplicate evidence policy: {input_id}")
        policies[input_id] = policy

    decision_keys: set[tuple[str, str, str, str]] = set()
    for policy in registry.get("decisionPolicies", []):
        for domain in policy["domains"]:
            for action in policy["actions"]:
                for risk in policy["riskTiers"]:
                    key = (policy["decisionType"], domain, action, risk)
                    if key in decision_keys:
                        raise TrustError(f"overlapping decision policy: {key}")
                    decision_keys.add(key)

    revocation_ids: set[str] = set()
    for row in registry.get("revocations", []):
        if row["revocationId"] in revocation_ids:
            raise TrustError(f"duplicate revocationId: {row['revocationId']}")
        revocation_ids.add(row["revocationId"])
        parse_time(row["effectiveAt"], f"{row['revocationId']}.effectiveAt")
    return principals, keys, policies


def is_revoked(registry: dict[str, Any], evaluated_at, *, attestation_id: str, principal_ref: str, key_ref: str) -> str | None:
    for row in registry["revocations"]:
        if parse_time(row["effectiveAt"], f"{row['revocationId']}.effectiveAt") > evaluated_at:
            continue
        if (row["targetType"], row["targetRef"]) in {("attestation", attestation_id), ("principal", principal_ref), ("key", key_ref)}:
            return row["revocationId"]
    return None


def verify_attestations(candidate: dict[str, Any], registry: dict[str, Any], attestations: list[dict[str, Any]], evaluated_at: str, *, candidate_schema: dict[str, Any] | None = None, registry_schema: dict[str, Any] | None = None, attestation_schema: dict[str, Any] | None = None, receipt_schema: dict[str, Any] | None = None) -> dict[str, Any]:
    if candidate_schema is not None:
        validate_schema(candidate, candidate_schema, "operator candidate")
    if registry_schema is not None:
        validate_schema(registry, registry_schema, "operational authority registry")
    principals, keys, policies = validate_registry(registry)
    evaluated = parse_time(evaluated_at, "evaluatedAt")
    candidate_digest = digest(candidate)

    supplied = {input_id: row for input_id, row in candidate["inputs"].items() if row["supplied"] is True}
    attestation_ids: set[str] = set()
    nonces: set[str] = set()
    by_input: dict[str, list[dict[str, Any]]] = {}
    for row in attestations:
        if attestation_schema is not None:
            validate_schema(row, attestation_schema, f"attestation {row.get('attestationId', '<unknown>')}")
        if row["attestationId"] in attestation_ids:
            raise TrustError(f"duplicate attestationId: {row['attestationId']}")
        if row["nonce"] in nonces:
            raise TrustError(f"duplicate attestation nonce: {row['nonce']}")
        attestation_ids.add(row["attestationId"])
        nonces.add(row["nonce"])
        by_input.setdefault(row["inputId"], []).append(row)

    extra_inputs = sorted(set(by_input) - set(supplied))
    if extra_inputs:
        raise TrustError("attestations supplied for absent inputs: " + ", ".join(extra_inputs))

    trusted: list[dict[str, Any]] = []
    blockers: list[str] = []
    for input_id, input_row in sorted(supplied.items()):
        policy = policies.get(input_id)
        if policy is None:
            raise TrustError(f"no evidence policy for supplied input: {input_id}")
        rows = by_input.get(input_id, [])
        if len(rows) < policy["requiredDistinctAttestors"]:
            blockers.append(f"attestation-count-unsatisfied:{input_id}")
            continue

        distinct_issuers: set[str] = set()
        for row in sorted(rows, key=lambda item: item["attestationId"]):
            if row["candidateDigest"] != candidate_digest:
                raise TrustError(f"attestation candidate binding failed: {row['attestationId']}")
            for field in ("classification", "artifactRef", "artifactDigest", "receiptDigest"):
                if row[field] != input_row[field]:
                    raise TrustError(f"attestation {field} binding failed: {row['attestationId']}")

            principal = principals.get(row["issuerRef"])
            if principal is None or principal["status"] != "active":
                raise TrustError(f"attestation issuer is not active: {row['issuerRef']}")
            if input_id not in principal["evidenceInputs"]:
                raise TrustError(f"issuer is not scoped to input {input_id}: {row['issuerRef']}")
            if not set(principal["roles"]).intersection(policy["allowedIssuerRoles"]):
                raise TrustError(f"issuer role is not allowed for input {input_id}: {row['issuerRef']}")
            if row["classification"] not in policy["allowedClassifications"]:
                raise TrustError(f"classification is not allowed for input {input_id}")

            key = keys.get(row["keyRef"])
            if key is None or key["principalRef"] != row["issuerRef"]:
                raise TrustError(f"attestation key does not belong to issuer: {row['attestationId']}")
            if key["status"] != "active":
                raise TrustError(f"attestation key is not active: {row['keyRef']}")
            if key["algorithm"] != row["algorithm"] or row["algorithm"] != "Ed25519":
                raise TrustError(f"attestation algorithm mismatch: {row['attestationId']}")

            issued = parse_time(row["issuedAt"], f"{row['attestationId']}.issuedAt")
            expires = parse_time(row["expiresAt"], f"{row['attestationId']}.expiresAt")
            key_start = parse_time(key["validFrom"], f"{key['keyRef']}.validFrom")
            key_end = parse_time(key["validUntil"], f"{key['keyRef']}.validUntil")
            skew = timedelta(seconds=policy["allowedClockSkewSeconds"])
            if issued > evaluated + skew:
                raise TrustError(f"attestation is future-dated: {row['attestationId']}")
            if not issued < expires:
                raise TrustError(f"attestation validity ordering is invalid: {row['attestationId']}")
            if not key_start <= issued < key_end:
                raise TrustError(f"attestation was signed outside key validity: {row['attestationId']}")
            if evaluated >= expires:
                raise TrustError(f"attestation is expired: {row['attestationId']}")
            age_seconds = max(0, int((evaluated - issued).total_seconds()))
            if age_seconds > policy["maximumAgeSeconds"]:
                raise TrustError(f"attestation is stale: {row['attestationId']}")

            revocation = is_revoked(registry, evaluated, attestation_id=row["attestationId"], principal_ref=row["issuerRef"], key_ref=row["keyRef"])
            if revocation is not None:
                raise TrustError(f"attestation trust is revoked by {revocation}")

            public_key = decode_base64(key["publicKeyBase64"], f"{key['keyRef']}.publicKeyBase64", 32)
            signature = decode_base64(row["signatureBase64"], f"{row['attestationId']}.signatureBase64", 64)
            unsigned = copy.deepcopy(row)
            unsigned.pop("signatureBase64")
            try:
                Ed25519PublicKey.from_public_bytes(public_key).verify(signature, canonical_bytes(unsigned))
            except InvalidSignature as exc:
                raise TrustError(f"attestation signature is invalid: {row['attestationId']}") from exc

            distinct_issuers.add(row["issuerRef"])
            trusted.append({"inputId": input_id, "attestationId": row["attestationId"], "issuerRef": row["issuerRef"], "keyRef": row["keyRef"], "statementDigest": digest(unsigned), "issuedAt": row["issuedAt"], "expiresAt": row["expiresAt"], "ageSeconds": age_seconds, "status": "trusted"})
        if len(distinct_issuers) < policy["requiredDistinctAttestors"]:
            blockers.append(f"distinct-attestors-unsatisfied:{input_id}")

    state = "trusted" if not blockers else "blocked"
    checks = [
        {"name": "registry-closure", "status": "pass"},
        {"name": "candidate-binding", "status": "pass"},
        {"name": "issuer-scope", "status": "pass"},
        {"name": "key-integrity", "status": "pass"},
        {"name": "signature-verification", "status": "pass"},
        {"name": "freshness", "status": "pass"},
        {"name": "revocation", "status": "pass"},
        {"name": "attestation-completeness", "status": "pass" if not blockers else "blocked"},
    ]
    receipt: dict[str, Any] = {"apiVersion": API_VERSION, "kind": "OperatorEvidenceTrustReceipt", "candidateId": candidate["candidateId"], "candidateDigest": candidate_digest, "registryId": registry["registryId"], "registryDigest": digest(registry), "evaluatedAt": evaluated_at, "state": state, "trustedInputs": trusted, "blockedInputs": sorted(blockers), "trustedInputCount": len({row["inputId"] for row in trusted}), "requiredInputCount": len(supplied), "checks": checks, "authority": AUTHORITY}
    receipt["receiptDigest"] = digest(receipt)
    if receipt_schema is not None:
        validate_schema(receipt, receipt_schema, "operator evidence trust receipt")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--attestations", type=Path, required=True)
    parser.add_argument("--evaluated-at", required=True)
    parser.add_argument("--candidate-schema", type=Path, default=Path("modos/contracts/operator-input-candidate.schema.json"))
    parser.add_argument("--registry-schema", type=Path, default=Path("modos/contracts/operational-authority-registry.schema.json"))
    parser.add_argument("--attestation-schema", type=Path, default=Path("modos/contracts/evidence-attestation.schema.json"))
    parser.add_argument("--receipt-schema", type=Path, default=Path("modos/contracts/operator-evidence-trust-receipt.schema.json"))
    parser.add_argument("--report", type=Path, default=Path("artifacts/operator-evidence-trust-receipt.json"))
    args = parser.parse_args()
    try:
        rows = load(args.attestations)
        if not isinstance(rows, list):
            raise TrustError("attestations file must contain an array")
        receipt = verify_attestations(load(args.candidate), load(args.registry), rows, args.evaluated_at, candidate_schema=load(args.candidate_schema), registry_schema=load(args.registry_schema), attestation_schema=load(args.attestation_schema), receipt_schema=load(args.receipt_schema))
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"operator evidence trust {receipt['state']}: {receipt['receiptDigest']}")
        return 0 if receipt["state"] == "trusted" else 2
    except (OSError, json.JSONDecodeError, TrustError) as exc:
        print(f"operator evidence trust failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
