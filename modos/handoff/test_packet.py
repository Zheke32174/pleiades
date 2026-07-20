#!/usr/bin/env python3
from __future__ import annotations

import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    value = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = value
    spec.loader.exec_module(value)
    return value


intake = module("pleiades_handoff_intake_for_packet", HERE / "intake.py")
sys.path.insert(0, str(HERE))
packet = module("pleiades_handoff_packet", HERE / "packet.py")
template = module("pleiades_handoff_template_for_packet", HERE / "template.py")


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def signed(value: dict, field: str) -> dict:
    result = copy.deepcopy(value)
    result[field] = intake.digest(result)
    return result


class OperatorHandoffPacketTests(unittest.TestCase):
    def setUp(self):
        self.candidate = load(HERE / "fixtures" / "operator-input-candidate.synthetic-ready.json")
        self.compilation = load(HERE / "fixtures" / "expected-operator-input-compilation-receipt.json")
        self.schema = load(ROOT / "modos" / "contracts" / "operator-handoff-packet.schema.json")
        self.branch = signed(
            {
                "apiVersion": "modos.pleiades/v1alpha1",
                "kind": "BranchConvergenceEvidence",
                "suite": {"status": "pass", "exitCode": 0},
                "currentTreeSensitivity": {"status": "clear"},
                "syntheticRehearsal": {"status": "pass"},
                "validationPackage": {"receiptDigest": "sha256:" + "a" * 64, "privateMaterialIncluded": False},
            },
            "evidenceDigest",
        )
        self.frontier = signed(
            {
                "apiVersion": "modos.pleiades/v1alpha1",
                "kind": "InterventionFrontierReceipt",
                "status": "ready-to-derive-next-progression",
                "operatorOrLiveActions": [],
                "authority": {"ceiling": "none", "canonicalMutationApplied": False},
            },
            "receiptDigest",
        )

    def build(self, candidate=None, compilation=None, branch=None, frontier=None):
        return packet.build_packet(
            candidate or self.candidate,
            compilation or self.compilation,
            branch or self.branch,
            frontier or self.frontier,
            self.schema,
            "operator-handoff:synthetic-0001",
        )

    def test_fully_bound_synthetic_packet_is_review_ready(self):
        result = self.build()
        self.assertEqual(result["state"], "ready-for-sovereign-review")
        self.assertEqual(len(result["readyPlans"]), 7)
        self.assertEqual(result["blockedPlans"], [])
        self.assertFalse(result["authority"]["liveExecutionApplied"])
        self.assertFalse(result["authority"]["grantIssued"])

    def test_packet_is_deterministic(self):
        self.assertEqual(intake.canonical_bytes(self.build()), intake.canonical_bytes(self.build()))

    def test_candidate_binding_mismatch_fails(self):
        candidate = copy.deepcopy(self.candidate)
        candidate["candidateId"] = "operator-input-candidate:synthetic-ready-0002"
        with self.assertRaisesRegex(packet.PacketError, "exact operator candidate"):
            self.build(candidate=candidate)

    def test_tampered_branch_evidence_fails(self):
        branch = copy.deepcopy(self.branch)
        branch["suite"]["status"] = "fail"
        with self.assertRaisesRegex(packet.PacketError, "does not reproduce"):
            self.build(branch=branch)

    def test_repository_failure_precedes_operator_readiness(self):
        branch = copy.deepcopy(self.branch)
        branch.pop("evidenceDigest")
        branch["suite"] = {"status": "fail", "exitCode": 1}
        branch = signed(branch, "evidenceDigest")
        self.assertEqual(self.build(branch=branch)["state"], "repository-repair-required")

    def test_frontier_actions_remain_operator_actions(self):
        frontier = copy.deepcopy(self.frontier)
        frontier.pop("receiptDigest")
        frontier["status"] = "operator-intervention-required"
        frontier["operatorOrLiveActions"] = [
            {"id": "issue-first-live-grant", "description": "Issue the first real delegated authority grant."}
        ]
        frontier = signed(frontier, "receiptDigest")
        result = self.build(frontier=frontier)
        self.assertEqual(result["state"], "operator-intervention-required")
        self.assertEqual(result["operatorActions"][0]["id"], "issue-first-live-grant")
        self.assertFalse(result["authority"]["grantIssued"])

    def test_empty_template_produces_operator_input_state(self):
        candidate = template.build_template(
            "2" * 40,
            "2026-07-20T23:30:00Z",
            "operator-input-candidate:empty-template-0001",
        )
        candidate_schema = load(ROOT / "modos" / "contracts" / "operator-input-candidate.schema.json")
        compilation = intake.compile_candidate(candidate, candidate_schema)
        result = self.build(candidate=candidate, compilation=compilation)
        self.assertEqual(result["state"], "operator-inputs-required")
        self.assertGreater(len(result["blockedPlans"]), 0)
        self.assertFalse(result["authority"]["canonicalMutationApplied"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
