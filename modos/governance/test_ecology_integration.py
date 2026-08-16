#!/usr/bin/env python3
from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


engine = load("ecology_integration")
fixtures = load("ecology_integration_fixtures")


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.candidate = copy.deepcopy(fixtures.CANDIDATE)

    def evaluate(self):
        return engine.evaluate(self.candidate)

    def test_ready_live_blocked(self):
        receipt = self.evaluate()
        self.assertEqual(receipt["status"], "repository-ready-live-blocked")
        self.assertEqual(len(receipt["blockers"]), 3)

    def test_full_live_private_clears_one_blocker(self):
        self.candidate["ontologyClosure"]["verifiedAgainstLivePrivateRegistry"] = True
        self.assertEqual(len(self.evaluate()["blockers"]), 2)

    def test_seed_only_rejected(self):
        self.candidate["ontologyClosure"]["seedOnly"] = True
        with self.assertRaisesRegex(engine.IntegrationReadinessError, "seed-only"):
            self.evaluate()

    def test_service_joint_complete(self):
        self.candidate["serviceLearningJoints"][0]["structuredOutputs"].remove("correction")
        with self.assertRaisesRegex(engine.IntegrationReadinessError, "incomplete"):
            self.evaluate()

    def test_blind_training_rejected(self):
        self.candidate["serviceLearningJoints"][0]["blindSelfTrainingAllowed"] = True
        with self.assertRaisesRegex(engine.IntegrationReadinessError, "blind"):
            self.evaluate()

    def test_simulation_count(self):
        self.candidate["simulation"]["scenarioCount"] = 2
        with self.assertRaisesRegex(engine.IntegrationReadinessError, "ten scenarios"):
            self.evaluate()

    def test_calibration_error(self):
        self.candidate["calibration"]["observedSuccessBps"] = 1000
        with self.assertRaisesRegex(engine.IntegrationReadinessError, "calibration"):
            self.evaluate()

    def test_metric_regression(self):
        self.candidate["improvementEvaluation"]["machineMetrics"][0]["after"] = 1000
        with self.assertRaisesRegex(engine.IntegrationReadinessError, "metric"):
            self.evaluate()

    def test_ordinary_person_evidence(self):
        self.candidate["improvementEvaluation"]["ordinaryPersonEvaluation"]["preferenceRateBps"] = 5000
        with self.assertRaisesRegex(engine.IntegrationReadinessError, "ordinary-person"):
            self.evaluate()

    def test_treaty_constitution_forbidden(self):
        self.candidate["treaties"][0]["constitutionalDelegationAllowed"] = True
        with self.assertRaisesRegex(engine.IntegrationReadinessError, "constitutional"):
            self.evaluate()

    def test_missing_relation(self):
        self.candidate["relations"].pop()
        with self.assertRaisesRegex(engine.IntegrationReadinessError, "relations are incomplete"):
            self.evaluate()

    def test_golden(self):
        self.assertEqual(engine.digest(self.evaluate()), fixtures.EXPECTED)


if __name__ == "__main__":
    unittest.main(verbosity=2)
