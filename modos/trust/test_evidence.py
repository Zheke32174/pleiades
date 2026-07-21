#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

import evidence  # noqa: E402
from common import TrustError, canonical_bytes  # noqa: E402


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


class OperatorEvidenceTrustTests(unittest.TestCase):
    def setUp(self):
        self.candidate = load(ROOT / "modos" / "handoff" / "fixtures" / "operator-input-candidate.synthetic-ready.json")
        self.registry = load(HERE / "fixtures" / "operational-authority-registry.synthetic.json")
        self.attestations = load(HERE / "fixtures" / "evidence-attestations.synthetic.json")
        self.expected = load(HERE / "fixtures" / "expected-operator-evidence-trust-receipt.json")
        self.registry_schema = load(ROOT / "modos" / "contracts" / "operational-authority-registry.schema.json")
        self.attestation_schema = load(ROOT / "modos" / "contracts" / "evidence-attestation.schema.json")
        self.receipt_schema = load(ROOT / "modos" / "contracts" / "operator-evidence-trust-receipt.schema.json")

    def verify(self, candidate=None, registry=None, attestations=None, evaluated_at="2026-07-20T23:30:00Z"):
        return evidence.verify_attestations(
            candidate or self.candidate,
            registry or self.registry,
            self.attestations if attestations is None else attestations,
            evaluated_at,
            registry_schema=self.registry_schema,
            attestation_schema=self.attestation_schema,
            receipt_schema=self.receipt_schema,
        )

    def test_golden_trust_receipt(self):
        self.assertEqual(canonical_bytes(self.verify()), canonical_bytes(self.expected))

    def test_verification_is_deterministic(self):
        self.assertEqual(canonical_bytes(self.verify()), canonical_bytes(self.verify()))

    def test_missing_attestation_blocks_without_authorizing(self):
        receipt = self.verify(attestations=self.attestations[:-1])
        self.assertEqual(receipt["state"], "blocked")
        self.assertEqual(receipt["authority"]["ceiling"], "none")
        self.assertFalse(receipt["authority"]["authorizationApplied"])
        self.assertFalse(receipt["authority"]["executionApplied"])

    def test_tampered_signature_is_rejected(self):
        rows = copy.deepcopy(self.attestations)
        rows[0]["signatureBase64"] = "A" * 86 + "=="
        with self.assertRaisesRegex(TrustError, "signature is invalid"):
            self.verify(attestations=rows)

    def test_candidate_binding_mismatch_is_rejected(self):
        candidate = copy.deepcopy(self.candidate)
        candidate["candidateId"] = "operator-input-candidate:synthetic-ready-9999"
        with self.assertRaisesRegex(TrustError, "candidate binding failed"):
            self.verify(candidate=candidate)

    def test_wrong_issuer_scope_is_rejected(self):
        registry = copy.deepcopy(self.registry)
        for principal in registry["principals"]:
            if principal["principalRef"] == "service:synthetic-private-evidence":
                principal["evidenceInputs"].remove("privateEcology")
        with self.assertRaisesRegex(TrustError, "not scoped to input privateEcology"):
            self.verify(registry=registry)

    def test_expired_attestation_is_rejected(self):
        with self.assertRaisesRegex(TrustError, "expired"):
            self.verify(evaluated_at="2026-07-22T00:00:00Z")

    def test_effective_key_revocation_is_rejected(self):
        registry = copy.deepcopy(self.registry)
        registry["revocations"].append(
            {
                "revocationId": "revocation:synthetic-live-key",
                "targetType": "key",
                "targetRef": "key:synthetic-live-evidence-v1",
                "effectiveAt": "2026-07-20T23:29:00Z",
                "reasonDigest": "sha256:" + "f" * 64,
            }
        )
        with self.assertRaisesRegex(TrustError, "trust is revoked"):
            self.verify(registry=registry)

    def test_duplicate_nonce_is_rejected(self):
        rows = copy.deepcopy(self.attestations)
        duplicate = copy.deepcopy(rows[0])
        duplicate["attestationId"] = "attestation:synthetic:duplicate:v1"
        rows.append(duplicate)
        with self.assertRaisesRegex(TrustError, "duplicate attestation nonce"):
            self.verify(attestations=rows)

    def test_extra_input_attestation_is_rejected(self):
        rows = copy.deepcopy(self.attestations)
        extra = copy.deepcopy(rows[0])
        extra["attestationId"] = "attestation:synthetic:unknown:v1"
        extra["inputId"] = "unknownInput"
        extra["nonce"] = "f" * 64
        rows.append(extra)
        with self.assertRaisesRegex(TrustError, "absent inputs"):
            self.verify(attestations=rows)

    def test_public_key_digest_tamper_is_rejected(self):
        registry = copy.deepcopy(self.registry)
        registry["keys"][0]["publicKeyDigest"] = "sha256:" + "f" * 64
        with self.assertRaisesRegex(TrustError, "public key digest mismatch"):
            self.verify(registry=registry)


if __name__ == "__main__":
    unittest.main(verbosity=2)
