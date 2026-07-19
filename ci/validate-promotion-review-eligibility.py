#!/usr/bin/env python3
"""Validate MODOS promotion review-eligibility bundle contracts."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def sha256_id(value: Any) -> str:
    return f"sha256:{hashlib.sha256(canonical_bytes(value)).hexdigest()}"


def contains_float(value: Any) -> bool:
    if isinstance(value, float):
        return True
    if isinstance(value, dict):
        return any(contains_float(item) for item in value.values())
    if isinstance(value, list):
        return any(contains_float(item) for item in value)
    return False


def observation_digest(observation: dict[str, Any]) -> str:
    material = copy.deepcopy(observation)
    material["contentDigest"] = ""
    return sha256_id(material)


def evaluation_input_digest(instance: dict[str, Any]) -> str:
    evaluation = instance["evaluation"]
    material = {
        "runManifest": instance["runManifest"],
        "observations": instance["observations"],
        "evaluationInputs": {
            "criterionResults": evaluation["criterionResults"],
            "reproducibilityMicros": evaluation["reproducibilityMicros"],
            "reproducibilityEvidenceRefs": evaluation[
                "reproducibilityEvidenceRefs"
            ],
            "rollbackTested": evaluation["rollbackTested"],
            "rollbackEvidenceRefs": evaluation["rollbackEvidenceRefs"],
            "safetyViolations": evaluation["safetyViolations"],
            "safetyEvidenceRefs": evaluation["safetyEvidenceRefs"],
        },
    }
    return sha256_id(material)


def evaluation_decision_digest(evaluation: dict[str, Any]) -> str:
    material = copy.deepcopy(evaluation)
    material["decisionDigest"] = ""
    return sha256_id(material)


def bundle_digest(instance: dict[str, Any]) -> str:
    material = copy.deepcopy(instance)
    material["integrity"]["bundleDigest"] = ""
    return sha256_id(material)


def semantic_errors(instance: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if contains_float(instance):
        errors.append(
            "review-eligibility bundle cannot contain floating-point values"
        )

    metadata = instance["metadata"]
    manifest = instance["runManifest"]
    observations = instance["observations"]
    evaluation = instance["evaluation"]

    if metadata["runId"] != manifest["runId"]:
        errors.append("metadata runId must match runManifest runId")
    if parse_time(metadata["createdAt"]) < parse_time(manifest["createdAt"]):
        errors.append("bundle createdAt cannot precede run creation")
    if parse_time(evaluation["evaluatedAt"]) < parse_time(
        manifest["createdAt"]
    ):
        errors.append("evaluation cannot precede run creation")

    if metadata["generation"] == 1 and "previousEvaluationDigest" in metadata:
        errors.append("generation one must not claim a previous evaluation")
    if (
        metadata["generation"] > 1
        and "previousEvaluationDigest" not in metadata
    ):
        errors.append("later generations require previousEvaluationDigest")
    if metadata.get("previousEvaluationDigest") == evaluation[
        "decisionDigest"
    ]:
        errors.append("evaluation cannot name itself as its previous generation")

    criteria = manifest["criteria"]
    criterion_by_id: dict[str, dict[str, Any]] = {}
    for criterion in criteria:
        criterion_id = criterion["id"]
        if criterion_id in criterion_by_id:
            errors.append(f"duplicate manifest criterion: {criterion_id}")
        criterion_by_id[criterion_id] = criterion

    observation_by_digest: dict[str, dict[str, Any]] = {}
    observation_ids: set[str] = set()
    observation_digests_by_criterion: dict[str, list[str]] = {
        criterion_id: [] for criterion_id in criterion_by_id
    }
    superseded_targets: set[str] = set()

    for observation in observations:
        observation_id = observation["observationId"]
        criterion_id = observation["criterionId"]
        digest = observation["contentDigest"]

        if observation_id in observation_ids:
            errors.append(f"duplicate observationId: {observation_id}")
        observation_ids.add(observation_id)

        if criterion_id not in criterion_by_id:
            errors.append(
                f"observation references unknown criterion: {criterion_id}"
            )
        else:
            observation_digests_by_criterion[criterion_id].append(digest)

        if observation["workOrderDigest"] != manifest["workOrderDigest"]:
            errors.append(
                f"observation work-order digest mismatch: {observation_id}"
            )
        if parse_time(observation["recordedAt"]) < parse_time(
            manifest["createdAt"]
        ):
            errors.append(f"observation predates run: {observation_id}")
        if digest != observation_digest(observation):
            errors.append(
                f"observation content digest mismatch: {observation_id}"
            )
        if digest in observation_by_digest:
            errors.append(f"duplicate observation content digest: {digest}")

        supersedes = observation.get("supersedesObservationDigest")
        if supersedes:
            prior = observation_by_digest.get(supersedes)
            if prior is None:
                errors.append(
                    "observation supersession must reference an earlier "
                    f"bundle record: {observation_id}"
                )
            elif prior["criterionId"] != criterion_id:
                errors.append(
                    "observation supersession must remain within one "
                    f"criterion: {observation_id}"
                )
            if supersedes in superseded_targets:
                errors.append(
                    f"observation is superseded more than once: {supersedes}"
                )
            superseded_targets.add(supersedes)

        observation_by_digest[digest] = observation

    result_by_id: dict[str, dict[str, Any]] = {}
    for result in evaluation["criterionResults"]:
        criterion_id = result["criterionId"]
        if criterion_id in result_by_id:
            errors.append(f"duplicate criterion result: {criterion_id}")
        result_by_id[criterion_id] = result

    if set(result_by_id) != set(criterion_by_id):
        errors.append("criterion results must exactly cover manifest criteria")

    expected_blockers: list[str] = []
    for criterion in criteria:
        criterion_id = criterion["id"]
        result = result_by_id.get(criterion_id)
        if result is None:
            continue

        if result["thresholdMicros"] != criterion["thresholdMicros"]:
            errors.append(f"criterion threshold drift: {criterion_id}")

        expected_digests = observation_digests_by_criterion.get(
            criterion_id, []
        )
        if result["selectedObservationDigests"] != expected_digests:
            errors.append(
                "all-valid-observations-pass must select every ordered "
                f"observation: {criterion_id}"
            )

        selected = [
            observation_by_digest[digest]
            for digest in expected_digests
            if digest in observation_by_digest
        ]
        if not selected:
            expected_status = "inconclusive"
        elif all(
            item["passed"]
            and item["scoreMicros"] >= criterion["thresholdMicros"]
            and item["independentVerification"]
            for item in selected
        ):
            expected_status = "pass"
        else:
            expected_status = "fail"

        if result["status"] != expected_status:
            errors.append(
                f"criterion result status mismatch for {criterion_id}: "
                f"expected {expected_status}"
            )
        if criterion["required"] and expected_status != "pass":
            expected_blockers.append(f"criterion:{criterion_id}")

    if evaluation["reproducibilityMicros"] < manifest[
        "minimumReproducibilityMicros"
    ]:
        expected_blockers.append("reproducibility")
    if manifest["requireRollback"] and not evaluation["rollbackTested"]:
        expected_blockers.append("rollback-not-tested")
    if evaluation["rollbackTested"] and not evaluation[
        "rollbackEvidenceRefs"
    ]:
        errors.append("tested rollback requires rollback evidence references")
    if evaluation["safetyViolations"]:
        expected_blockers.append("safety-violation")

    if evaluation["blockers"] != expected_blockers:
        errors.append("evaluation blockers do not exactly match derived blockers")

    expected_verdict = (
        "eligible-for-promotion-review" if not expected_blockers else "blocked"
    )
    if evaluation["verdict"] != expected_verdict:
        errors.append(
            f"evaluation verdict must be {expected_verdict} for its evidence"
        )

    if evaluation["inputDigest"] != evaluation_input_digest(instance):
        errors.append("evaluation input digest mismatch")
    if evaluation["decisionDigest"] != evaluation_decision_digest(evaluation):
        errors.append("evaluation decision digest mismatch")
    if instance["integrity"]["bundleDigest"] != bundle_digest(instance):
        errors.append("bundle digest mismatch")

    return errors


def finalized(instance: dict[str, Any]) -> dict[str, Any]:
    value = copy.deepcopy(instance)
    value["evaluation"]["inputDigest"] = evaluation_input_digest(value)
    value["evaluation"]["decisionDigest"] = evaluation_decision_digest(
        value["evaluation"]
    )
    value["integrity"]["bundleDigest"] = bundle_digest(value)
    return value


def make_observation(
    observation_id: str,
    criterion_id: str,
    score_micros: int,
    passed: bool,
    recorded_by: str,
    recorded_at: str,
    evidence_ref: str,
    *,
    work_order_digest: str,
    supersedes: str | None = None,
    correction_reason: str | None = None,
) -> dict[str, Any]:
    value: dict[str, Any] = {
        "observationId": observation_id,
        "criterionId": criterion_id,
        "workOrderDigest": work_order_digest,
        "scoreMicros": score_micros,
        "passed": passed,
        "evidenceRefs": [evidence_ref],
        "recordedBy": recorded_by,
        "recordedAt": recorded_at,
        "independentVerification": True,
        "contentDigest": "",
    }
    if supersedes:
        value["supersedesObservationDigest"] = supersedes
        value["correctionReason"] = correction_reason
    value["contentDigest"] = observation_digest(value)
    return value


def build_cases() -> list[dict[str, Any]]:
    work_digest = "sha256:" + "a" * 64
    criteria = [
        {
            "id": "machine-check",
            "kind": "machine",
            "required": True,
            "thresholdMicros": 900000,
        },
        {
            "id": "steward-check",
            "kind": "steward",
            "required": True,
            "thresholdMicros": 1000000,
        },
        {
            "id": "ordinary-check",
            "kind": "ordinary-person",
            "required": True,
            "thresholdMicros": 750000,
        },
    ]
    observations = [
        make_observation(
            "obs-machine-1",
            "machine-check",
            950000,
            True,
            "ci/run-312",
            "2026-07-19T20:00:00Z",
            "github-actions://run/312",
            work_order_digest=work_digest,
        ),
        make_observation(
            "obs-steward-1",
            "steward-check",
            1000000,
            True,
            "steward/anthony",
            "2026-07-19T20:05:00Z",
            "review://steward/1",
            work_order_digest=work_digest,
        ),
        make_observation(
            "obs-ordinary-1",
            "ordinary-check",
            800000,
            True,
            "study/blind-comparison",
            "2026-07-19T20:10:00Z",
            "comparison://blind/1",
            work_order_digest=work_digest,
        ),
    ]
    eligible = finalized(
        {
            "apiVersion": "modos.pleiades/v1alpha1",
            "kind": "PromotionReviewEligibilityBundle",
            "metadata": {
                "bundleId": "factory-bundle/run-001/generation-1",
                "runId": "run-001",
                "generation": 1,
                "createdAt": "2026-07-19T20:20:00Z",
            },
            "runManifest": {
                "runId": "run-001",
                "workOrderId": "change-v1",
                "workOrderDigest": work_digest,
                "createdAt": "2026-07-19T19:55:00Z",
                "authorityCeiling": "none",
                "aggregationPolicy": "all-valid-observations-pass",
                "criteria": criteria,
                "minimumReproducibilityMicros": 950000,
                "requireRollback": True,
            },
            "observations": observations,
            "evaluation": {
                "evaluationId": "evaluation/run-001/1",
                "evaluatedAt": "2026-07-19T20:15:00Z",
                "evaluatedBy": "factory/evaluator-v1",
                "inputDigest": "",
                "verdict": "eligible-for-promotion-review",
                "criterionResults": [
                    {
                        "criterionId": criterion["id"],
                        "thresholdMicros": criterion["thresholdMicros"],
                        "selectedObservationDigests": [
                            observations[index]["contentDigest"]
                        ],
                        "status": "pass",
                    }
                    for index, criterion in enumerate(criteria)
                ],
                "reproducibilityMicros": 990000,
                "reproducibilityEvidenceRefs": [
                    "reproducibility://attempts/99-of-100"
                ],
                "rollbackTested": True,
                "rollbackEvidenceRefs": ["rollback://fixture/1"],
                "safetyViolations": [],
                "safetyEvidenceRefs": ["safety://scan/1"],
                "blockers": [],
                "authorityCeiling": "none",
                "promotionTransactionRequired": True,
                "decisionDigest": "",
            },
            "integrity": {"bundleDigest": ""},
        }
    )

    blocked_observations = copy.deepcopy(observations)
    blocked_observations[0] = make_observation(
        "obs-machine-fail",
        "machine-check",
        400000,
        False,
        "ci/run-313",
        "2026-07-19T20:00:00Z",
        "github-actions://run/313",
        work_order_digest=work_digest,
    )
    blocked = copy.deepcopy(eligible)
    blocked["metadata"].update(
        {
            "bundleId": "factory-bundle/run-002/generation-1",
            "runId": "run-002",
        }
    )
    blocked["runManifest"]["runId"] = "run-002"
    blocked["observations"] = blocked_observations
    blocked["evaluation"]["evaluationId"] = "evaluation/run-002/1"
    blocked["evaluation"]["criterionResults"][0].update(
        {
            "selectedObservationDigests": [
                blocked_observations[0]["contentDigest"]
            ],
            "status": "fail",
        }
    )
    for index in (1, 2):
        blocked["evaluation"]["criterionResults"][index][
            "selectedObservationDigests"
        ] = [blocked_observations[index]["contentDigest"]]
    blocked["evaluation"].update(
        {
            "reproducibilityMicros": 800000,
            "rollbackTested": False,
            "rollbackEvidenceRefs": [],
            "safetyViolations": ["unexpected-write"],
            "blockers": [
                "criterion:machine-check",
                "reproducibility",
                "rollback-not-tested",
                "safety-violation",
            ],
            "verdict": "blocked",
        }
    )
    blocked = finalized(blocked)

    original_failure = make_observation(
        "obs-machine-original-fail",
        "machine-check",
        500000,
        False,
        "ci/run-314",
        "2026-07-19T20:00:00Z",
        "github-actions://run/314",
        work_order_digest=work_digest,
    )
    correction = make_observation(
        "obs-machine-correction",
        "machine-check",
        980000,
        True,
        "ci/run-315",
        "2026-07-19T20:03:00Z",
        "github-actions://run/315",
        work_order_digest=work_digest,
        supersedes=original_failure["contentDigest"],
        correction_reason="rerun after fixture correction",
    )
    corrected = copy.deepcopy(eligible)
    corrected["metadata"].update(
        {
            "bundleId": "factory-bundle/run-003/generation-1",
            "runId": "run-003",
        }
    )
    corrected["runManifest"]["runId"] = "run-003"
    corrected["observations"] = [
        original_failure,
        correction,
        observations[1],
        observations[2],
    ]
    corrected["evaluation"]["evaluationId"] = "evaluation/run-003/1"
    corrected["evaluation"]["criterionResults"][0].update(
        {
            "selectedObservationDigests": [
                original_failure["contentDigest"],
                correction["contentDigest"],
            ],
            "status": "fail",
        }
    )
    corrected["evaluation"]["criterionResults"][1][
        "selectedObservationDigests"
    ] = [observations[1]["contentDigest"]]
    corrected["evaluation"]["criterionResults"][2][
        "selectedObservationDigests"
    ] = [observations[2]["contentDigest"]]
    corrected["evaluation"].update(
        {
            "blockers": ["criterion:machine-check"],
            "verdict": "blocked",
        }
    )
    corrected = finalized(corrected)

    cases = [
        {
            "name": "eligible bundle requires later promotion transaction",
            "valid": True,
            "instance": eligible,
        },
        {
            "name": "blocked bundle preserves all derived blockers",
            "valid": True,
            "instance": blocked,
        },
        {
            "name": "correction lineage preserves earlier negative evidence",
            "valid": True,
            "instance": corrected,
        },
    ]

    altered = copy.deepcopy(eligible)
    altered["observations"][0]["scoreMicros"] = 960000
    cases.append(
        {
            "name": "altered observation content is rejected",
            "valid": False,
            "instance": altered,
        }
    )

    drifted = copy.deepcopy(eligible)
    drifted["observations"][0]["workOrderDigest"] = "sha256:" + "b" * 64
    drifted["observations"][0]["contentDigest"] = observation_digest(
        drifted["observations"][0]
    )
    drifted["evaluation"]["criterionResults"][0][
        "selectedObservationDigests"
    ] = [drifted["observations"][0]["contentDigest"]]
    cases.append(
        {
            "name": "observation cannot drift from run work order",
            "valid": False,
            "instance": finalized(drifted),
        }
    )

    earlier_failure = make_observation(
        "obs-machine-earlier-fail",
        "machine-check",
        100000,
        False,
        "ci/run-old",
        "2026-07-19T19:59:00Z",
        "github-actions://run/old",
        work_order_digest=work_digest,
    )
    hidden = copy.deepcopy(eligible)
    hidden["observations"] = [earlier_failure, *hidden["observations"]]
    cases.append(
        {
            "name": "later pass cannot hide earlier negative evidence",
            "valid": False,
            "instance": finalized(hidden),
        }
    )

    false_eligible = copy.deepcopy(blocked)
    false_eligible["evaluation"]["verdict"] = (
        "eligible-for-promotion-review"
    )
    cases.append(
        {
            "name": "blocked evidence cannot claim review eligibility",
            "valid": False,
            "instance": finalized(false_eligible),
        }
    )

    missing_previous = copy.deepcopy(eligible)
    missing_previous["metadata"].update(
        {
            "generation": 2,
            "bundleId": "factory-bundle/run-001/generation-2",
        }
    )
    cases.append(
        {
            "name": "later generation requires immutable predecessor",
            "valid": False,
            "instance": finalized(missing_previous),
        }
    )

    self_previous = copy.deepcopy(eligible)
    self_previous["metadata"].update(
        {
            "generation": 2,
            "previousEvaluationDigest": eligible["evaluation"][
                "decisionDigest"
            ],
        }
    )
    cases.append(
        {
            "name": "generation cannot point to its own decision",
            "valid": False,
            "instance": finalized(self_previous),
        }
    )

    no_rollback_evidence = copy.deepcopy(eligible)
    no_rollback_evidence["evaluation"]["rollbackEvidenceRefs"] = []
    cases.append(
        {
            "name": "rollback claim requires evidence references",
            "valid": False,
            "instance": finalized(no_rollback_evidence),
        }
    )

    waiver = copy.deepcopy(eligible)
    waiver["evaluation"]["promotionTransactionRequired"] = False
    cases.append(
        {
            "name": "factory output cannot waive governed promotion",
            "valid": False,
            "instance": finalized(waiver),
        }
    )

    floating = copy.deepcopy(eligible)
    floating["evaluation"]["reproducibilityMicros"] = 0.99
    cases.append(
        {
            "name": "binary floats are excluded from promotion identity",
            "valid": False,
            "instance": floating,
        }
    )

    altered_decision = copy.deepcopy(eligible)
    altered_decision["evaluation"]["decisionDigest"] = (
        "sha256:" + "0" * 64
    )
    altered_decision["integrity"]["bundleDigest"] = bundle_digest(
        altered_decision
    )
    cases.append(
        {
            "name": "altered decision digest is rejected",
            "valid": False,
            "instance": altered_decision,
        }
    )
    return cases


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--schema",
        type=Path,
        default=Path(
            "modos/contracts/promotion-review-eligibility-bundle.schema.json"
        ),
    )
    args = parser.parse_args()
    schema = load_json(args.schema)
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())

    failures: list[str] = []
    cases = build_cases()
    for case in cases:
        shape_errors = sorted(
            validator.iter_errors(case["instance"]),
            key=lambda error: list(error.path),
        )
        semantics = semantic_errors(case["instance"]) if not shape_errors else []
        actual_valid = not shape_errors and not semantics
        if actual_valid != case["valid"]:
            details = [error.message for error in shape_errors] + semantics
            failures.append(
                f"{case['name']}: expected valid={case['valid']}, "
                f"got valid={actual_valid}; " + "; ".join(details)
            )
        else:
            outcome = "accepted" if actual_valid else "rejected"
            print(f"case {outcome}: {case['name']}")

    if failures:
        print("promotion review-eligibility failures:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    print(f"validated schema and {len(cases)} review-eligibility cases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
