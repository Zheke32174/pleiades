#!/usr/bin/env python3
from __future__ import annotations

import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("pleiades_ontology_projection", HERE / "projection.py")
assert SPEC and SPEC.loader
projection = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = projection
SPEC.loader.exec_module(projection)


def load(name: str):
    with (HERE / "fixtures" / name).open(encoding="utf-8") as handle:
        return json.load(handle)


class ProjectionTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = load("expected-candidate-snapshot.json")
        self.receipt = load("expected-closure-receipt.json")

    def test_projection_matches_golden_bundle(self):
        bundle = projection.build_projection_bundle(self.snapshot, self.receipt)
        self.assertEqual(
            projection.canonical_bytes(bundle),
            projection.canonical_bytes(load("expected-projection-bundle.json")),
        )

    def test_projection_is_non_authoritative(self):
        bundle = projection.build_projection_bundle(self.snapshot, self.receipt)
        self.assertEqual(bundle["authority"]["ceiling"], "none")
        self.assertFalse(bundle["authority"]["canonical"])
        self.assertFalse(bundle["authority"]["writeBackAllowed"])

    def test_receipt_digest_mismatch_fails(self):
        receipt = copy.deepcopy(self.receipt)
        receipt["resultSnapshotDigest"] = "sha256:" + "0" * 64
        with self.assertRaisesRegex(projection.ProjectionError, "exact projected snapshot"):
            projection.build_projection_bundle(self.snapshot, receipt)

    def test_authority_widening_fails(self):
        receipt = copy.deepcopy(self.receipt)
        receipt["authority"]["canonicalMutationApplied"] = True
        with self.assertRaisesRegex(projection.ProjectionError, "authority boundary"):
            projection.build_projection_bundle(self.snapshot, receipt)

    def test_projection_rows_cover_snapshot(self):
        bundle = projection.build_projection_bundle(self.snapshot, self.receipt)
        self.assertEqual(len(bundle["objectRows"]), len(self.snapshot["objects"]))
        self.assertEqual(len(bundle["relationRows"]), len(self.snapshot["relations"]))
        self.assertTrue(all(row["snapshotDigest"] == bundle["source"]["snapshotDigest"] for row in bundle["objectRows"]))

    def test_sql_projection_is_read_only_for_consumers(self):
        sql = (HERE / "sql" / "001_ontology_projection.sql").read_text(encoding="utf-8").lower()
        for table in ("snapshots", "objects", "relations"):
            self.assertIn(f"alter table ontology_projection.{table} enable row level security", sql)
        self.assertNotIn("grant insert", sql)
        self.assertNotIn("grant update", sql)
        self.assertNotIn("grant delete", sql)
        self.assertNotIn("security definer", sql)
        self.assertIn("grant select", sql)
        self.assertIn("never a canonical ontology", sql)


if __name__ == "__main__":
    unittest.main(verbosity=2)
