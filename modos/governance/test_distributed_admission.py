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


engine = load("distributed_admission")
fixtures = load("distributed_fixtures")


class DistributedAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.registry = copy.deepcopy(fixtures.REGISTRY)
        self.plan = copy.deepcopy(fixtures.PLAN)

    def close(self, history=None):
        return engine.close_rollout(self.registry, self.plan, [] if history is None else history)

    def test_closed(self):
        self.assertEqual(self.close()["status"], "closed")

    def test_canary_first(self):
        self.plan["stages"][0]["canary"] = False
        with self.assertRaisesRegex(engine.DistributedAdmissionError, "canary"):
            self.close()

    def test_unknown_node(self):
        self.plan["stages"][1]["nodeRefs"] = ["node:missing"]
        with self.assertRaisesRegex(engine.DistributedAdmissionError, "unknown node"):
            self.close()

    def test_capability_required(self):
        self.registry["nodes"][0]["capabilities"].remove("ontology.snapshot.admit")
        with self.assertRaisesRegex(engine.DistributedAdmissionError, "lacks executor"):
            self.close()

    def test_rollback_required(self):
        self.registry["nodes"][0]["capabilities"].remove("rollback.exact")
        with self.assertRaisesRegex(engine.DistributedAdmissionError, "rollback"):
            self.close()

    def test_write_scope_required(self):
        self.registry["nodes"][0]["writeScopes"] = ["other"]
        with self.assertRaisesRegex(engine.DistributedAdmissionError, "write scope"):
            self.close()

    def test_partition_ceiling(self):
        self.registry["nodes"][0]["partitionPolicy"] = {"mode": "limited-local", "maxOfflineSeconds": 60}
        with self.assertRaisesRegex(engine.DistributedAdmissionError, "partitioned"):
            self.close()

    def test_replay_rejected(self):
        prior = {
            "replayNonce": self.plan["replayNonce"],
            "idempotencyKey": "different-key-0001",
            "planDigest": engine.digest({"different": True}),
        }
        with self.assertRaisesRegex(engine.DistributedAdmissionError, "replay nonce"):
            self.close([prior])

    def test_idempotent_replay(self):
        receipt = self.close()
        prior = {
            "replayNonce": self.plan["replayNonce"],
            "idempotencyKey": self.plan["idempotencyKey"],
            "planDigest": engine.digest(self.plan),
            "stageSchedule": receipt["stageSchedule"],
            "rollbackGroups": receipt["rollbackGroups"],
        }
        self.assertEqual(self.close([prior])["status"], "idempotent-replay")

    def test_duplicate_node(self):
        self.plan["stages"][1]["nodeRefs"] = ["node:canary"]
        with self.assertRaisesRegex(engine.DistributedAdmissionError, "more than one stage"):
            self.close()

    def test_complete_coverage(self):
        self.plan["stages"].pop()
        with self.assertRaisesRegex(engine.DistributedAdmissionError, "does not cover"):
            self.close()

    def test_golden(self):
        self.assertEqual(engine.digest(self.close()), fixtures.EXPECTED)


if __name__ == "__main__":
    unittest.main(verbosity=2)
