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

import compiler  # noqa: E402
import ecology_adapter  # noqa: E402


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


class EcologyAdapterTests(unittest.TestCase):
    def setUp(self):
        self.registry = load(ROOT / "modos" / "ecology" / "public-ecology.json")
        self.schema = load(ROOT / "modos" / "contracts" / "ecology-registry.schema.json")

    def compile(self, registry=None):
        return ecology_adapter.compile_registry(registry or self.registry, self.schema)

    def test_public_projection_compiles_to_closed_snapshot(self):
        snapshot, receipt = self.compile()
        self.assertEqual(len(snapshot["objects"]), 18)
        self.assertEqual(len(snapshot["relations"]), 17)
        self.assertEqual(receipt["resultSnapshotDigest"], compiler.snapshot_digest(snapshot))
        self.assertFalse(receipt["fullEcologyClosure"])
        self.assertEqual(receipt["blockers"], ["live-private-exhaustive-registry-not-supplied"])

    def test_compilation_is_deterministic_under_input_array_reordering(self):
        reordered = copy.deepcopy(self.registry)
        for field in ("groups", "components", "capabilities", "relations"):
            reordered["spec"][field].reverse()
        first_snapshot, _ = self.compile()
        second_snapshot, _ = self.compile(reordered)
        self.assertEqual(compiler.canonical_bytes(first_snapshot), compiler.canonical_bytes(second_snapshot))

    def test_every_registry_repository_becomes_resource(self):
        snapshot, _ = self.compile()
        ids = {row["metadata"]["id"] for row in snapshot["objects"]}
        for repository in self.registry["spec"]["inventory"]["repositories"]:
            self.assertIn("repo:" + repository, ids)

    def test_authority_ceiling_is_preserved_on_repository_objects(self):
        snapshot, _ = self.compile()
        repositories = {
            row["metadata"]["id"]: row
            for row in snapshot["objects"]
            if row["kind"] == "Resource" and row["spec"].get("resourceClass") == "repository"
        }
        self.assertEqual(repositories["repo:Zheke32174/pleiades"]["spec"]["authorityCeiling"], "domain-control")
        self.assertEqual(repositories["repo:Zheke32174/pleiades-factory-stack"]["spec"]["authorityCeiling"], "proposal")

    def test_public_projection_cannot_claim_private_closure(self):
        _, receipt = self.compile()
        self.assertTrue(receipt["publicScopeIncluded"])
        self.assertFalse(receipt["privateScopeIncluded"])
        self.assertFalse(receipt["fullEcologyClosure"])

    def test_duplicate_membership_is_rejected(self):
        registry = copy.deepcopy(self.registry)
        registry["spec"]["groups"][1]["repositories"].append("Zheke32174/pleiades")
        with self.assertRaisesRegex(ecology_adapter.EcologyAdapterError, "multiple groups"):
            self.compile(registry)

    def test_unknown_relation_endpoint_fails_ontology_closure(self):
        registry = copy.deepcopy(self.registry)
        registry["spec"]["relations"].append(
            {
                "required": True,
                "scope": "runtime",
                "sourceRef": "repo:Zheke32174/pleiades",
                "targetRef": "repo:Zheke32174/does-not-exist",
                "type": "depends-on",
            }
        )
        with self.assertRaisesRegex(compiler.OntologyCompileError, "dangling relation target"):
            self.compile(registry)


if __name__ == "__main__":
    unittest.main(verbosity=2)
