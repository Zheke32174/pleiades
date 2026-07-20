#!/usr/bin/env python3
from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load_module(name):
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


policy = load_module("policy")
registry = load_module("registry")
execution = load_module("execution")
competence = load_module("competence")
fixtures = load_module("control_plane_fixtures")


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.policy = copy.deepcopy(fixtures.POLICY)
        self.request = copy.deepcopy(fixtures.REQUEST)

    def test_machine_executive(self):
        receipt = policy.classify(self.policy, self.request)
        self.assertEqual(receipt["authorization"]["mode"], "delegated-machine-executive")
        self.assertEqual(receipt["authorization"]["requiredHumanApprovals"], 0)

    def test_reserved_power(self):
        self.request["action"] = "expand-own-authority"
        receipt = policy.classify(self.policy, self.request)
        self.assertTrue(receipt["classification"]["reservedPower"])
        self.assertEqual(receipt["authorization"]["mode"], "human-steward")

    def test_wildcard_rejected(self):
        self.policy["rules"][0]["match"]["domains"] = ["*"]
        with self.assertRaisesRegex(policy.PolicyError, "wildcard"):
            policy.classify(self.policy, self.request)

    def test_machine_human_mix_rejected(self):
        self.policy["rules"][1]["decision"]["requiredHumanApprovals"] = 1
        with self.assertRaisesRegex(policy.PolicyError, "zero humans"):
            policy.classify(self.policy, self.request)

    def test_no_match_rejected(self):
        self.request["domain"] = "unknown"
        with self.assertRaisesRegex(policy.PolicyError, "no executive policy rule"):
            policy.classify(self.policy, self.request)

    def test_golden(self):
        receipt = policy.classify(self.policy, self.request)
        self.assertEqual(policy.digest(receipt), fixtures.EXPECTED_DIGESTS["policyReceipt"])


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.value = copy.deepcopy(fixtures.REGISTRY)

    def test_issued_active(self):
        receipt = registry.close_registry(self.value)
        self.assertEqual(receipt["activeGrantRefs"], ["grant:mind-pleiades:ontology-bounded-v1@1"])

    def test_suspension(self):
        self.value["events"].append({
            "apiVersion": fixtures.API,
            "kind": "AuthorityLifecycleEvent",
            "eventId": "suspend",
            "grantRef": fixtures.GRANT["grantId"],
            "grantGeneration": 1,
            "eventType": "suspended",
            "effectiveAt": "2026-07-20T21:00:00Z",
            "actor": {"principalRef": "sovereign:test", "principalType": "institution", "authoritySourceDigest": fixtures.sha("e")},
            "reasonDigest": fixtures.sha("f"),
        })
        receipt = registry.close_registry(self.value)
        self.assertFalse(receipt["activeGrantRefs"])
        self.assertEqual(receipt["inactiveGrants"][0]["reason"], "suspended")

    def test_self_issue_rejected(self):
        self.value["events"][0]["actor"]["principalRef"] = "mind:pleiades"
        with self.assertRaisesRegex(registry.AuthorityRegistryError, "self-issued"):
            registry.close_registry(self.value)

    def test_revocation_terminal(self):
        self.value["events"].extend([
            {"apiVersion": fixtures.API, "kind": "AuthorityLifecycleEvent", "eventId": "revoke", "grantRef": fixtures.GRANT["grantId"], "grantGeneration": 1, "eventType": "revoked", "effectiveAt": "2026-07-20T21:00:00Z", "actor": {"principalRef": "sovereign:test", "principalType": "institution", "authoritySourceDigest": fixtures.sha("e")}, "reasonDigest": fixtures.sha("f")},
            {"apiVersion": fixtures.API, "kind": "AuthorityLifecycleEvent", "eventId": "resume", "grantRef": fixtures.GRANT["grantId"], "grantGeneration": 1, "eventType": "resumed", "effectiveAt": "2026-07-20T21:30:00Z", "actor": {"principalRef": "sovereign:test", "principalType": "institution", "authoritySourceDigest": fixtures.sha("e")}, "reasonDigest": fixtures.sha("f")},
        ])
        with self.assertRaisesRegex(registry.AuthorityRegistryError, "after revocation"):
            registry.close_registry(self.value)

    def test_expiry(self):
        self.value["evaluationAt"] = "2028-01-01T00:00:00Z"
        receipt = registry.close_registry(self.value)
        self.assertEqual(receipt["inactiveGrants"][0]["reason"], "expired")

    def test_golden(self):
        receipt = registry.close_registry(self.value)
        self.assertEqual(registry.digest(receipt), fixtures.EXPECTED_DIGESTS["authorityRegistryReceipt"])


