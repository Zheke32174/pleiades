#!/usr/bin/env python3
"""Restart-safe bounded MODOS work-order reference controller.

It persists intent and lifecycle state but never executes commands or credentials.
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Iterable
from model import Capability, IdempotencyConflict, InvalidRequest, InvalidTransition, NotFound, RISK_ORDER, TERMINAL, TRANSITIONS, digest
from store import Store

class WorkOrderController:
 def __init__(self,database:str|Path):self.store=Store(database)
 def close(self):self.store.close()
 def __enter__(self):return self
 def __exit__(self,*_):self.close()
 def register_capability(self,c:Capability):
  if c.maximum_risk not in RISK_ORDER:raise InvalidRequest("unknown maximum risk")
  if not c.operations:raise InvalidRequest("operations required")
  if c.arbitrary_shell:raise InvalidRequest("arbitrary shell forbidden")
  if c.external_irreversible_effect:raise InvalidRequest("irreversible external effect forbidden")
  return self.store.put_capability({'capabilityId':c.capability_id,'version':c.version,'operations':sorted(set(c.operations)),'maximumRisk':c.maximum_risk,'canonicalWrite':c.canonical_write})
 def list_capabilities(self):
  return [self._capability_view(x) for x in self.store.capabilities()]
 def create_work_order(self,r:dict[str,Any]):
  self._shape(r);m=r['metadata'];c=r['capability'];x=r['constraints'];d=digest(r)
  old=self.store.by_idempotency(m['idempotencyKey'])
  if old:
   if old['request_digest']!=d:raise IdempotencyConflict("idempotency key differs")
   return self._view(old)
  try:cap=self.store.capability(c['capabilityId'],c['capabilityVersion'])
  except NotFound as exc:raise InvalidRequest("capability not registered") from exc
  if c['requestedOperation'] not in json.loads(cap['operations_json']):raise InvalidRequest("operation not registered")
  risk=x['riskCeiling']
  if risk not in RISK_ORDER:raise InvalidRequest("unknown risk")
  if risk=='external-sovereign':raise InvalidRequest("sovereign effects unreachable")
  if RISK_ORDER[risk]>RISK_ORDER[cap['maximum_risk']]:raise InvalidRequest("risk exceeds capability")
  if x['canonicalWrite'] and not cap['canonical_write']:raise InvalidRequest("canonical write not permitted")
  if x['canonicalWrite']:
   if r['approvalPolicy']['canonicalMutation']=='forbidden':raise InvalidRequest("canonical write requires approval")
   p=r['checkpointPolicy']
   if not p['beforeCanonicalMutation'] or not p['restoreTestRequired']:raise InvalidRequest("restore-tested checkpoint required")
  if r['isolation']['required'] and r['isolation']['mode']=='none':raise InvalidRequest("required isolation cannot be none")
  return self._view(self.store.insert_order(r))
 def get_work_order(self,wid):return self._view(self.store.order(wid))
 def list_work_orders(self,states:Iterable[str]|None=None):return [self._view(x) for x in self.store.orders(states)]
 def transition(self,wid,next_state,*,actor_principal_id,reason,operation_token):
  if not operation_token:raise InvalidRequest("operation token required")
  old=self.store.transition_by_token(operation_token)
  if old:
   if old['work_order_id']!=wid or old['next_state']!=next_state:raise IdempotencyConflict("transition token differs")
   return self.get_work_order(wid)
  row=self.store.order(wid);prior=row['state']
  if prior in TERMINAL:raise InvalidTransition("terminal state")
  if next_state not in TRANSITIONS.get(prior,set()):raise InvalidTransition(f"{prior}->{next_state} forbidden")
  self.store.set_state(wid,prior,next_state,actor_principal_id,reason,operation_token,next_state in TERMINAL)
  return self.get_work_order(wid)
 def cancel(self,wid,*,actor_principal_id,reason):
  o=self.get_work_order(wid)
  if o['state'] in TERMINAL:return o
  if o['state'] in {'draft','validating','admitted'}:return self.transition(wid,'canceled',actor_principal_id=actor_principal_id,reason=reason,operation_token='cancel:'+wid)
  if o['state']!='canceling':self.transition(wid,'canceling',actor_principal_id=actor_principal_id,reason=reason,operation_token='cancel-request:'+wid)
  return self.transition(wid,'canceled',actor_principal_id=actor_principal_id,reason=reason,operation_token='cancel-complete:'+wid)
 def record_action_receipt(self,r):
  if r.get('kind')!='ActionReceipt':raise InvalidRequest("ActionReceipt required")
  s=r['state'];e=r['effect']
  if s['status']=='completed' and not s.get('evidenceRefs'):raise InvalidRequest("completed action requires evidence")
  if s['status']=='failed-after-uncertain-effect' and not e.get('reconciliationRef'):raise InvalidRequest("uncertain effect requires reconciliation")
  if r['authority']['authorityCeiling']=='external-sovereign':raise InvalidRequest("sovereign receipt forbidden")
  return self.store.put_receipt(r)
 def transition_history(self,wid):return [dict(x) for x in self.store.transitions(wid)]
 def action_receipts(self,wid):return [json.loads(x['receipt_json']) for x in self.store.receipts(wid)]
 @staticmethod
 def _shape(r):
  needed={'apiVersion','kind','metadata','capability','constraints','isolation','checkpointPolicy','approvalPolicy'}
  if needed-r.keys():raise InvalidRequest("missing required fields")
  if r['apiVersion']!='modos.pleiades/v1alpha1' or r['kind']!='WorkOrder':raise InvalidRequest("unsupported work order")
  for f in ('workOrderId','mindId','requesterPrincipalId','idempotencyKey'):
   if not r['metadata'].get(f):raise InvalidRequest('metadata.'+f+' required')
 @staticmethod
 def _capability_view(r):
  return {'capabilityId':r['capability_id'],'version':r['version'],'operations':json.loads(r['operations_json']),'maximumRisk':r['maximum_risk'],'canonicalWrite':bool(r['canonical_write']),'definitionDigest':r['definition_digest']}
 @staticmethod
 def _view(r):
  return {'workOrderId':r['work_order_id'],'mindId':r['mind_id'],'requesterPrincipalId':r['requester_principal_id'],'idempotencyKey':r['idempotency_key'],'requestDigest':r['request_digest'],'capabilityId':r['capability_id'],'capabilityVersion':r['capability_version'],'requestedOperation':r['requested_operation'],'riskCeiling':r['risk_ceiling'],'canonicalWrite':bool(r['canonical_write']),'state':r['state'],'planVersion':r['plan_version'],'createdAt':r['created_at'],'updatedAt':r['updated_at'],'terminalReason':r['terminal_reason']}
