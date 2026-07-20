import tempfile,unittest
from pathlib import Path
from controller import Capability,IdempotencyConflict,InvalidRequest,WorkOrderController

def req(wid="wo:1"):
 return {"apiVersion":"modos.pleiades/v1alpha1","kind":"WorkOrder","metadata":{"workOrderId":wid,"mindId":"mind:pleiades","requesterPrincipalId":"principal:gateway","idempotencyKey":"idem:1"},"capability":{"capabilityId":"repository.test-and-report","capabilityVersion":"1.0.0","requestedOperation":"test"},"constraints":{"riskCeiling":"operate","canonicalWrite":False},"isolation":{"required":True,"mode":"ghost"},"checkpointPolicy":{"beforeCanonicalMutation":True,"restoreTestRequired":True},"approvalPolicy":{"canonicalMutation":"forbidden"}}
class Smoke(unittest.TestCase):
 def test_durable_bounded_controller(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/"db";c=WorkOrderController(path);c.register_capability(Capability("repository.test-and-report","1.0.0",("test",),"operate"));a=c.create_work_order(req());self.assertEqual(a,c.create_work_order(req()))
   with self.assertRaises(IdempotencyConflict):c.create_work_order(req("wo:2"))
   c.transition("wo:1","preparing",actor_principal_id="controller:1",reason="ready",operation_token="prepare");c.close();c=WorkOrderController(path);self.assertEqual(c.get_work_order("wo:1")["state"],"preparing");c.close()
 def test_forbidden_authority(self):
  with tempfile.TemporaryDirectory() as d:
   c=WorkOrderController(Path(d)/"db");c.register_capability(Capability("repository.test-and-report","1.0.0",("test",),"operate"));x=req();x["constraints"]["riskCeiling"]="external-sovereign"
   with self.assertRaises(InvalidRequest):c.create_work_order(x)
   with self.assertRaises(InvalidRequest):c.register_capability(Capability("host.shell","1.0.0",("run",),"operate",arbitrary_shell=True))
   c.close()
