#!/usr/bin/env python3
"""Validate operational trust contracts, signatures, goldens, and preflight."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
TRUST = ROOT / "modos" / "trust"
sys.path.insert(0, str(TRUST))

import evidence  # noqa: E402
import preflight  # noqa: E402
from common import TrustError, canonical_bytes, load  # noqa: E402


def main() -> int:
    try:
        schemas = {
            name: load(ROOT / "modos" / "contracts" / name)
            for name in (
                "operational-authority-registry.schema.json",
                "evidence-attestation.schema.json",
                "operator-evidence-trust-receipt.schema.json",
                "transition-authorization-candidate.schema.json",
                "transition-preflight-receipt.schema.json",
            )
        }
        for schema in schemas.values():
            Draft202012Validator.check_schema(schema)

        candidate = load(ROOT / "modos" / "handoff" / "fixtures" / "operator-input-candidate.synthetic-ready.json")
        candidate_schema = load(ROOT / "modos" / "contracts" / "operator-input-candidate.schema.json")
        registry = load(TRUST / "fixtures" / "operational-authority-registry.synthetic.json")
        attestations = load(TRUST / "fixtures" / "evidence-attestations.synthetic.json")
        expected_trust = load(TRUST / "fixtures" / "expected-operator-evidence-trust-receipt.json")
        compilation = load(ROOT / "modos" / "handoff" / "fixtures" / "expected-operator-input-compilation-receipt.json")
        authorization = load(TRUST / "fixtures" / "transition-authorization-candidate.synthetic.json")
        expected_preflight = load(TRUST / "fixtures" / "expected-transition-preflight-receipt.json")
        grant = load(ROOT / "modos" / "governance" / "fixtures" / "delegated-authority-grant.json")
        grant_schema = load(ROOT / "modos" / "contracts" / "delegated-authority-grant.schema.json")

        trust = evidence.verify_attestations(
            candidate,
            registry,
            attestations,
            "2026-07-20T23:30:00Z",
            candidate_schema=candidate_schema,
            registry_schema=schemas["operational-authority-registry.schema.json"],
            attestation_schema=schemas["evidence-attestation.schema.json"],
            receipt_schema=schemas["operator-evidence-trust-receipt.schema.json"],
        )
        if canonical_bytes(trust) != canonical_bytes(expected_trust):
            raise TrustError("operator evidence trust golden receipt mismatch")
        if trust["state"] != "trusted" or trust["authority"] != evidence.AUTHORITY:
            raise TrustError("operator evidence trust boundary is not exact")

        receipt = preflight.evaluate_preflight(
            registry,
            authorization,
            compilation,
            trust,
            grant,
            "2026-07-20T23:30:00Z",
            registry_schema=schemas["operational-authority-registry.schema.json"],
            candidate_schema=schemas["transition-authorization-candidate.schema.json"],
            trust_schema=schemas["operator-evidence-trust-receipt.schema.json"],
            grant_schema=grant_schema,
            receipt_schema=schemas["transition-preflight-receipt.schema.json"],
        )
        if canonical_bytes(receipt) != canonical_bytes(expected_preflight):
            raise TrustError("transition preflight golden receipt mismatch")
        if receipt["status"] != "eligible-for-mandate-construction":
            raise TrustError("synthetic transition did not reach preflight eligibility")
        if receipt["authority"] != preflight.AUTHORITY:
            raise TrustError("transition preflight authority boundary is not exact")

        rendered = json.dumps(
            {"registry": registry, "attestations": attestations, "authorization": authorization},
            sort_keys=True,
        )
        forbidden = ("BEGIN PRIVATE KEY", "BEGIN OPENSSH PRIVATE KEY", "privateKeyBase64", "privateKeyPem")
        if any(token in rendered for token in forbidden):
            raise TrustError("trust fixtures contain private key material")

        print(
            "validated operational trust and transition preflight: "
            f"{trust['receiptDigest']} {receipt['receiptDigest']}"
        )
        return 0
    except (OSError, json.JSONDecodeError, TrustError) as exc:
        print(f"operational trust validation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
