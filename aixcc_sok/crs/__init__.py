"""
AIxCC SoK — CRS Reference Scaffold
Paper: https://arxiv.org/abs/2602.07666

§3 — "four CRS capabilities: Full Scan, Delta Scan, SARIF Review, Report Synthesis"
§6 — Taxonomy of techniques across 7 finalist teams

Public API:
    from crs.pipeline import CRSOrchestrator, Challenge, ScanMode
    from crs.pov_generation import PoVGenerationModule
    from crs.patch_generation import PatchGenerationModule
    from crs.sarif_validation import SARIFValidationModule
    from crs.bundling import Bundler
    from crs.taxonomy import FINALIST_TEAMS, technique_adoption_rate
"""

from aixcc_sok.crs.pipeline import CRSOrchestrator, Challenge, ScanMode, CRSResult
from aixcc_sok.crs.taxonomy import FINALIST_TEAMS, technique_adoption_rate

__all__ = [
    "CRSOrchestrator",
    "Challenge",
    "ScanMode",
    "CRSResult",
    "FINALIST_TEAMS",
    "technique_adoption_rate",
]
