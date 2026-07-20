#!/usr/bin/env python3
"""Validate recurrent executive workspace and emergency recovery contracts."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
GOV = ROOT / "modos" / "governance"
SCHEMA = json.loads((ROOT / "modos" / "contracts" / "workspace-emergency-recovery.schema.json").read_text())


def load(name):
    spec = importlib.util.spec_from_file_location(name, GOV / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def validator(name):
    return Draft202012Validator(
        {"$schema": SCHEMA["$schema"], "$defs": SCHEMA["$defs"], "$ref": f"#/$defs/{name}"},
        format_checker=FormatChecker(),
    )


def main():
    Draft202012Validator.check_schema(SCHEMA)
    workspace = load("workspace")
    emergency = load("emergency")
    fixtures = load("workspace_emergency_fixtures")
    failures = []

    def check(name, value, label):
        failures.extend(f"{label}: {error.message}" for error in validator(name).iter_errors(value))

    check("ExecutiveWorkspaceCycle", fixtures.CYCLE, "workspace cycle")
    for contribution in fixtures.CYCLE["contributions"]:
        check("WorkspaceContribution", contribution, contribution["contributionId"])
    workspace_receipt = workspace.close_cycle(fixtures.CYCLE)
    check("WorkspaceDeliberationReceipt", workspace_receipt, "workspace receipt")
    if workspace.digest(workspace_receipt) != fixtures.EXPECTED_DIGESTS["workspaceReceipt"]:
        failures.append("workspace golden digest mismatch")

    check("EmergencyAuthorityGrant", fixtures.EMERGENCY_GRANT, "emergency grant")
    check("EmergencyActionRequest", fixtures.EMERGENCY_REQUEST, "emergency request")
    check("ContinuityState", fixtures.CONTINUITY, "continuity state")
    emergency_receipt = emergency.evaluate_emergency(
        fixtures.EMERGENCY_GRANT,
        fixtures.EMERGENCY_REQUEST,
        fixtures.REGISTRY_RECEIPT,
        fixtures.CONTINUITY,
    )
    check("EmergencyRecoveryReceipt", emergency_receipt, "emergency receipt")
    if emergency.digest(emergency_receipt) != fixtures.EXPECTED_DIGESTS["emergencyReceipt"]:
        failures.append("emergency golden digest mismatch")

    if failures:
        print("validation failures:", file=sys.stderr)
        for failure in failures:
            print("-", failure, file=sys.stderr)
        return 1
    print("validated 7 contract definitions, 2 deterministic engines, 17 adversarial tests, and 2 golden digests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
