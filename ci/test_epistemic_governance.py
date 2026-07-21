#!/usr/bin/env python3
"""Regression tests for the MODOS epistemic-governance validator."""
from __future__ import annotations

import copy
import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "ci" / "validate_epistemic_governance.py"
SPEC = importlib.util.spec_from_file_location("validate_epistemic_governance", MODULE_PATH)
assert SPEC and SPEC.loader
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


class EpistemicGovernanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.distinctions = json.loads(
            (ROOT / "modos" / "ontology" / "distinctions.json").read_text(encoding="utf-8")
        )
        cls.ledger = json.loads(
            (ROOT / "modos" / "ontology" / "epistemic-ledger.example.json").read_text(
                encoding="utf-8"
            )
        )
        _, _, _, cls.distinction_ids = validator.validate_distinctions(cls.distinctions)

    def validate(self, ledger: dict) -> tuple[list[str], list[str], dict]:
        return validator.validate_ledger(ledger, self.distinction_ids)

    def test_reference_fixture_is_valid(self) -> None:
        distinction_errors, _, _, _ = validator.validate_distinctions(self.distinctions)
        ledger_errors, _, _ = self.validate(self.ledger)
        self.assertEqual([], distinction_errors)
        self.assertEqual([], ledger_errors)

    def test_category_sensitive_claim_cannot_silently_collapse(self) -> None:
        ledger = copy.deepcopy(self.ledger)
        claim = ledger["spec"]["claims"][0]
        claim["preservesDistinctions"] = []
        claim["potentialCollapses"] = []
        errors, _, _ = self.validate(ledger)
        self.assertTrue(
            any("preserves no registered distinction" in error for error in errors),
            errors,
        )
        self.assertTrue(
            any("records no collapse risk" in error for error in errors),
            errors,
        )

    def test_accepting_decision_must_retain_active_dissent(self) -> None:
        ledger = copy.deepcopy(self.ledger)
        ledger["spec"]["decisions"][0]["dissentingArguments"] = []
        errors, _, _ = self.validate(ledger)
        self.assertTrue(any("silently omits active dissent" in error for error in errors), errors)

    def test_dependency_cycles_are_rejected(self) -> None:
        ledger = copy.deepcopy(self.ledger)
        ledger["spec"]["claims"][0]["dependsOn"] = ["claim-ontology-must-audit-itself"]
        errors, _, _ = self.validate(ledger)
        self.assertTrue(any("dependency graph contains a cycle" in error for error in errors), errors)

    def test_unknown_distinction_reference_is_rejected(self) -> None:
        ledger = copy.deepcopy(self.ledger)
        ledger["spec"]["claims"][0]["preservesDistinctions"].append("invented-binary")
        errors, _, _ = self.validate(ledger)
        self.assertTrue(any("preserves unknown distinction" in error for error in errors), errors)

    def test_argument_cycles_remain_unresolved_instead_of_being_deleted(self) -> None:
        errors, _, report = self.validate(self.ledger)
        self.assertEqual([], errors)
        self.assertIn("arg-local-intent", report["unresolvedActiveArguments"])
        self.assertIn("arg-centralization-objection", report["unresolvedActiveArguments"])


if __name__ == "__main__":
    unittest.main()
