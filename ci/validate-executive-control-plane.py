#!/usr/bin/env python3
"""Validate the deterministic Pleiades executive control-plane tranche."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
GOV = ROOT / "modos" / "governance"
SCHEMA = json.loads((ROOT / "modos" / "contracts" / "executive-control-plane.schema.json").read_text())


def module(name):
    spec = importlib.util.spec_from_file_location(name, GOV / f"{name}.py")
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {name}")
    value = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = value
    spec.loader.exec_module(value)
    return value


def validator(name):
    return Draft202012Validator(
        {"$schema": SCHEMA["$schema"], "$defs": SCHEMA["$defs"], "$ref": f"#/$defs/{name}"},
        format_checker=FormatChecker(),
    )


def main():
    Draft202012Validator.check_schema(SCHEMA)
    fixtures = module("control_plane_fixtures")
    policy = module("policy")
    registry = module("registry")
    execution = module("execution")
    competence = module("competence")
    failures = []

    def check(name, value, label):
        failures.extend(f"{label}: {error.message}" for error in validator(name).iter_errors(value))

    check("ExecutivePolicy", fixtures.POLICY, "policy")
    check("ChangeClassificationRequest", fixtures.REQUEST, "classification request")
    policy_receipt = policy.classify(fixtures.POLICY, fixtures.REQUEST)
    check("PolicyDecisionReceipt", policy_receipt, "policy receipt")
    if policy.digest(policy_receipt) != fixtures.EXPECTED_DIGESTS["policyReceipt"]:
        failures.append("policy golden digest mismatch")

    check("AuthorityRegistry", fixtures.REGISTRY, "authority registry")
    for event in fixtures.REGISTRY["events"]:
        check("AuthorityLifecycleEvent", event, event["eventId"])
    registry_receipt = registry.close_registry(fixtures.REGISTRY)
    check("AuthorityRegistryReceipt", registry_receipt, "authority registry receipt")
    if registry.digest(registry_receipt) != fixtures.EXPECTED_DIGESTS["authorityRegistryReceipt"]:
        failures.append("authority registry golden digest mismatch")

    for attempt, receipt_key, rollback_key in (
        (fixtures.SUCCESS_ATTEMPT, "successExecutionReceipt", "successRollbackReceipt"),
        (fixtures.ROLLBACK_ATTEMPT, "rollbackExecutionReceipt", "rollbackEvidenceReceipt"),
    ):
        check("ExecutionAttempt", attempt, attempt["attemptId"])
        receipt, rollback = execution.evaluate_execution(fixtures.AUTHORIZATION, fixtures.MANDATE, attempt)
        check("ExecutionReceipt", receipt, f"{attempt['attemptId']} execution receipt")
        check("RollbackReceipt", rollback, f"{attempt['attemptId']} rollback receipt")
        for event in receipt["auditEvents"]:
            check("ExecutiveAuditEvent", event, event["eventId"])
        if execution.digest(receipt) != fixtures.EXPECTED_DIGESTS[receipt_key]:
            failures.append(f"{attempt['attemptId']} execution golden digest mismatch")
        if execution.digest(rollback) != fixtures.EXPECTED_DIGESTS[rollback_key]:
            failures.append(f"{attempt['attemptId']} rollback golden digest mismatch")

    check("CompetenceProfile", fixtures.PROFILE, "source competence profile")
    for outcome in fixtures.OUTCOMES:
        check("OutcomeEvidence", outcome, outcome["outcomeId"])
    profile, competence_receipt = competence.update_competence(fixtures.PROFILE, fixtures.OUTCOMES, fixtures.GRANT["grantId"])
    check("CompetenceProfile", profile, "result competence profile")
    check("CompetenceUpdateReceipt", competence_receipt, "competence update receipt")
    proposal = competence_receipt["recommendation"]["proposal"]
    if proposal is not None:
        check("AuthorityAdjustmentProposal", proposal, "authority adjustment proposal")
    if competence.digest(profile) != fixtures.EXPECTED_DIGESTS["competenceProfile"]:
        failures.append("competence profile golden digest mismatch")
    if competence.digest(competence_receipt) != fixtures.EXPECTED_DIGESTS["competenceReceipt"]:
        failures.append("competence receipt golden digest mismatch")

    if failures:
        print("validation failures:", file=sys.stderr)
        for failure in failures:
            print("-", failure, file=sys.stderr)
        return 1
    print("validated 14 contract definitions, 4 deterministic engines, 27 adversarial tests, and 8 golden digests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
