"""SQLite persistence for durable work orders."""
from __future__ import annotations
import json, sqlite3
from pathlib import Path
from typing import Any, Iterable
from model import IdempotencyConflict, NotFound, canonical_bytes, digest, utc_now

class Store:
 def __init__(self,path:str|Path):
  self.db=sqlite3.connect(str(path));self.db.row_factory=sqlite3.Row
  self.db.execute("PRAGMA foreign_keys=ON");self.db.execute("PRAGMA journal_mode=WAL");self.db.execute("PRAGMA synchronous=FULL");self._migrate()
 def close(self):self.db.close()
 def _migrate(self):
  self.db.executescript('''
CREATE TABLE IF NOT EXISTS capabilities(capability_id TEXT,version TEXT,definition_digest TEXT NOT NULL,operations_json TEXT NOT NULL,maximum_risk TEXT NOT NULL,canonical_write INTEGER NOT NULL,active INTEGER NOT NULL DEFAULT 1,PRIMARY KEY(capability_id,version));
CREATE TABLE IF NOT EXISTS work_orders(work_order_id TEXT PRIMARY KEY,mind_id TEXT NOT NULL,requester_principal_id TEXT NOT NULL,idempotency_key TEXT NOT NULL UNIQUE,request_digest TEXT NOT NULL,request_json TEXT NOT NULL,capability_id TEXT NOT NULL,capability_version TEXT NOT NULL,requested_operation TEXT NOT NULL,risk_ceiling TEXT NOT NULL,canonical_write INTEGER NOT NULL,state TEXT NOT NULL,plan_version INTEGER NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,terminal_reason TEXT,FOREIGN KEY(capability_id,capability_version) REFERENCES capabilities(capability_id,version));
CREATE TABLE IF NOT EXISTS transitions(transition_id INTEGER PRIMARY KEY AUTOINCREMENT,work_order_id TEXT NOT NULL,operation_token TEXT NOT NULL UNIQUE,prior_state TEXT NOT NULL,next_state TEXT NOT NULL,actor_principal_id TEXT NOT NULL,reason TEXT NOT NULL,observed_at TEXT NOT NULL,FOREIGN KEY(work_order_id) REFERENCES work_orders(work_order_id));
CREATE TABLE IF NOT EXISTS action_receipts(operation_id TEXT PRIMARY KEY,work_order_id TEXT NOT NULL,stage_id TEXT NOT NULL,idempotency_key TEXT NOT NULL UNIQUE,effect_class TEXT NOT NULL,status TEXT NOT NULL,receipt_digest TEXT NOT NULL,receipt_json TEXT NOT NULL,observed_at TEXT NOT NULL,FOREIGN KEY(work_order_id) REFERENCES work_orders(work_order_id));''');self.db.commit()
 def put_capability(self,definition:dict[str,Any]):
  d=digest(definition);key=(definition['capabilityId'],definition['version'])
  with self.db:
   row=self.db.execute("SELECT definition_digest FROM capabilities WHERE capability_id=? AND version=?",key).fetchone()
   if row and row['definition_digest']!=d:raise IdempotencyConflict("capability version differs")
   self.db.execute("INSERT OR IGNORE INTO capabilities VALUES(?,?,?,?,?,?,1)",(*key,d,json.dumps(definition['operations'],separators=(',',':')),definition['maximumRisk'],int(definition['canonicalWrite'])))
  return d
 def capability(self,cid,version):
  row=self.db.execute("SELECT * FROM capabilities WHERE capability_id=? AND version=? AND active=1",(cid,version)).fetchone()
  if not row:raise NotFound("capability")
  return row
 def by_idempotency(self,key):return self.db.execute("SELECT * FROM work_orders WHERE idempotency_key=?",(key,)).fetchone()
 def insert_order(self,request):
  m=request['metadata'];c=request['capability'];x=request['constraints'];d=digest(request);now=utc_now()
  with self.db:
   self.db.execute('''INSERT INTO work_orders VALUES(?,?,?,?,?,?,?,?,?,?,?,'admitted',1,?,?,NULL)''',(m['workOrderId'],m['mindId'],m['requesterPrincipalId'],m['idempotencyKey'],d,canonical_bytes(request).decode(),c['capabilityId'],c['capabilityVersion'],c['requestedOperation'],x['riskCeiling'],int(x['canonicalWrite']),now,now))
   self.db.execute("INSERT INTO transitions(work_order_id,operation_token,prior_state,next_state,actor_principal_id,reason,observed_at) VALUES(?,?,'validating','admitted',?,?,?)",(m['workOrderId'],'admit:'+d,m['requesterPrincipalId'],'deterministic admission passed',now))
  return self.order(m['workOrderId'])
 def order(self,wid):
  row=self.db.execute("SELECT * FROM work_orders WHERE work_order_id=?",(wid,)).fetchone()
  if not row:raise NotFound(wid)
  return row
 def orders(self,states:Iterable[str]|None=None):
  if states:
   values=tuple(states);q=','.join('?' for _ in values);return self.db.execute(f"SELECT * FROM work_orders WHERE state IN ({q}) ORDER BY created_at",values).fetchall()
  return self.db.execute("SELECT * FROM work_orders ORDER BY created_at").fetchall()
 def transition_by_token(self,token):return self.db.execute("SELECT * FROM transitions WHERE operation_token=?",(token,)).fetchone()
 def set_state(self,wid,prior,next_state,actor,reason,token,terminal=False):
  now=utc_now()
  with self.db:
   self.db.execute("UPDATE work_orders SET state=?,updated_at=?,terminal_reason=? WHERE work_order_id=?",(next_state,now,reason if terminal else None,wid))
   self.db.execute("INSERT INTO transitions(work_order_id,operation_token,prior_state,next_state,actor_principal_id,reason,observed_at) VALUES(?,?,?,?,?,?,?)",(wid,token,prior,next_state,actor,reason,now))
 def transitions(self,wid):
  self.order(wid);return self.db.execute("SELECT * FROM transitions WHERE work_order_id=? ORDER BY transition_id",(wid,)).fetchall()
 def put_receipt(self,receipt):
  m=receipt['metadata'];d=digest(receipt);now=utc_now()
  with self.db:
   row=self.db.execute("SELECT receipt_digest FROM action_receipts WHERE idempotency_key=?",(m['idempotencyKey'],)).fetchone()
   if row:
    if row['receipt_digest']!=d:raise IdempotencyConflict("receipt differs")
    return d
   self.order(m['workOrderId'])
   self.db.execute("INSERT INTO action_receipts VALUES(?,?,?,?,?,?,?,?,?)",(m['operationId'],m['workOrderId'],m['stageId'],m['idempotencyKey'],receipt['effect']['class'],receipt['state']['status'],d,canonical_bytes(receipt).decode(),now))
  return d
