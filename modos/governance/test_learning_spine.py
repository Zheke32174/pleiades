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


engine = load("learning_spine")
fixtures = load("learning_fixtures")


class LearningSpineTests(unittest.TestCase):
    def setUp(self):
        self.batch = copy.deepcopy(fixtures.BATCH)

    def close(self):
        return engine.close_spine(self.batch)

    def test_closed(self):
        self.assertEqual(len(self.close()["recordsIndex"]), 6)

    def test_episode_index(self):
        self.assertEqual(len(self.close()["episodicIndex"][0]["recordRefs"]), 6)

    def test_semantic_index(self):
        self.assertEqual(len(self.close()["semanticIndex"]), 6)

    def test_contradiction_preserved(self):
        self.assertEqual(self.close()["contradictions"][0]["status"], "unresolved")

    def test_correction_does_not_erase(self):
        receipt = self.close()
        index = {item["recordId"]: item for item in receipt["recordsIndex"]}
        self.assertTrue(index["record:observation"]["corrected"])
        self.assertIn("record:observation", index)

    def test_verified_feedback_only(self):
        self.assertEqual(
            [item["recordId"] for item in self.close()["feedbackManifest"]["verifiedOutcomeRecords"]],
            ["record:outcome"],
        )

    def test_unverified_training_rejected(self):
        outcome = next(item for item in self.batch["records"] if item["recordId"] == "record:outcome")
        outcome["verification"] = {"status": "unverified", "independent": False}
        with self.assertRaisesRegex(engine.LearningSpineError, "training outcome"):
            self.close()

    def test_non_outcome_training_rejected(self):
        self.batch["records"][0]["trainingEligible"] = True
        with self.assertRaisesRegex(engine.LearningSpineError, "non-outcome"):
            self.close()

    def test_self_generated_training_rejected(self):
        outcome = next(item for item in self.batch["records"] if item["recordId"] == "record:outcome")
        outcome["source"] = {"sourceType": "mind", "principalRef": "mind:pleiades"}
        with self.assertRaisesRegex(engine.LearningSpineError, "self-generated"):
            self.close()

    def test_missing_correction_target(self):
        correction = next(item for item in self.batch["records"] if item["recordKind"] == "correction")
        correction["correctsRefs"] = ["missing"]
        with self.assertRaisesRegex(engine.LearningSpineError, "target is missing"):
            self.close()

    def test_ephemeral_evidence_rejected(self):
        next(item for item in self.batch["records"] if item["recordKind"] == "decision")["retentionClass"] = "ephemeral"
        with self.assertRaisesRegex(engine.LearningSpineError, "cannot be ephemeral"):
            self.close()

    def test_golden(self):
        self.assertEqual(engine.digest(self.close()), fixtures.EXPECTED)


if __name__ == "__main__":
    unittest.main(verbosity=2)
