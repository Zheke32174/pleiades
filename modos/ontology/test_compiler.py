#!/usr/bin/env python3
from __future__ import annotations

import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("pleiades_ontology_compiler", HERE / "compiler.py")
assert SPEC and SPEC.loader
compiler = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = compiler
SPEC.loader.exec_module(compiler)


def load(name: str):
    with (HERE / "fixtures" / name).open(encoding="utf-8") as handle:
        return json.load(handle)


class CompilerTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = load("seed-snapshot.json")
        self.proposal = load("link-workspace.proposal.json")

    def test_link_compiles_with_closed_receipt(self):
        result, receipt = compiler.compile_proposal(self.snapshot, self.proposal)
        self.assertEqual(receipt["closureStatus"], "closed")
        self.assertFalse(receipt["authority"]["canonicalMutationApplied"])
        self.assertTrue(receipt["authority"]["promotionTransactionRequired"])
        self.assertEqual(receipt["semanticDiff"]["objectsAdded"], [])
        self.assertEqual(len(receipt["semanticDiff"]["relationsAdded"]), 1)
        self.assertEqual(compiler.snapshot_digest(result), receipt["resultSnapshotDigest"])

    def test_source_digest_mismatch_fails_closed(self):
        proposal = copy.deepcopy(self.proposal)
        proposal["sourceSnapshotDigest"] = "sha256:" + "0" * 64
        with self.assertRaisesRegex(compiler.OntologyCompileError, "sourceSnapshotDigest"):
            compiler.compile_proposal(self.snapshot, proposal)

    def test_dangling_target_fails_closed(self):
        proposal = copy.deepcopy(self.proposal)
        proposal["operations"][0]["targetRef"] = "workspace:missing"
        with self.assertRaisesRegex(compiler.OntologyCompileError, "target does not exist"):
            compiler.compile_proposal(self.snapshot, proposal)

    def test_model_cannot_be_whole_mind(self):
        proposal = load("create-whole-mind-model.proposal.json")
        with self.assertRaisesRegex(compiler.OntologyCompileError, "whole Mind"):
            compiler.compile_proposal(self.snapshot, proposal)

    def test_candidate_cannot_arrive_canonical(self):
        proposal = load("create-model.proposal.json")
        proposal["operations"][0]["payload"]["provenance"]["trust"] = "canonical"
        with self.assertRaisesRegex(compiler.OntologyCompileError, "cannot create or update an object as canonical"):
            compiler.compile_proposal(self.snapshot, proposal)

    def test_update_generation_must_advance_once(self):
        proposal = load("update-mind.proposal.json")
        proposal["operations"][0]["payload"]["metadata"]["generation"] = 3
        with self.assertRaisesRegex(compiler.OntologyCompileError, "generation must advance exactly once"):
            compiler.compile_proposal(self.snapshot, proposal)

    def test_delete_referenced_object_fails_closure(self):
        proposal = load("delete-workspace.proposal.json")
        linked, _ = compiler.compile_proposal(self.snapshot, self.proposal)
        proposal["sourceSnapshotDigest"] = compiler.snapshot_digest(linked)
        with self.assertRaisesRegex(compiler.OntologyCompileError, "dangling relation target"):
            compiler.compile_proposal(linked, proposal)

    def test_input_order_does_not_change_snapshot_digest(self):
        reordered = copy.deepcopy(self.snapshot)
        reordered["objects"].reverse()
        reordered["relations"].reverse()
        self.assertEqual(compiler.snapshot_digest(self.snapshot), compiler.snapshot_digest(reordered))

    def test_duplicate_operation_is_rejected(self):
        proposal = copy.deepcopy(self.proposal)
        proposal["operations"].append(copy.deepcopy(proposal["operations"][0]))
        with self.assertRaisesRegex(compiler.OntologyCompileError, "duplicates"):
            compiler.compile_proposal(self.snapshot, proposal)

    def test_exact_compilation_is_deterministic(self):
        first_result, first_receipt = compiler.compile_proposal(self.snapshot, self.proposal)
        second_result, second_receipt = compiler.compile_proposal(self.snapshot, self.proposal)
        self.assertEqual(compiler.canonical_bytes(first_result), compiler.canonical_bytes(second_result))
        self.assertEqual(compiler.canonical_bytes(first_receipt), compiler.canonical_bytes(second_receipt))

    def test_compilation_matches_checked_in_golden_outputs(self):
        result, receipt = compiler.compile_proposal(self.snapshot, self.proposal)
        self.assertEqual(compiler.canonical_bytes(result), compiler.canonical_bytes(load("expected-candidate-snapshot.json")))
        self.assertEqual(compiler.canonical_bytes(receipt), compiler.canonical_bytes(load("expected-closure-receipt.json")))


if __name__ == "__main__":
    unittest.main(verbosity=2)