class ExecutionTests(unittest.TestCase):
    def setUp(self):
        self.auth = copy.deepcopy(fixtures.AUTHORIZATION)
        self.mandate = copy.deepcopy(fixtures.MANDATE)
        self.attempt = copy.deepcopy(fixtures.SUCCESS_ATTEMPT)

    def test_success(self):
        receipt, rollback = execution.evaluate_execution(self.auth, self.mandate, self.attempt)
        self.assertEqual(receipt["status"], "succeeded")
        self.assertEqual(rollback["status"], "not-required")

    def test_rollback(self):
        receipt, rollback = execution.evaluate_execution(self.auth, self.mandate, copy.deepcopy(fixtures.ROLLBACK_ATTEMPT))
        self.assertEqual(receipt["status"], "rolled-back")
        self.assertEqual(rollback["status"], "succeeded")

    def test_executor_mismatch(self):
        self.attempt["executorRef"] = "service:wrong"
        with self.assertRaisesRegex(execution.ExecutionEvidenceError, "executor"):
            execution.evaluate_execution(self.auth, self.mandate, self.attempt)

    def test_expired(self):
        self.attempt["completedAt"] = "2027-01-01T00:00:00Z"
        with self.assertRaisesRegex(execution.ExecutionEvidenceError, "expired"):
            execution.evaluate_execution(self.auth, self.mandate, self.attempt)

    def test_write_budget(self):
        self.attempt["resourceUsage"]["writeOperations"] = 2
        with self.assertRaisesRegex(execution.ExecutionEvidenceError, "write operations"):
            execution.evaluate_execution(self.auth, self.mandate, self.attempt)

    def test_failed_rollback(self):
        attempt = copy.deepcopy(fixtures.ROLLBACK_ATTEMPT)
        attempt["rollback"]["succeeded"] = False
        receipt, rollback = execution.evaluate_execution(self.auth, self.mandate, attempt)
        self.assertEqual(receipt["status"], "failed")
        self.assertEqual(rollback["status"], "failed")

    def test_golden_success(self):
        receipt, rollback = execution.evaluate_execution(self.auth, self.mandate, self.attempt)
        self.assertEqual(execution.digest(receipt), fixtures.EXPECTED_DIGESTS["successExecutionReceipt"])
        self.assertEqual(execution.digest(rollback), fixtures.EXPECTED_DIGESTS["successRollbackReceipt"])

    def test_golden_rollback(self):
        receipt, rollback = execution.evaluate_execution(self.auth, self.mandate, copy.deepcopy(fixtures.ROLLBACK_ATTEMPT))
        self.assertEqual(execution.digest(receipt), fixtures.EXPECTED_DIGESTS["rollbackExecutionReceipt"])
        self.assertEqual(execution.digest(rollback), fixtures.EXPECTED_DIGESTS["rollbackEvidenceReceipt"])


class CompetenceTests(unittest.TestCase):
    def setUp(self):
        self.profile = copy.deepcopy(fixtures.PROFILE)
        self.outcomes = copy.deepcopy(fixtures.OUTCOMES)

    def test_growth_proposal_only(self):
        profile, receipt = competence.update_competence(self.profile, self.outcomes, "grant:test")
        self.assertEqual(receipt["recommendation"]["action"], "grow")
        self.assertFalse(receipt["authority"]["grantMutationApplied"])
        self.assertEqual(profile["counts"]["succeeded"], 10)

    def test_self_verification(self):
        self.outcomes[0]["verifierRef"] = "mind:pleiades"
        with self.assertRaisesRegex(competence.CompetenceError, "self-verified"):
            competence.update_competence(self.profile, self.outcomes, "grant:test")

    def test_policy_violation_suspends(self):
        outcomes = [copy.deepcopy(self.outcomes[0])]
        outcomes[0]["result"] = "policy-violation"
        _, receipt = competence.update_competence(self.profile, outcomes, "grant:test")
        self.assertEqual(receipt["recommendation"]["action"], "suspend")

    def test_small_sample_maintains(self):
        _, receipt = competence.update_competence(self.profile, self.outcomes[:2], "grant:test")
        self.assertEqual(receipt["recommendation"]["action"], "maintain")

    def test_duplicate_outcome(self):
        with self.assertRaisesRegex(competence.CompetenceError, "unique"):
            competence.update_competence(self.profile, [self.outcomes[0], copy.deepcopy(self.outcomes[0])], "grant:test")

    def test_domain_mismatch(self):
        self.outcomes[0]["domain"] = "runtime"
        with self.assertRaisesRegex(competence.CompetenceError, "domain"):
            competence.update_competence(self.profile, [self.outcomes[0]], "grant:test")

    def test_golden(self):
        profile, receipt = competence.update_competence(self.profile, self.outcomes, fixtures.GRANT["grantId"])
        self.assertEqual(competence.digest(profile), fixtures.EXPECTED_DIGESTS["competenceProfile"])
        self.assertEqual(competence.digest(receipt), fixtures.EXPECTED_DIGESTS["competenceReceipt"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
