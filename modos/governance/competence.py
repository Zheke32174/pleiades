#!/usr/bin/env python3
"""Deterministic competence updater and proposal-only authority adjustment.

Competence is updated only from independently verified outcomes. The module may
emit a proposal to grow, narrow, or suspend authority, but it never mutates a
live grant and never allows a principal to score itself.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Iterable

API_VERSION = "modos.pleiades/v1alpha1"


class CompetenceError(ValueError):
    pass


def _reject_float(value: str) -> None:
    raise CompetenceError(f"floating-point values are forbidden: {value}")


def _reject_constant(value: str) -> None:
    raise CompetenceError(f"non-finite JSON constant is forbidden: {value}")


def _no_duplicate_keys(pairs: Iterable[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CompetenceError(f"duplicate JSON key is forbidden: {key}")
        result[key] = value
    return result


def load_json_strict(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle, parse_float=_reject_float, parse_constant=_reject_constant, object_pairs_hook=_no_duplicate_keys)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_bytes(value)).hexdigest()


def _validate_profile(profile: dict[str, Any]) -> None:
    if profile.get("apiVersion") != API_VERSION or profile.get("kind") != "CompetenceProfile":
        raise CompetenceError("unsupported competence profile envelope")
    if profile.get("authority") != {"selfScored": False, "grantMutationApplied": False}:
        raise CompetenceError("competence profile authority boundary is not exact")
    counts = profile.get("counts")
    if not isinstance(counts, dict) or any(not isinstance(counts.get(key), int) or counts[key] < 0 for key in ("succeeded", "failed", "rolledBack", "policyViolations")):
        raise CompetenceError("competence profile counts are invalid")
    if not isinstance(profile.get("competenceScoreBps"), int) or not 0 <= profile["competenceScoreBps"] <= 10000:
        raise CompetenceError("competence score must use integer basis points")


def update_competence(profile: dict[str, Any], outcomes: list[dict[str, Any]], grant_ref: str) -> tuple[dict[str, Any], dict[str, Any]]:
    _validate_profile(profile)
    if not isinstance(outcomes, list) or not outcomes:
        raise CompetenceError("verified outcome evidence is required")
    updated = copy.deepcopy(profile)
    identities: set[str] = set(updated.get("evidenceRefs", []))
    outcome_digests: list[str] = []
    external_verifiers: set[str] = set()
    for outcome in outcomes:
        if outcome.get("apiVersion") != API_VERSION or outcome.get("kind") != "OutcomeEvidence":
            raise CompetenceError("unsupported outcome evidence envelope")
        outcome_id = outcome.get("outcomeId")
        if not isinstance(outcome_id, str) or not outcome_id or outcome_id in identities:
            raise CompetenceError("outcome evidence ids must be nonempty and unique")
        if outcome.get("principalRef") != profile["principalRef"]:
            raise CompetenceError(f"outcome {outcome_id} principal does not match profile")
        for field in ("domain", "action", "riskTier"):
            if outcome.get(field) != profile[field]:
                raise CompetenceError(f"outcome {outcome_id} {field} does not match profile")
        verification = outcome.get("verification")
        if verification != {"status": "verified", "independent": True}:
            raise CompetenceError(f"outcome {outcome_id} is not independently verified")
        verifier = outcome.get("verifierRef")
        if not isinstance(verifier, str) or not verifier or verifier == profile["principalRef"]:
            raise CompetenceError(f"outcome {outcome_id} cannot be self-verified")
        external_verifiers.add(verifier)
        confidence = outcome.get("confidenceBps")
        if not isinstance(confidence, int) or isinstance(confidence, bool) or not 0 <= confidence <= 10000:
            raise CompetenceError(f"outcome {outcome_id} confidenceBps is invalid")
        result = outcome.get("result")
        if result == "succeeded":
            updated["counts"]["succeeded"] += 1
        elif result == "failed":
            updated["counts"]["failed"] += 1
        elif result == "rolled-back":
            updated["counts"]["rolledBack"] += 1
        elif result == "policy-violation":
            updated["counts"]["policyViolations"] += 1
        else:
            raise CompetenceError(f"outcome {outcome_id} result is unsupported")
        identities.add(outcome_id)
        outcome_digests.append(digest(outcome))
    if not external_verifiers:
        raise CompetenceError("competence update requires an external verifier")
    updated["generation"] += 1
    updated["evidenceRefs"] = sorted(identities)
    counts = updated["counts"]
    score = 5000 + counts["succeeded"] * 450 + counts["rolledBack"] * 100 - counts["failed"] * 700 - counts["policyViolations"] * 3000
    updated["competenceScoreBps"] = max(0, min(10000, score))
    total = sum(counts.values())
    recommendation = "maintain"
    if counts["policyViolations"] > 0:
        recommendation = "suspend"
    elif total >= 5 and counts["failed"] > counts["succeeded"]:
        recommendation = "narrow"
    elif total >= 10 and updated["competenceScoreBps"] >= 8000 and counts["policyViolations"] == 0:
        recommendation = "grow"

    proposal = None
    if recommendation != "maintain":
        proposal = {
            "apiVersion": API_VERSION,
            "kind": "AuthorityAdjustmentProposal",
            "proposalId": f"authority-adjustment:{profile['profileId']}:{updated['generation']}",
            "principalRef": profile["principalRef"],
            "grantRef": grant_ref,
            "adjustment": recommendation,
            "basis": {
                "profileDigest": digest(updated),
                "competenceScoreBps": updated["competenceScoreBps"],
                "verifiedOutcomes": total,
                "reason": {
                    "grow": "verified competence threshold reached",
                    "narrow": "verified failures exceed successes",
                    "suspend": "verified policy violation observed",
                }[recommendation],
            },
            "evidenceRefs": sorted(outcome["outcomeId"] for outcome in outcomes),
            "authority": {"ceiling": "proposal", "grantMutationApplied": False, "externalAuthorizationRequired": True},
        }
    receipt = {
        "apiVersion": API_VERSION,
        "kind": "CompetenceUpdateReceipt",
        "profileId": profile["profileId"],
        "sourceProfileDigest": digest(profile),
        "resultProfileDigest": digest(updated),
        "outcomeDigests": sorted(outcome_digests),
        "recommendation": {"action": recommendation, "proposal": proposal},
        "authority": {"selfScoringApplied": False, "grantMutationApplied": False},
    }
    return updated, receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--outcomes", type=Path, required=True)
    parser.add_argument("--grant-ref", required=True)
    parser.add_argument("--out-profile", type=Path, required=True)
    parser.add_argument("--out-receipt", type=Path, required=True)
    args = parser.parse_args()
    try:
        outcomes = load_json_strict(args.outcomes)
        profile, receipt = update_competence(load_json_strict(args.profile), outcomes, args.grant_ref)
        for path, value in ((args.out_profile, profile), (args.out_receipt, receipt)):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(receipt["recommendation"]["action"])
        return 0
    except (OSError, json.JSONDecodeError, CompetenceError) as exc:
        print(f"competence update failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
