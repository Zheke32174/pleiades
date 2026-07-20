#!/usr/bin/env python3
from __future__ import annotations

import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("pleiades_executive_authority", HERE / "executive.py")
assert SPEC and SPEC.loader
executive = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = executive
SPEC.loader.exec_module(executive)


def load(name: str):
    with (HERE / "fixtures" / name).open(encoding="utf-8") as handle:
        return json.load(handle)


class ExecutiveAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.grant = load("delegated-authority-grant.json")
        self.decision = load("executive-decision.json")
        self.mandate = load("admission-mandate.json")

    def authorize(self, grant=None, decision=None, mandate=None):
        return executive.authorize(
            grant or self.grant,
            decision or self.decision,
            mandate or self.mandate,
        )

    def test_delegated_mind_can_authorize_bounded_admission(self):
        receipt = self.authorize()
        self.assertEqual(receipt["status"], "authorized")
        self.assertEqual(receipt["authority"]["decisionPrincipal"], "delegated-mind")
        self.assertEqual(receipt["authority"]["executorDecisionAuthority"], "none")
        self.assertTrue(receipt["authority"]["executionStillPending"])

    def test_domain_outside_grant_is_blocked(self):
        decision = copy.deepcopy(self.decision)
        decision["classification"]["domain"] = "constitution"
        mandate = copy.deepcopy(self.mandate)
        mandate["decisionDigest"] = executive.digest(decision)
        receipt = self.authorize(decision=decision, mandate=mandate)
        self.assertEqual(receipt["status"], "blocked")
        self.assertIn("domain-covered", [check["name"] for check in receipt["checks"] if check["status"] == "blocked"])

    def test_risk_above_grant_ceiling_is_blocked(self):
        decision = copy.deepcopy(self.decision)
        decision["classification"]["riskTier"] = "high-impact"
        mandate = copy.deepcopy(self.mandate)
        mandate["decisionDigest"] = executive.digest(decision)
        receipt = self.authorize(decision=decision, mandate=mandate)
        self.assertEqual(receipt["status"], "blocked")
        self.assertIn("risk-within-ceiling", [check["name"] for check in receipt["checks"] if check["status"] == "blocked"])

    def test_constitutional_machine_only_decision_is_forbidden(self):
        decision = copy.deepcopy(self.decision)
        decision["classification"]["riskTier"] = "constitutional"
        with self.assertRaisesRegex(executive.ExecutiveAuthorityError, "constitutional"):
            self.authorize(decision=decision)

    def test_grant_cannot_allow_self_expansion(self):
        grant = copy.deepcopy(self.grant)
        grant["delegation"]["maySelfExpand"] = True
        with self.assertRaisesRegex(executive.ExecutiveAuthorityError, "self-expansion"):
            self.authorize(grant=grant)

    def test_decision_requires_distinct_polycentric_principals(self):
        decision = copy.deepcopy(self.decision)
        for contribution in decision["deliberation"]["contributions"]:
            contribution["principalRef"] = "agent:one-model"
        with self.assertRaisesRegex(executive.ExecutiveAuthorityError, "distinct principals"):
            self.authorize(decision=decision)

    def test_dissent_must_be_preserved(self):
        decision = copy.deepcopy(self.decision)
        decision["deliberation"]["dissentPreserved"] = False
        with self.assertRaisesRegex(executive.ExecutiveAuthorityError, "preserve dissent"):
            self.authorize(decision=decision)

    def test_executor_cannot_acquire_decision_authority(self):
        mandate = copy.deepcopy(self.mandate)
        mandate["executor"]["decisionAuthority"] = "approve"
        with self.assertRaisesRegex(executive.ExecutiveAuthorityError, "no decision authority"):
            self.authorize(mandate=mandate)

    def test_target_mismatch_is_blocked(self):
        mandate = copy.deepcopy(self.mandate)
        mandate["stateTransition"]["targetDigest"] = "sha256:" + "9" * 64
        receipt = self.authorize(mandate=mandate)
        self.assertEqual(receipt["status"], "blocked")
        self.assertIn("target-bound", [check["name"] for check in receipt["checks"] if check["status"] == "blocked"])

    def test_rejected_decision_cannot_authorize_execution(self):
        decision = copy.deepcopy(self.decision)
        decision["decision"] = "reject"
        mandate = copy.deepcopy(self.mandate)
        mandate["decisionDigest"] = executive.digest(decision)
        receipt = self.authorize(decision=decision, mandate=mandate)
        self.assertEqual(receipt["status"], "blocked")
        self.assertIn("decision-approved", [check["name"] for check in receipt["checks"] if check["status"] == "blocked"])

    def test_exact_authorization_matches_golden_receipt(self):
        receipt = self.authorize()
        self.assertEqual(
            executive.canonical_bytes(receipt),
            executive.canonical_bytes(load("expected-executive-authorization-receipt.json")),
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
