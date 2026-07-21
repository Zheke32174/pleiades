#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from ci.validate_ontology_revision import validate_semantics


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "modos/contracts/ontology-revision-proposal.schema.json"
PROPOSAL_PATH = ROOT / "modos/ontology/ontology-revision-proposal.example.json"


class OntologyRevisionValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        cls.proposal = json.loads(PROPOSAL_PATH.read_text(encoding="utf-8"))
        cls.validator = Draft202012Validator(
            cls.schema, format_checker=FormatChecker()
        )

    def assert_schema_valid(self, value: dict) -> None:
        errors = list(self.validator.iter_errors(value))
        self.assertEqual([], errors, [error.message for error in errors])

    def test_reference_proposal_is_valid(self) -> None:
        proposal = copy.deepcopy(self.proposal)
        self.assert_schema_valid(proposal)
        errors, warnings, report = validate_semantics(proposal)
        self.assertEqual([], errors)
        self.assertTrue(report["hermeneuticalGap"])
        self.assertTrue(report["consistencyIllusionSignal"])
        self.assertGreaterEqual(len(warnings), 1)

    def test_hermeneutical_gap_requires_recurring_residuals(self) -> None:
        proposal = copy.deepcopy(self.proposal)
        proposal["spec"]["trigger"]["observedResiduals"] = [
            proposal["spec"]["trigger"]["observedResiduals"][0]
        ]
        errors, _, _ = validate_semantics(proposal)
        self.assertTrue(
            any("at least two recurring residual" in error for error in errors)
        )

    def test_boundary_object_requires_multiple_local_interpretations(self) -> None:
        proposal = copy.deepcopy(self.proposal)
        proposal["spec"]["change"]["operation"] = "add-boundary-object"
        proposal["spec"]["plurality"]["localInterpretations"] = [
            proposal["spec"]["plurality"]["localInterpretations"][0]
        ]
        errors, _, _ = validate_semantics(proposal)
        self.assertTrue(
            any("at least two local interpretations" in error for error in errors)
        )

    def test_deprecation_requires_non_destructive_alternative(self) -> None:
        proposal = copy.deepcopy(self.proposal)
        proposal["spec"]["diagnosis"]["hermeneuticalGap"] = False
        proposal["spec"]["change"]["operation"] = "deprecate-concept"
        proposal["spec"]["change"]["deprecatesRefs"] = ["concept:conspiracy"]
        proposal["spec"]["alternatives"] = [
            {
                "id": "delete-anyway",
                "operation": "deprecate-concept",
                "description": "Deprecate without testing a weaker repair.",
                "status": "active",
                "rationale": "Convenient but destructive.",
            }
        ]
        errors, _, _ = validate_semantics(proposal)
        self.assertTrue(
            any("requires a documented weakening" in error for error in errors)
        )

    def test_approved_proposal_requires_evidence_diversity(self) -> None:
        proposal = copy.deepcopy(self.proposal)
        proposal["metadata"]["status"] = "approved"
        proposal["spec"]["review"]["decision"] = "approve"
        proposal["spec"]["review"]["evidenceSourceGroups"] = ["one-source"]
        errors, _, _ = validate_semantics(proposal)
        self.assertTrue(
            any("fewer independent evidence source groups" in error for error in errors)
        )

    def test_consistency_illusion_requires_mitigation(self) -> None:
        proposal = copy.deepcopy(self.proposal)
        proposal["spec"]["proofObligations"]["consistencyIllusionMitigation"] = ""
        errors, _, _ = validate_semantics(proposal)
        self.assertTrue(
            any("consistency-illusion signal requires" in error for error in errors)
        )

    def test_translation_rules_must_reference_known_viewpoints(self) -> None:
        proposal = copy.deepcopy(self.proposal)
        proposal["spec"]["plurality"]["translationRules"][0]["toViewpoint"] = "unknown"
        errors, _, _ = validate_semantics(proposal)
        self.assertTrue(
            any("unknown toViewpoint" in error for error in errors)
        )

    def test_experimental_proposal_requires_branch(self) -> None:
        proposal = copy.deepcopy(self.proposal)
        proposal["metadata"].pop("branchRef")
        errors, _, _ = validate_semantics(proposal)
        self.assertTrue(
            any("experimental proposal requires a branchRef" in error for error in errors)
        )


if __name__ == "__main__":
    unittest.main()
