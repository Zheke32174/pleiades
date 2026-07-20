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


engine = load("constitutional")
fixtures = load("constitutional_fixtures")


class ConstitutionalTests(unittest.TestCase):
    def setUp(self):
        self.registry = copy.deepcopy(fixtures.REGISTRY)
        self.proposal = copy.deepcopy(fixtures.PROPOSAL)
        self.deliberation = copy.deepcopy(fixtures.DELIBERATION)

    def gate(self, when=None):
        return engine.gate_amendment(
            self.registry,
            self.proposal,
            self.deliberation,
            fixtures.EVALUATED_AT if when is None else when,
        )

    def test_eligible(self):
        self.assertEqual(self.gate()["status"], "eligible-for-activation")

    def test_timelock_pending(self):
        self.assertEqual(self.gate("2026-07-22T12:00:00Z")["status"], "timelock-pending")

    def test_cancellation(self):
        self.deliberation["cancellationRequests"] = [
            {"principalRef": "human:steward-a", "requestedAt": "2026-07-21T12:00:00Z"}
        ]
        self.assertEqual(self.gate()["status"], "cancelled")

    def test_human_quorum(self):
        self.deliberation["contributions"][1]["position"] = "abstain"
        with self.assertRaisesRegex(engine.ConstitutionalError, "human quorum"):
            self.gate()

    def test_machine_quorum(self):
        self.deliberation["contributions"][2]["position"] = "abstain"
        with self.assertRaisesRegex(engine.ConstitutionalError, "machine executive"):
            self.gate()

    def test_audit_required(self):
        self.deliberation["contributions"][3]["recused"] = True
        with self.assertRaisesRegex(engine.ConstitutionalError, "audit quorum"):
            self.gate()

    def test_appeal_cannot_approve(self):
        self.deliberation["contributions"][4]["position"] = "approve"
        with self.assertRaisesRegex(engine.ConstitutionalError, "appeal authority"):
            self.gate()

    def test_conflict_recusal(self):
        self.registry["principals"][0]["conflictDomains"] = ["authority-model"]
        with self.assertRaisesRegex(engine.ConstitutionalError, "must recuse"):
            self.gate()

    def test_short_timelock(self):
        self.proposal["activationNotBefore"] = "2026-07-22T00:00:00Z"
        self.deliberation["proposalDigest"] = engine.digest(self.proposal)
        with self.assertRaisesRegex(engine.ConstitutionalError, "timelock"):
            self.gate()

    def test_rollback_lineage(self):
        self.proposal["rollbackDigest"] = fixtures.sha("f")
        self.deliberation["proposalDigest"] = engine.digest(self.proposal)
        with self.assertRaisesRegex(engine.ConstitutionalError, "rollback"):
            self.gate()

    def test_succession_resolves(self):
        self.registry["principals"][0]["status"] = "succeeded"
        self.registry["principals"][0].pop("successorRef")
        with self.assertRaisesRegex(engine.ConstitutionalError, "requires successor"):
            self.gate()

    def test_golden(self):
        self.assertEqual(engine.digest(self.gate()), fixtures.EXPECTED)


if __name__ == "__main__":
    unittest.main(verbosity=2)
