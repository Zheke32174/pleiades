#!/usr/bin/env python3
from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load_module(name: str):
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


judgment = load_module("judgment")
fixtures = load_module("judgment_fixtures")


class AdministrativeJudgmentTests(unittest.TestCase):
    def setUp(self):
        self.policy = copy.deepcopy(fixtures.POLICY_RECEIPT)
        self.workspace = copy.deepcopy(fixtures.WORKSPACE_RECEIPT)
        self.preflight = copy.deepcopy(fixtures.PREFLIGHT_RECEIPT)
        self.workspace["bindings"]["policyReceiptDigest"] = judgment.digest(self.policy)
        self.case = copy.deepcopy(fixtures.CASE)
        self.case["bindings"].update(
            {
                "policyReceiptDigest": judgment.digest(self.policy),
                "workspaceReceiptDigest": judgment.digest(self.workspace),
                "transitionPreflightReceiptDigest": judgment.digest(self.preflight),
            }
        )

    def evaluate(self):
        return judgment.evaluate_judgment(self.case, self.policy, self.workspace, self.preflight)

    def test_operator_independent_approval(self):
        receipt = self.evaluate()
        self.assertEqual(receipt["disposition"], "approve")
        self.assertEqual(receipt["status"], "eligible-for-mandate-construction")
        self.assertFalse(receipt["authority"]["operatorApprovalRequiredForThisJudgment"])
        self.assertTrue(receipt["authority"]["mandateConstructionEligible"])
        self.assertFalse(receipt["authority"]["mandateConstructed"])
        self.assertFalse(receipt["authority"]["executionApplied"])

    def test_deterministic(self):
        self.assertEqual(judgment.canonical_bytes(self.evaluate()), judgment.canonical_bytes(self.evaluate()))

    def test_policy_digest_mismatch_fails_closed(self):
        self.case["bindings"]["policyReceiptDigest"] = fixtures.sha("9")
        with self.assertRaisesRegex(judgment.JudgmentError, "policyReceiptDigest mismatch"):
            self.evaluate()

    def test_blocked_preflight_rejects(self):
        self.preflight["status"] = "blocked"
        self.preflight["blockers"] = ["grant-revoked"]
        self.case["bindings"]["transitionPreflightReceiptDigest"] = judgment.digest(self.preflight)
        receipt = self.evaluate()
        self.assertEqual(receipt["disposition"], "reject")
        self.assertIn("transition-preflight-not-eligible", receipt["blockers"])

    def test_workspace_rejection_rejects(self):
        self.workspace["outcome"] = "reject"
        self.case["bindings"]["workspaceReceiptDigest"] = judgment.digest(self.workspace)
        receipt = self.evaluate()
        self.assertEqual(receipt["disposition"], "reject")

    def test_transitive_defeated_assumption_defers(self):
        self.case["assumptions"][0]["status"] = "defeated"
        receipt = self.evaluate()
        self.assertEqual(receipt["disposition"], "defer")
        self.assertIn("assumption-defeated:assumption:evidence-current", receipt["blockers"])
        self.assertIn("assumption:evidence-current", receipt["assumptionState"]["retractedRefs"])

    def test_unknown_assumption_defers(self):
        self.case["assumptions"][1]["status"] = "unknown"
        receipt = self.evaluate()
        self.assertEqual(receipt["disposition"], "defer")
        self.assertIn("assumption-unknown:assumption:target-reversible", receipt["blockers"])

    def test_assumption_cycle_is_rejected(self):
        self.case["assumptions"][0]["dependsOn"] = ["assumption:target-reversible"]
        with self.assertRaisesRegex(judgment.JudgmentError, "dependency cycle"):
            self.evaluate()

    def test_triggered_nogood_defers(self):
        self.case["requiredAssumptionRefs"].append("assumption:executor-healthy")
        receipt = self.evaluate()
        self.assertEqual(receipt["disposition"], "defer")
        self.assertIn("nogood-triggered:nogood:reversible-and-irreversible", receipt["blockers"])

    def test_excess_selective_risk_abstains(self):
        self.case["riskCertificate"]["riskUpperBoundBps"] = 900
        receipt = self.evaluate()
        self.assertEqual(receipt["disposition"], "abstain")
        self.assertIn("selective-risk-above-budget", receipt["blockers"])

    def test_low_coverage_abstains(self):
        self.case["riskCertificate"]["coverageBps"] = 6000
        receipt = self.evaluate()
        self.assertEqual(receipt["disposition"], "abstain")
        self.assertIn("coverage-below-minimum", receipt["blockers"])

    def test_expired_certificate_abstains(self):
        self.case["riskCertificate"]["validUntil"] = "2026-07-22T04:04:59Z"
        receipt = self.evaluate()
        self.assertEqual(receipt["disposition"], "abstain")
        self.assertIn("risk-certificate-not-current", receipt["blockers"])

    def test_runtime_threshold_forces_fallback(self):
        self.case["runtimeAssurance"]["hazardScoreBps"] = 3500
        receipt = self.evaluate()
        self.assertEqual(receipt["disposition"], "fallback-only")
        self.assertTrue(receipt["authority"]["fallbackTakeoverRequired"])
        self.assertIn("runtime-takeover-threshold-breached", receipt["blockers"])

    def test_failed_invariant_forces_fallback(self):
        self.case["runtimeAssurance"]["invariants"][0]["status"] = "fail"
        receipt = self.evaluate()
        self.assertEqual(receipt["disposition"], "fallback-only")
        self.assertIn("runtime-invariant-failed:rollback-exact", receipt["blockers"])

    def test_non_independent_monitor_forces_fallback(self):
        self.case["runtimeAssurance"]["monitorIndependent"] = False
        receipt = self.evaluate()
        self.assertEqual(receipt["disposition"], "fallback-only")
        self.assertIn("runtime-monitor-not-independent", receipt["blockers"])

    def test_stale_dependency_defers(self):
        self.case["assumptions"][0]["validUntil"] = "2026-07-22T04:04:59Z"
        receipt = self.evaluate()
        self.assertEqual(receipt["disposition"], "defer")
        self.assertIn("assumption-not-current:assumption:evidence-current", receipt["blockers"])

    def test_future_transaction_time_is_rejected(self):
        self.case["transactionTime"]["recordedAt"] = "2026-07-22T04:06:00Z"
        with self.assertRaisesRegex(judgment.JudgmentError, "transaction time"):
            self.evaluate()

    def test_supersession_is_preserved(self):
        self.case["transactionTime"]["supersedesReceiptDigest"] = fixtures.sha("8")
        receipt = self.evaluate()
        self.assertEqual(receipt["bitemporal"]["supersedesReceiptDigest"], fixtures.sha("8"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
