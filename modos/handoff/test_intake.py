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

INTAKE_SPEC = importlib.util.spec_from_file_location("pleiades_operator_intake", HERE / "intake.py")
assert INTAKE_SPEC and INTAKE_SPEC.loader
intake = importlib.util.module_from_spec(INTAKE_SPEC)
sys.modules[INTAKE_SPEC.name] = intake
INTAKE_SPEC.loader.exec_module(intake)

TEMPLATE_SPEC = importlib.util.spec_from_file_location("pleiades_operator_template", HERE / "template.py")
assert TEMPLATE_SPEC and TEMPLATE_SPEC.loader
template = importlib.util.module_from_spec(TEMPLATE_SPEC)
sys.modules[TEMPLATE_SPEC.name] = template
TEMPLATE_SPEC.loader.exec_module(template)


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


class OperatorIntakeTests(unittest.TestCase):
    def setUp(self):
        self.candidate = load(HERE / "fixtures" / "operator-input-candidate.synthetic-ready.json")
        self.expected = load(HERE / "fixtures" / "expected-operator-input-compilation-receipt.json")
        self.schema = load(ROOT / "modos" / "contracts" / "operator-input-candidate.schema.json")

    def compile(self, candidate=None):
        return intake.compile_candidate(candidate or self.candidate, self.schema)

    def test_golden_receipt(self):
        self.assertEqual(intake.canonical_bytes(self.compile()), intake.canonical_bytes(self.expected))

    def test_identical_candidate_is_deterministic(self):
        self.assertEqual(intake.canonical_bytes(self.compile()), intake.canonical_bytes(self.compile()))

    def test_empty_template_is_schema_valid_and_non_authoritative(self):
        candidate = template.build_template(
            "2" * 40,
            "2026-07-20T23:30:00Z",
            "operator-input-candidate:empty-template-0001",
        )
        receipt = self.compile(candidate)
        self.assertEqual(receipt["state"], "operator-inputs-required")
        self.assertEqual(receipt["satisfiedInputs"], [])
        self.assertEqual(len(receipt["pendingInputs"]), 8)
        self.assertTrue(all(row["artifactRef"] is None for row in candidate["inputs"].values()))
        self.assertFalse(receipt["authority"]["liveExecutionApplied"])

    def test_template_generation_is_deterministic_for_explicit_inputs(self):
        first = template.build_template("2" * 40, "2026-07-20T23:30:00Z", "operator-input-candidate:empty-template-0001")
        second = template.build_template("2" * 40, "2026-07-20T23:30:00Z", "operator-input-candidate:empty-template-0001")
        self.assertEqual(intake.canonical_bytes(first), intake.canonical_bytes(second))

    def test_receipt_remains_proposal_only(self):
        receipt = self.compile()
        self.assertEqual(receipt["authority"]["ceiling"], "none")
        self.assertFalse(receipt["authority"]["canonicalMutationApplied"])
        self.assertFalse(receipt["authority"]["liveExecutionApplied"])
        self.assertFalse(receipt["authority"]["historyRewriteApplied"])
        self.assertFalse(receipt["authority"]["grantIssued"])
        self.assertTrue(all(not row["executionApplied"] for row in receipt["outputPlans"]))

    def test_unsupplied_input_cannot_retain_bindings(self):
        candidate = copy.deepcopy(self.candidate)
        candidate["inputs"]["authorityGrant"]["supplied"] = False
        with self.assertRaisesRegex(intake.IntakeError, "unsupplied input authorityGrant"):
            self.compile(candidate)

    def test_supplied_input_requires_all_bindings(self):
        candidate = copy.deepcopy(self.candidate)
        candidate["inputs"]["nodeInventory"]["receiptDigest"] = None
        with self.assertRaisesRegex(intake.IntakeError, "supplied input nodeInventory"):
            self.compile(candidate)

    def test_nonpublic_reference_must_be_opaque(self):
        candidate = copy.deepcopy(self.candidate)
        candidate["inputs"]["privateEcology"]["artifactRef"] = "github:owner/private-ecology"
        with self.assertRaisesRegex(intake.IntakeError, "opaque Pleiades URN"):
            self.compile(candidate)

    def test_secret_like_reference_is_rejected(self):
        candidate = copy.deepcopy(self.candidate)
        candidate["inputs"]["privateEcology"]["classification"] = "public-reference"
        candidate["inputs"]["privateEcology"]["artifactRef"] = "github:owner/ghp_abcdefghijklmnopqrstuvwxyz123456"
        with self.assertRaisesRegex(intake.IntakeError, "secret-like material"):
            self.compile(candidate)

    def test_sovereign_history_decision_requires_evidence(self):
        candidate = copy.deepcopy(self.candidate)
        row = candidate["inputs"]["historyDecision"]
        row.update({"supplied": False, "artifactRef": None, "artifactDigest": None, "receiptDigest": None})
        with self.assertRaisesRegex(intake.IntakeError, "requires supplied sovereign evidence"):
            self.compile(candidate)

    def test_canary_selection_requires_node_and_plan_evidence(self):
        candidate = copy.deepcopy(self.candidate)
        row = candidate["inputs"]["canaryPlan"]
        row.update({"supplied": False, "artifactRef": None, "artifactDigest": None, "receiptDigest": None})
        with self.assertRaisesRegex(intake.IntakeError, "canary selection requires"):
            self.compile(candidate)

    def test_pending_candidate_emits_blocked_plans_without_execution(self):
        candidate = copy.deepcopy(self.candidate)
        for input_id in ("authorityGrant", "canaryPlan", "observationPlan"):
            row = candidate["inputs"][input_id]
            row.update({"supplied": False, "artifactRef": None, "artifactDigest": None, "receiptDigest": None})
        candidate["selections"] = {"canaryNodeId": None, "observationWindowSeconds": None}
        receipt = self.compile(candidate)
        self.assertEqual(receipt["state"], "operator-inputs-required")
        self.assertGreater(receipt["blockedOutputCount"], 0)
        self.assertFalse(receipt["authority"]["liveExecutionApplied"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
