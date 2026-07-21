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

import preflight  # noqa: E402
from common import TrustError, canonical_bytes  # noqa: E402


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


class TransitionPreflightTests(unittest.TestCase):
    def setUp(self):
        self.registry = load(HERE / "fixtures" / "operational-authority-registry.synthetic.json")
        self.candidate = load(HERE / "fixtures" / "transition-authorization-candidate.synthetic.json")
        self.compilation = load(ROOT / "modos" / "handoff" / "fixtures" / "expected-operator-input-compilation-receipt.json")
        self.trust = load(HERE / "fixtures" / "expected-operator-evidence-trust-receipt.json")
        self.grant = load(ROOT / "modos" / "governance" / "fixtures" / "delegated-authority-grant.json")
        self.expected = load(HERE / "fixtures" / "expected-transition-preflight-receipt.json")
        self.registry_schema = load(ROOT / "modos" / "contracts" / "operational-authority-registry.schema.json")
        self.candidate_schema = load(ROOT / "modos" / "contracts" / "transition-authorization-candidate.schema.json")
        self.trust_schema = load(ROOT / "modos" / "contracts" / "operator-evidence-trust-receipt.schema.json")
        self.grant_schema = load(ROOT / "modos" / "contracts" / "delegated-authority-grant.schema.json")
        self.receipt_schema = load(ROOT / "modos" / "contracts" / "transition-preflight-receipt.schema.json")

    def evaluate(self, registry=None, candidate=None, compilation=None, trust=None, grant=None, evaluated_at="2026-07-20T23:30:00Z"):
        return preflight.evaluate_preflight(
            registry or self.registry,
            candidate or self.candidate,
            compilation or self.compilation,
            trust or self.trust,
            grant or self.grant,
            evaluated_at,
            registry_schema=self.registry_schema,
            candidate_schema=self.candidate_schema,
            trust_schema=self.trust_schema,
            grant_schema=self.grant_schema,
            receipt_schema=self.receipt_schema,
        )

    def test_golden_preflight_receipt(self):
        self.assertEqual(canonical_bytes(self.evaluate()), canonical_bytes(self.expected))

    def test_preflight_is_deterministic(self):
        self.assertEqual(canonical_bytes(self.evaluate()), canonical_bytes(self.evaluate()))

    def test_result_never_constructs_or_executes_mandate(self):
        receipt = self.evaluate()
        self.assertEqual(receipt["status"], "eligible-for-mandate-construction")
        self.assertFalse(receipt["authority"]["mandateConstructed"])
        self.assertFalse(receipt["authority"]["authorizationApplied"])
        self.assertFalse(receipt["authority"]["executionApplied"])

    def test_missing_machine_approval_blocks(self):
        candidate = copy.deepcopy(self.candidate)
        candidate["approvals"] = [row for row in candidate["approvals"] if row["principalRef"] != "mind:pleiades"]
        receipt = self.evaluate(candidate=candidate)
        self.assertEqual(receipt["status"], "blocked")
        self.assertIn("required-role-quorum-unsatisfied:machine-executive", receipt["blockers"])

    def test_missing_independent_audit_blocks(self):
        candidate = copy.deepcopy(self.candidate)
        candidate["approvals"] = [row for row in candidate["approvals"] if row["position"] != "audit"]
        receipt = self.evaluate(candidate=candidate)
        self.assertEqual(receipt["status"], "blocked")
        self.assertIn("independent-audit-quorum-unsatisfied", receipt["blockers"])

    def test_effective_approval_principal_revocation_is_rejected(self):
        registry = copy.deepcopy(self.registry)
        registry["revocations"].append({
            "revocationId": "revocation:synthetic-mind",
            "targetType": "principal",
            "targetRef": "mind:pleiades",
            "effectiveAt": "2026-07-20T23:29:00Z",
            "reasonDigest": "sha256:" + "f" * 64,
        })
        with self.assertRaisesRegex(TrustError, "approval trust is revoked"):
            self.evaluate(registry=registry)

    def test_effective_grant_revocation_blocks(self):
        registry = copy.deepcopy(self.registry)
        registry["revocations"].append({
            "revocationId": "revocation:synthetic-grant",
            "targetType": "grant",
            "targetRef": self.grant["grantId"],
            "effectiveAt": "2026-07-20T23:29:00Z",
            "reasonDigest": "sha256:" + "e" * 64,
        })
        receipt = self.evaluate(registry=registry)
        self.assertEqual(receipt["status"], "blocked")
        self.assertIn("delegated-grant-revoked:revocation:synthetic-grant", receipt["blockers"])

    def test_inactive_executor_is_rejected(self):
        registry = copy.deepcopy(self.registry)
        for principal in registry["principals"]:
            if principal["principalRef"] == self.candidate["executorRef"]:
                principal["status"] = "suspended"
        with self.assertRaisesRegex(TrustError, "executor is not an active"):
            self.evaluate(registry=registry)

    def test_executor_capability_removed_is_rejected(self):
        registry = copy.deepcopy(self.registry)
        for principal in registry["principals"]:
            if principal["principalRef"] == self.candidate["executorRef"]:
                principal["executorCapabilities"] = []
        with self.assertRaisesRegex(TrustError, "lacks the exact required capability"):
            self.evaluate(registry=registry)

    def test_policy_quorum_increase_blocks(self):
        registry = copy.deepcopy(self.registry)
        registry["decisionPolicies"][0]["requiredRoleApprovals"]["machine-executive"] = 2
        receipt = self.evaluate(registry=registry)
        self.assertEqual(receipt["status"], "blocked")
        self.assertIn("required-role-quorum-unsatisfied:machine-executive", receipt["blockers"])

    def test_duplicate_approval_id_is_rejected(self):
        candidate = copy.deepcopy(self.candidate)
        candidate["approvals"].append(copy.deepcopy(candidate["approvals"][0]))
        with self.assertRaisesRegex(TrustError, "duplicate approvalId"):
            self.evaluate(candidate=candidate)

    def test_principal_cannot_contribute_twice(self):
        candidate = copy.deepcopy(self.candidate)
        duplicate = copy.deepcopy(candidate["approvals"][0])
        duplicate["approvalId"] = "approval:synthetic-steward:v2"
        duplicate["nonce"] = "d" * 64
        candidate["approvals"].append(duplicate)
        with self.assertRaisesRegex(TrustError, "principal contributed more than once"):
            self.evaluate(candidate=candidate)

    def test_tampered_approval_signature_is_rejected(self):
        candidate = copy.deepcopy(self.candidate)
        candidate["approvals"][0]["signatureBase64"] = "A" * 86 + "=="
        with self.assertRaisesRegex(TrustError, "approval signature is invalid"):
            self.evaluate(candidate=candidate)

    def test_expired_grant_blocks(self):
        receipt = self.evaluate(evaluated_at="2027-07-21T00:00:00Z")
        self.assertEqual(receipt["status"], "blocked")
        self.assertIn("delegated-grant-outside-validity", receipt["blockers"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
