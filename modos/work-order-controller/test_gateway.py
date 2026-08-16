import tempfile,unittest
from pathlib import Path
from controller import Capability,InvalidRequest,WorkOrderController
from gateway import AutonomyGateway,ToolUnavailable
from test_smoke import req

class GatewayTests(unittest.TestCase):
 def test_typed_surface_and_bindings(self):
  with tempfile.TemporaryDirectory() as d:
   c=WorkOrderController(Path(d)/"db");c.register_capability(Capability("repository.test-and-report","1.0.0",("test",),"operate"));g=AutonomyGateway(c,caller_principal_id="principal:gateway",mind_id="mind:pleiades")
   self.assertEqual(g.inspect_ecology()["capabilities"][0]["capabilityId"],"repository.test-and-report");self.assertEqual(g.create_work_order(req())["state"],"admitted");self.assertEqual(g.cancel_work_order("wo:1",reason="stop")["state"],"canceled");self.assertFalse(hasattr(g,"run_command"));c.close()
 def test_mismatch_and_unavailable_mutation_fail_closed(self):
  with tempfile.TemporaryDirectory() as d:
   c=WorkOrderController(Path(d)/"db");c.register_capability(Capability("repository.test-and-report","1.0.0",("test",),"operate"));g=AutonomyGateway(c,caller_principal_id="principal:gateway",mind_id="mind:pleiades");x=req();x["metadata"]["mindId"]="mind:other"
   with self.assertRaises(InvalidRequest):g.create_work_order(x)
   with self.assertRaises(ToolUnavailable):g.manage_service()
   c.close()
