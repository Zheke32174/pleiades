#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import tarfile
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MODULE_PATH = ROOT / "ci" / "build-modos-validation-package.py"
spec = importlib.util.spec_from_file_location("build_modos_validation_package", MODULE_PATH)
assert spec and spec.loader
package_builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(package_builder)


class ValidationPackageTests(unittest.TestCase):
    def setUp(self):
        self.commit = "a" * 40
        self.schema = json.loads((ROOT / "modos" / "contracts" / "validation-package.schema.json").read_text())

    def build(self, directory: Path, name: str):
        output = directory / name
        receipt = package_builder.build(ROOT, output, self.commit)
        return output, receipt

    def test_two_builds_are_byte_identical(self):
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            first, first_receipt = self.build(directory, "first.tar.gz")
            second, second_receipt = self.build(directory, "second.tar.gz")
            self.assertEqual(first.read_bytes(), second.read_bytes())
            self.assertEqual(first_receipt, second_receipt)

    def test_package_contains_handoff_and_operational_trust_checkpoints(self):
        with tempfile.TemporaryDirectory() as raw:
            output, receipt = self.build(Path(raw), "package.tar.gz")
            with tarfile.open(output, mode="r:gz") as archive:
                names = set(archive.getnames())
                self.assertIn("PACKAGE_MANIFEST.json", names)
                self.assertIn("PACKAGE_SBOM.cdx.json", names)
                self.assertIn("modos/handoff/intake.py", names)
                self.assertIn("modos/handoff/packet.py", names)
                self.assertIn("modos/trust/evidence.py", names)
                self.assertIn("modos/trust/preflight.py", names)
                self.assertIn("modos/contracts/operator-input-candidate.schema.json", names)
                self.assertIn("modos/contracts/operator-handoff-packet.schema.json", names)
                self.assertIn("modos/contracts/operational-authority-registry.schema.json", names)
                self.assertIn("modos/contracts/evidence-attestation.schema.json", names)
                self.assertIn("modos/contracts/transition-preflight-receipt.schema.json", names)
                self.assertIn("modos/ECOLOGY_PROGRESSION_300.md", names)
                self.assertIn("modos/ECOLOGY_PROGRESSION_400.md", names)
                manifest = json.load(archive.extractfile("PACKAGE_MANIFEST.json"))
                sbom = json.load(archive.extractfile("PACKAGE_SBOM.cdx.json"))
            Draft202012Validator(self.schema).validate(manifest)
            Draft202012Validator(self.schema).validate(sbom)
            Draft202012Validator(self.schema).validate(receipt)
            self.assertEqual(sbom["bomFormat"], "CycloneDX")
            self.assertFalse(receipt["networkResolutionAllowed"])
            self.assertFalse(receipt["privateMaterialIncluded"])

    def test_archive_metadata_is_normalized(self):
        with tempfile.TemporaryDirectory() as raw:
            output, _ = self.build(Path(raw), "package.tar.gz")
            with tarfile.open(output, mode="r:gz") as archive:
                for member in archive.getmembers():
                    self.assertEqual(member.mtime, 0)
                    self.assertEqual(member.uid, 0)
                    self.assertEqual(member.gid, 0)
                    self.assertEqual(member.uname, "")
                    self.assertEqual(member.gname, "")

    def test_package_excludes_private_and_generated_surfaces(self):
        with tempfile.TemporaryDirectory() as raw:
            output, _ = self.build(Path(raw), "package.tar.gz")
            with tarfile.open(output, mode="r:gz") as archive:
                names = archive.getnames()
            self.assertFalse(any("/.git/" in f"/{name}/" for name in names))
            self.assertFalse(any("/artifacts/" in f"/{name}/" for name in names))
            self.assertFalse(any("private-key" in name.lower() for name in names))
            self.assertFalse(any("undergrowth" in name.lower() for name in names))

    def test_manifest_file_count_matches_package_sources(self):
        with tempfile.TemporaryDirectory() as raw:
            output, receipt = self.build(Path(raw), "package.tar.gz")
            with tarfile.open(output, mode="r:gz") as archive:
                manifest = json.load(archive.extractfile("PACKAGE_MANIFEST.json"))
            self.assertEqual(manifest["fileCount"], len(manifest["files"]))
            self.assertEqual(receipt["fileCount"], manifest["fileCount"])
            self.assertGreater(manifest["fileCount"], 20)


if __name__ == "__main__":
    unittest.main(verbosity=2)
