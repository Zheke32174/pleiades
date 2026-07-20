#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import promotion  # noqa: E402


def load(name: str):
    with (HERE / "fixtures" / name).open(encoding="utf-8") as handle:
        return json.load(handle)


class PromotionGateTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = load("expected-candidate-snapshot.json")
        self.receipt = load("expected-closure-receipt.json")
        self.manifest = load("source-manifest.json")
        self.candidate = load("promotion-candidate.json")

    def evaluate(self, candidate=None, manifest=None, receipt=None, snapshot=None):
        return promotion.evaluate_promotion_candidate(
            snapshot or self.snapshot,
            receipt or self.receipt,
            manifest or self.manifest,
            candidate or self.candidate,
        )

    def test_checked_in_candidate_is_blocked_by_preserved_history_gate(self):
        report = self.evaluate()
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["blockers"], ["github:Zheke32174/pleiades#42"])
        self.assertFalse(report["authority"]["canonicalMutationApplied"])
        self.assertTrue(report["authority"]["promotionTransactionRequired"])

    def test_candidate_without_blockers_is_eligible_for_authorized_decision(self):
        candidate = copy.deepcopy(self.candidate)
        candidate["blockingIssues"] = []
        report = self.evaluate(candidate=candidate)
        self.assertEqual(report["status"], "eligible-for-authorized-decision")
        self.assertEqual(report["authority"]["ceiling"], "none")

    def test_delegated_machine_executive_policy_can_require_zero_human_approvals(self):
        candidate = copy.deepcopy(self.candidate)
        candidate["blockingIssues"] = []
        candidate["authorizationPolicy"] = {
            "authorizationMode": "delegated-machine-executive",
            "requiredHumanApprovals": 0,
            "machineExecutiveDecisionRequired": True,
            "delegatedAuthorityGrantRequired": True,
            "codeownersRequired": True,
            "rulesetReviewRequired": True,
            "artifactAttestationRequired": False,
            "signedPromotionTransactionRequired": True,
        }
        report = self.evaluate(candidate=candidate)
        self.assertEqual(report["status"], "eligible-for-authorized-decision")

    def test_machine_executive_policy_rejects_hidden_human_gate(self):
        candidate = copy.deepcopy(self.candidate)
        candidate["authorizationPolicy"] = {
            "authorizationMode": "delegated-machine-executive",
            "requiredHumanApprovals": 1,
            "machineExecutiveDecisionRequired": True,
            "delegatedAuthorityGrantRequired": True,
            "codeownersRequired": True,
            "rulesetReviewRequired": True,
            "artifactAttestationRequired": False,
            "signedPromotionTransactionRequired": True,
        }
        with self.assertRaisesRegex(promotion.PromotionEvidenceError, "zero human approvals"):
            self.evaluate(candidate=candidate)

    def test_placeholder_digest_is_rejected(self):
        candidate = copy.deepcopy(self.candidate)
        candidate["sourceSnapshotDigest"] = "sha256:" + "0" * 64
        with self.assertRaisesRegex(promotion.PromotionEvidenceError, "non-placeholder"):
            self.evaluate(candidate=candidate)

    def test_commit_binding_mismatch_is_rejected(self):
        candidate = copy.deepcopy(self.candidate)
        candidate["commitSha"] = "f" * 40
        with self.assertRaisesRegex(promotion.PromotionEvidenceError, "repository-branch-commit-bound"):
            self.evaluate(candidate=candidate)

    def test_candidate_snapshot_digest_mismatch_is_rejected(self):
        candidate = copy.deepcopy(self.candidate)
        candidate["candidateSnapshotDigest"] = "sha256:" + "f" * 64
        with self.assertRaisesRegex(promotion.PromotionEvidenceError, "candidate-snapshot-digest-bound"):
            self.evaluate(candidate=candidate)

    def test_manifest_reordering_does_not_change_gate_report(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["artifacts"].reverse()
        candidate = copy.deepcopy(self.candidate)
        candidate["sourceManifestDigest"] = promotion.digest(manifest)
        first = self.evaluate()
        second = self.evaluate(candidate=candidate, manifest=manifest)
        self.assertEqual(first["status"], second["status"])
        self.assertEqual(first["blockers"], second["blockers"])
        self.assertNotEqual(first["bindings"]["sourceManifestDigest"], second["bindings"]["sourceManifestDigest"])

    def test_duplicate_source_artifact_is_rejected(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["artifacts"].append(copy.deepcopy(manifest["artifacts"][0]))
        candidate = copy.deepcopy(self.candidate)
        candidate["sourceManifestDigest"] = promotion.digest(manifest)
        with self.assertRaisesRegex(promotion.PromotionEvidenceError, "duplicate source artifact"):
            self.evaluate(candidate=candidate, manifest=manifest)

    def test_codeowners_evidence_is_required(self):
        candidate = copy.deepcopy(self.candidate)
        candidate["governanceEvidence"] = []
        with self.assertRaisesRegex(promotion.PromotionEvidenceError, "governanceEvidence must be nonempty"):
            self.evaluate(candidate=candidate)

    def test_failed_closure_check_is_rejected(self):
        receipt = copy.deepcopy(self.receipt)
        receipt["checks"][0]["status"] = "fail"
        manifest = copy.deepcopy(self.manifest)
        manifest["subject"]["closureReceiptDigest"] = promotion.digest(receipt)
        candidate = copy.deepcopy(self.candidate)
        candidate["closureReceiptDigest"] = promotion.digest(receipt)
        candidate["sourceManifestDigest"] = promotion.digest(manifest)
        with self.assertRaisesRegex(promotion.PromotionEvidenceError, "every closure receipt check must pass"):
            self.evaluate(candidate=candidate, manifest=manifest, receipt=receipt)

    def test_gate_report_matches_checked_in_golden_output(self):
        report = self.evaluate()
        self.assertEqual(
            promotion.canonical_bytes(report),
            promotion.canonical_bytes(load("expected-promotion-gate-report.json")),
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
