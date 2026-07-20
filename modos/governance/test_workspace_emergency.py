#!/usr/bin/env python3
from __future__ import annotations
import copy, importlib.util, unittest
from pathlib import Path

HERE=Path(__file__).resolve().parent
def load(name):
    spec=importlib.util.spec_from_file_location(name,HERE/f"{name}.py");assert spec and spec.loader
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
workspace=load("workspace"); emergency=load("emergency"); fixtures=load("workspace_emergency_fixtures")

class WorkspaceTests(unittest.TestCase):
    def setUp(self): self.cycle=copy.deepcopy(fixtures.CYCLE)
    def test_polycentric_approval(self):
        receipt=workspace.close_cycle(self.cycle)
        self.assertEqual(receipt["outcome"],"approve")
        self.assertEqual(receipt["authority"]["decisionPrincipal"],"persistent-mind")
    def test_dissent_persisted(self):
        receipt=workspace.close_cycle(self.cycle)
        self.assertIn("contrib:dissent",receipt["unresolvedDissentRefs"])
        self.assertIn("dissent:prior:0001",receipt["unresolvedDissentRefs"])
    def test_independent_first_pass_required(self):
        self.cycle["contributions"][0]["firstPassIndependent"]=False
        with self.assertRaisesRegex(workspace.WorkspaceError,"independent first pass"): workspace.close_cycle(self.cycle)
    def test_all_roles_required(self):
        self.cycle["contributions"][3]["role"]="risk"
        with self.assertRaisesRegex(workspace.WorkspaceError,"requires"): workspace.close_cycle(self.cycle)
    def test_three_principals_required(self):
        for item in self.cycle["contributions"]: item["principalRef"]="model:one"
        with self.assertRaisesRegex(workspace.WorkspaceError,"three distinct"): workspace.close_cycle(self.cycle)
    def test_tie_defers(self):
        self.cycle["contributions"][0].update({"recommendation":"approve","confidenceBps":10000,"competenceWeightBps":1000})
        self.cycle["contributions"][1].update({"recommendation":"reject","confidenceBps":10000,"competenceWeightBps":1000})
        self.cycle["contributions"][2].update({"recommendation":"request-more-evidence","confidenceBps":0})
        self.cycle["contributions"][3].update({"recommendation":"defer","confidenceBps":0})
        self.assertEqual(workspace.close_cycle(self.cycle)["outcome"],"defer")
    def test_competence_weight_capped(self):
        self.cycle["contributions"][0]["competenceWeightBps"]=10000
        receipt=workspace.close_cycle(self.cycle)
        item=next(x for x in receipt["contributions"] if x["contributionId"]=="contrib:proposal")
        self.assertEqual(item["effectiveWeightBps"],4000)
    def test_golden(self):
        self.assertEqual(workspace.digest(workspace.close_cycle(self.cycle)),fixtures.EXPECTED_DIGESTS["workspaceReceipt"])

class EmergencyTests(unittest.TestCase):
    def setUp(self):
        self.grant=copy.deepcopy(fixtures.EMERGENCY_GRANT);self.request=copy.deepcopy(fixtures.EMERGENCY_REQUEST)
        self.registry=copy.deepcopy(fixtures.REGISTRY_RECEIPT);self.continuity=copy.deepcopy(fixtures.CONTINUITY)
    def evaluate(self): return emergency.evaluate_emergency(self.grant,self.request,self.registry,self.continuity)
    def test_containment_authorized(self):
        receipt=self.evaluate()
        self.assertEqual(receipt["status"],"containment-authorized")
        self.assertTrue(receipt["obligations"]["postEventReviewRequired"])
    def test_grant_must_expire_within_hour(self):
        self.grant["expiresAt"]="2026-07-21T00:00:01Z"
        with self.assertRaisesRegex(emergency.EmergencyError,"one hour"): self.evaluate()
    def test_constitutional_power_forbidden(self):
        self.grant["constraints"]["constitutionalMutationAllowed"]=True
        with self.assertRaisesRegex(emergency.EmergencyError,"constraints"): self.evaluate()
    def test_action_outside_grant_rejected(self):
        self.request["action"]="deploy"
        with self.assertRaisesRegex(emergency.EmergencyError,"outside grant"): self.evaluate()
    def test_inactive_grant_rejected(self):
        self.registry["activeGrantRefs"]=[]
        with self.assertRaisesRegex(emergency.EmergencyError,"not active"): self.evaluate()
    def test_revoked_grant_not_rehydrated(self):
        self.continuity["revokedGrantRefs"].append("emergency-grant:pleiades:0001@1")
        with self.assertRaisesRegex(emergency.EmergencyError,"revoked"): self.evaluate()
    def test_degraded_state_enters_safe_mode(self):
        self.continuity["availableMindComponents"]=1
        self.assertEqual(self.evaluate()["status"],"safe-mode-authorized")
    def test_degraded_recovery_requires_quorum(self):
        self.continuity["availableMindComponents"]=1;self.continuity["recoveryQuorumRefs"]=["principal:one"]
        with self.assertRaisesRegex(emergency.EmergencyError,"two quorum"): self.evaluate()
    def test_golden(self):
        self.assertEqual(emergency.digest(self.evaluate()),fixtures.EXPECTED_DIGESTS["emergencyReceipt"])

if __name__=="__main__": unittest.main(verbosity=2)
