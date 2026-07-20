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
sys.path.insert(0, str(ROOT / "modos" / "ontology"))

import compiler  # type: ignore  # noqa: E402
import synthetic_rehearsal  # noqa: E402


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


class SyntheticRehearsalTests(unittest.TestCase):
    def setUp(self):
        self.public = load(ROOT / "modos" / "ecology" / "public-ecology.json")
        self.schema = load(ROOT / "modos" / "contracts" / "ecology-registry.schema.json")

    def rehearse(self, public=None):
        return synthetic_rehearsal.run_rehearsal(public or self.public, self.schema)

    def test_complete_rehearsal_passes_without_live_or_authority_mutation(self):
        receipt = self.rehearse()
        self.assertEqual(receipt["status"], "pass")
        self.assertEqual(receipt["scope"], "synthetic-two-scope")
        self.assertEqual(receipt["mergedObjectCount"], 28)
        self.assertEqual(receipt["mergedRelationCount"], 26)
        self.assertEqual(receipt["feedbackRecordCount"], 10)
        self.assertEqual(receipt["competenceRecommendation"], "maintain")
        self.assertFalse(receipt["livePrivateEcologySupplied"])
        self.assertFalse(receipt["liveExecutionApplied"])
        self.assertFalse(receipt["trainingApplied"])
        self.assertFalse(receipt["grantMutationApplied"])
        self.assertFalse(receipt["constitutionalMutationApplied"])

    def test_rehearsal_is_deterministic_for_identical_source_evidence(self):
        first = self.rehearse()
        second = self.rehearse()
        self.assertEqual(compiler.canonical_bytes(first), compiler.canonical_bytes(second))

    def test_reordering_public_ecology_preserves_topology_but_changes_provenance_identity(self):
        reordered = copy.deepcopy(self.public)
        for field in ("groups", "components", "capabilities", "relations"):
            reordered["spec"][field].reverse()
        first = self.rehearse()
        second = self.rehearse(reordered)
        self.assertEqual(first["mergedObjectCount"], second["mergedObjectCount"])
        self.assertEqual(first["mergedRelationCount"], second["mergedRelationCount"])
        self.assertNotEqual(first["publicRegistryDigest"], second["publicRegistryDigest"])
        self.assertNotEqual(first["mergedSnapshotDigest"], second["mergedSnapshotDigest"])
        self.assertNotEqual(first["receiptDigest"], second["receiptDigest"])

    def test_synthetic_private_registry_contains_no_real_project_owner(self):
        registry = synthetic_rehearsal.synthetic_private_registry()
        rendered = json.dumps(registry, sort_keys=True)
        self.assertNotIn("Zheke32174", rendered)
        self.assertEqual(registry["metadata"]["owner"], "SyntheticLab")
        self.assertTrue(all(name.startswith("SyntheticLab/") for name in registry["spec"]["inventory"]["repositories"]))

    def test_synthetic_private_receipt_cannot_satisfy_live_private_blocker(self):
        receipt = self.rehearse()
        self.assertIn("live-private-exhaustive-registry-not-supplied", receipt["remainingBlockers"])

    def test_public_dangling_relation_aborts_rehearsal(self):
        public = copy.deepcopy(self.public)
        public["spec"]["relations"].append(
            {
                "type": "depends-on",
                "sourceRef": "repo:Zheke32174/pleiades",
                "targetRef": "repo:Zheke32174/missing",
                "scope": "runtime",
                "required": True,
            }
        )
        with self.assertRaisesRegex(compiler.OntologyCompileError, "dangling relation target"):
            self.rehearse(public)


if __name__ == "__main__":
    unittest.main(verbosity=2)
