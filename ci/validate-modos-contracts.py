#!/usr/bin/env python3
"""Validate shared MODOS schemas and legacy semantic fixture bundles."""
from __future__ import annotations
import argparse,sys
from pathlib import Path
from typing import Any
from jsonschema import Draft202012Validator,FormatChecker
from modos_semantics_legacy import semantic_errors
from modos_validation_common import load_json

DELEGATED_FIXTURE_PREFIXES=("extended-autonomy-",)

def main()->int:
 parser=argparse.ArgumentParser();parser.add_argument("--contracts",type=Path,default=Path("modos/contracts"));args=parser.parse_args()
 contracts=args.contracts.resolve();checker=FormatChecker();failures=[];schemas:dict[str,dict[str,Any]]={}
 for path in sorted(contracts.glob("*.schema.json")):
  schema=load_json(path);Draft202012Validator.check_schema(schema);schemas[path.name]=schema;print(f"schema ok: {path.name}")
 fixtures=sorted(contracts.glob("*.fixtures.json"))
 if not fixtures:print("no contract fixture bundles found",file=sys.stderr);return 1
 count=0;delegated=0
 for path in fixtures:
  if path.name.startswith(DELEGATED_FIXTURE_PREFIXES):
   delegated+=1;print(f"fixture delegated to dedicated validator: {path.name}");continue
  bundle=load_json(path);cases=bundle.get("cases")
  if not isinstance(cases,list) or not cases:failures.append(f"{path.name}: cases must be a nonempty list");continue
  print(f"fixture bundle: {path.name}")
  for case in cases:
   count+=1;schema_name=case["schema"];name=case["name"];expected=bool(case["valid"]);schema=schemas.get(schema_name)
   if schema is None:failures.append(f"{path.name}/{name}: unknown schema {schema_name}");continue
   instance=case["instance"];validator=Draft202012Validator(schema,format_checker=checker);schema_errors=sorted(validator.iter_errors(instance),key=lambda error:list(error.path));semantics=semantic_errors(instance) if not schema_errors else [];actual=not schema_errors and not semantics
   if actual!=expected:
    detail=[error.message for error in schema_errors]+semantics;failures.append(f"{path.name}/{name}: expected valid={expected}, got valid={actual}; "+"; ".join(detail))
   else:print(f"fixture {'accepted' if actual else 'rejected'}: {name}")
 if failures:
  print("contract validation failures:",file=sys.stderr)
  for failure in failures:print(f"- {failure}",file=sys.stderr)
  return 1
 print(f"validated {len(schemas)} schemas, {len(fixtures)} bundles, {count} legacy fixtures, and delegated {delegated} bundles");return 0

if __name__=="__main__":raise SystemExit(main())
