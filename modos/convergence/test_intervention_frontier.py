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

import intervention_frontier  # noqa: E402


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


class InterventionFrontierTests(unittest.TestCase):
    def setUp(self):
        self.bundle = load(HERE / "repository-ready-intervention.fixture.json")
        self.schema = load(ROOT / "modos" / "contracts" / "operator-intervention-bundle.schema.json")

    def evaluate(self, bundle=None):
        return intervention_frontier.evaluate(bundle or self.bundle, self.schema)

    def test_repository_ready_fixture_requires_operator_intervention(self):
        receipt = self.evaluate()
        self.assertEqual(receipt["status"], "operator-intervention-required")
        self.assertEqual(receipt["autonomousActionCount"], 0)
        self.assertGreater(receipt["operatorActionCount"], 0)
        self.assertFalse(receipt["maySimulateOperatorConsent"])

    def test_incomplete_repository_work_precedes_operator_frontier(self):
        bundle = copy.deepcopy(self.bundle)
        bundle["repositoryReadiness"]["syntheticRehearsalPassed"] = False
        receipt = self.evaluate(bundle)
        self.assertEqual(receipt["status"], "autonomous-repository-work-remains")
        self.assertIn("run-synthetic-rehearsal", {row["id"] for row in receipt["autonomousRepositoryActions"]})

    def test_private_key_material_is_forbidden(self):
        bundle = copy.deepcopy(self.bundle)
        bundle["signingAuthority"]["privateKeyMaterialIncluded"] = True
        with self.assertRaisesRegex(intervention_frontier.FrontierError, "schema validation failed"):
            self.evaluate(bundle)

    def test_unresolved_canary_is_rejected(self):
        bundle = copy.deepcopy(self.bundle)
        bundle["liveSubstrate"]["canaryNodeId"] = "node:missing"
        with self.assertRaisesRegex(intervention_frontier.FrontierError, "does not resolve"):
            self.evaluate(bundle)

    def test_fully_supplied_bundle_reaches_next_progression_boundary(self):
        bundle = copy.deepcopy(self.bundle)
        d = "sha256:" + "a" * 64
        bundle["privateEcology"] = {"supplied": True, "artifactDigest": d, "receiptDigest": d}
        bundle["observedInventory"] = {"supplied": True, "artifactDigest": d, "receiptDigest": d}
        bundle["historyRewrite"] = {"decision": "declined", "authorizationRef": "decision:retain-history", "planDigest": d}
        bundle["signingAuthority"] = {"delegated": True, "issuerRef": "principal:constitutional-steward", "publicKeyDigest": d, "privateKeyMaterialIncluded": False}
        bundle["liveSubstrate"] = {
            "nodes": [{"nodeId": "node:canary", "capabilityDigest": d, "publicKeyDigest": d, "rollbackPredecessorDigest": d}],
            "canaryNodeId": "node:canary",
            "delegatedGrantIssued": True,
            "grantDigest": d,
            "liveLoopAuthorized": True,
            "liveLoopCompleted": True,
            "liveLoopEvidenceDigest": d,
        }
        bundle["sustainedObservation"] = {"authorized": True, "requiredSeconds": 604800, "completed": True, "evidenceDigest": d}
        receipt = self.evaluate(bundle)
        self.assertEqual(receipt["status"], "ready-to-derive-next-progression")
        self.assertEqual(receipt["operatorActionCount"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
