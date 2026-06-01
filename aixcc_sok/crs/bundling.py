"""
AIxCC SoK — Bundling Module
Paper: https://arxiv.org/abs/2602.07666

§6.4 — "Bundling pairs PoVs, patches, and SARIF assessments into coherent
vulnerability reports."

§6.4 — "Unlike other submissions with time decay, bundling allows free updates
until the deadline, with scoring based solely on final results."

§6.4 — "A bundle can contain any two of three pairings:
    PoV-Patch, PoV-SARIF, and Patch-SARIF
to form a complete scoring bundle, while any incorrect pairing will penalize
the entire bundle."

§6.4, Table 6 — Team strategies:
    All 7 teams: PoV-Patch from PoV-based patch generation
    5 teams:    PoV-SARIF from SARIF validation results
    2 teams:    Patch-SARIF (TI, FB — only those with No-PoV patch capability)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class Bundle:
    """A vulnerability bundle: correlated PoV + Patch + SARIF for one vulnerability.

    §6.4 — "links related findings for the same vulnerability"
    §3 — Score: [−7, 7] pts — "any incorrect pairing penalizes the entire bundle"
    """

    bundle_id: str
    # §6.4 — PoV-Patch pairing (always attempted — §6.4 "all teams")
    pov_id: Optional[str] = None
    patch_id: Optional[str] = None
    # §6.4 — PoV-SARIF pairing (most teams)
    sarif_report_id: Optional[str] = None
    # §6.4 — which pairings are active
    has_pov_patch: bool = False
    has_pov_sarif: bool = False
    has_patch_sarif: bool = False


class Bundler:
    """§6.4 — Forms bundles from discovered PoVs, patches, and SARIF assessments.

    Risk profile: bundles carry penalty risk, so pairings are derived conservatively
    from existing workflows rather than inferred independently.

    "teams tend to derive pairings from existing workflows rather than inferring
    relationships independently" — [SPECIFIED] design principle for all teams.

    §6.4 — rebundle_on_new_result: True (default) — updates submitted until deadline.
    """

    def __init__(self, config: dict[str, Any]):
        self.config = config
        bundle_cfg = config.get("bundling", {})
        self._do_pov_patch = bundle_cfg.get("pov_patch", True)
        self._do_pov_sarif = bundle_cfg.get("pov_sarif", True)
        # §6.4 — "only teams with No-PoV patch capability can submit Patch-SARIF bundles"
        no_pov = config.get("patch_generation", {}).get("generation", {}).get(
            "no_pov_patch_gen", False
        )
        self._do_patch_sarif = bundle_cfg.get("patch_sarif", False) and no_pov

    async def bundle(self, challenge: Any, result: Any) -> list[Bundle]:
        """§6.4 — Form all valid bundles from a completed challenge result.

        §6.4 — "rebundle on any new result until deadline" when rebundle_on_new_result=True.
        """
        bundles: list[Bundle] = []
        import hashlib, time

        # §6.4 — Pairing 1: PoV-Patch (all teams — natural pairing from PoV-based patch gen)
        if self._do_pov_patch:
            pov_patch_bundles = self._form_pov_patch_bundles(result)
            bundles.extend(pov_patch_bundles)
            logger.info(
                "challenge=%s pov_patch_bundles=%d", challenge.challenge_id, len(pov_patch_bundles)
            )

        # §6.4 — Pairing 2: PoV-SARIF (teams with SARIF validation results)
        if self._do_pov_sarif and result.sarif_assessments:
            pov_sarif_bundles = self._form_pov_sarif_bundles(result)
            bundles.extend(pov_sarif_bundles)
            logger.info(
                "challenge=%s pov_sarif_bundles=%d", challenge.challenge_id, len(pov_sarif_bundles)
            )

        # §6.4 — Pairing 3: Patch-SARIF (only TI, FB — No-PoV patch teams)
        if self._do_patch_sarif and result.sarif_assessments:
            patch_sarif_bundles = self._form_patch_sarif_bundles(result)
            bundles.extend(patch_sarif_bundles)
            logger.info(
                "challenge=%s patch_sarif_bundles=%d",
                challenge.challenge_id, len(patch_sarif_bundles),
            )

        logger.info(
            "challenge=%s total_bundles=%d", challenge.challenge_id, len(bundles)
        )
        return bundles

    def _form_pov_patch_bundles(self, result: Any) -> list[Bundle]:
        """§6.4 — "All teams naturally derive PoV-Patch from PoV-based patch generation."

        Each patch already knows its source_pov_ids from the patch generation phase.
        """
        bundles: list[Bundle] = []
        import hashlib, time

        for patch in result.patches:
            for pov_id in getattr(patch, "source_pov_ids", []):
                bid = hashlib.sha256(
                    f"pov_patch:{pov_id}:{patch.patch_id}".encode()
                ).hexdigest()[:16]
                bundles.append(Bundle(
                    bundle_id=bid,
                    pov_id=pov_id,
                    patch_id=patch.patch_id,
                    has_pov_patch=True,
                ))
        return bundles

    def _form_pov_sarif_bundles(self, result: Any) -> list[Bundle]:
        """§6.4 — "Reuse SARIF validation results for PoV-SARIF."

        Match SARIF Correct assessments to PoVs that share the same vulnerability location.

        §6.4 — "teams either reuse their SARIF validation results (§6.3) or use
        SARIF reports to generate PoVs/patches, pairing them upon success."
        Default: reuse (simpler; all SARIF-active teams did this first).
        """
        bundles: list[Bundle] = []
        import hashlib

        # Only form PoV-SARIF bundles for Correct assessments
        correct_sarif = [
            a for a in result.sarif_assessments
            if getattr(a, "verdict", None) and a.verdict.value == "Correct"
        ]

        for sarif_assessment in correct_sarif:
            # Match to PoVs that cover the same vulnerability
            # [UNSPECIFIED] Exact matching logic not described; using heuristic overlap
            for pov in result.povs:
                if self._pov_covers_sarif(pov, sarif_assessment):
                    bid = hashlib.sha256(
                        f"pov_sarif:{pov.pov_id}:{sarif_assessment.sarif_report_id}".encode()
                    ).hexdigest()[:16]
                    bundles.append(Bundle(
                        bundle_id=bid,
                        pov_id=pov.pov_id,
                        sarif_report_id=sarif_assessment.sarif_report_id,
                        has_pov_sarif=True,
                    ))
                    break  # one PoV per SARIF report is sufficient

        return bundles

    def _form_patch_sarif_bundles(self, result: Any) -> list[Bundle]:
        """§6.4 — Patch-SARIF bundles (TI, FB only — requires No-PoV patch capability).

        "only teams with No-PoV patch capability can submit Patch-SARIF bundles"
        Derived from Bug Candidate DB linking patches to SARIF reports (TI)
        or SARIF-guided patch generation (FB).
        """
        # TODO: Implement Patch-SARIF pairing via bug candidate DB
        # This requires the bug_candidate_db to link patches to SARIF report IDs
        return []

    def _pov_covers_sarif(self, pov: Any, sarif_assessment: Any) -> bool:
        """Heuristic: check if a PoV's crash covers the SARIF report's location.

        §6.3 — "Match Any PoV: matching SARIF locations against crash information"
        [UNSPECIFIED] Exact matching criteria not described; using crash stack heuristic.
        """
        # TODO: Implement robust SARIF location → PoV crash overlap matching
        return False
