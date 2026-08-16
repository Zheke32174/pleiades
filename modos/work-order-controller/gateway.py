"""Semantic GPT-facing gateway over the bounded durable controller.

This module exposes only typed supervisory verbs. It has no shell, script,
credential, filesystem, or network execution surface.
"""
from __future__ import annotations
from typing import Any
from controller import InvalidRequest, NotFound, WorkOrderController

class ToolUnavailable(InvalidRequest):
 """The connector verb exists in the contract but its safe backend is absent."""

class AutonomyGateway:
 TOOL_SURFACE=("inspect_ecology","create_work_order","get_work_order","approve_stage","cancel_work_order","apply_scoped_change","manage_service","collect_evidence","restore_checkpoint")
 IMPLEMENTED={"inspect_ecology","create_work_order","get_work_order","cancel_work_order","collect_evidence"}
 def __init__(self,controller:WorkOrderController,*,caller_principal_id:str,mind_id:str):
  if not caller_principal_id or not mind_id:raise InvalidRequest("caller principal and mind binding required")
  self.controller=controller;self.caller_principal_id=caller_principal_id;self.mind_id=mind_id
 def inspect_ecology(self,*,states:tuple[str,...]|None=None)->dict[str,Any]:
  work=[x for x in self.controller.list_work_orders(states) if x['mindId']==self.mind_id]
  return {'mindId':self.mind_id,'callerPrincipalId':self.caller_principal_id,'availableTools':sorted(self.IMPLEMENTED),'unavailableTools':sorted(set(self.TOOL_SURFACE)-self.IMPLEMENTED),'capabilities':self.controller.list_capabilities(),'workOrders':work}
 def create_work_order(self,request:dict[str,Any])->dict[str,Any]:
  meta=request.get('metadata',{})
  if meta.get('mindId')!=self.mind_id:raise InvalidRequest("work order mind binding mismatch")
  if meta.get('requesterPrincipalId')!=self.caller_principal_id:raise InvalidRequest("work order caller binding mismatch")
  return self.controller.create_work_order(request)
 def get_work_order(self,work_order_id:str)->dict[str,Any]:
  order=self.controller.get_work_order(work_order_id);self._assert_visible(order)
  return {**order,'transitionHistory':self.controller.transition_history(work_order_id)}
 def cancel_work_order(self,work_order_id:str,*,reason:str)->dict[str,Any]:
  order=self.controller.get_work_order(work_order_id);self._assert_visible(order)
  if not reason:raise InvalidRequest("cancellation reason required")
  return self.controller.cancel(work_order_id,actor_principal_id=self.caller_principal_id,reason=reason)
 def collect_evidence(self,work_order_id:str)->dict[str,Any]:
  order=self.controller.get_work_order(work_order_id);self._assert_visible(order)
  return {'workOrderId':work_order_id,'mindId':self.mind_id,'actionReceipts':self.controller.action_receipts(work_order_id),'transitionHistory':self.controller.transition_history(work_order_id)}
 def approve_stage(self,*_:Any,**__:Any)->None:self._unavailable('approve_stage','exact stage approval store is not implemented')
 def apply_scoped_change(self,*_:Any,**__:Any)->None:self._unavailable('apply_scoped_change','scoped mutation executor is not implemented')
 def manage_service(self,*_:Any,**__:Any)->None:self._unavailable('manage_service','PDK service adapter is not implemented')
 def restore_checkpoint(self,*_:Any,**__:Any)->None:self._unavailable('restore_checkpoint','restore-tested recovery backend is not implemented')
 def _assert_visible(self,order:dict[str,Any])->None:
  if order['mindId']!=self.mind_id:raise NotFound(order['workOrderId'])
 @staticmethod
 def _unavailable(tool:str,reason:str)->None:raise ToolUnavailable(f"{tool} unavailable: {reason}")
