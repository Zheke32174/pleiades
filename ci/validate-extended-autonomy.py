#!/usr/bin/env python3
"""Validate durable-work-order schemas plus adversarial semantic fixture bundles."""
import json, sys
from datetime import datetime
from pathlib import Path
from jsonschema import Draft202012Validator, FormatChecker
ROOT=Path(__file__).resolve().parents[1]; CONTRACTS=ROOT/'modos'/'contracts'
SCHEMAS={'WorkOrder':'work-order.schema.json','WorkOrderStage':'work-order-stage.schema.json','StageApproval':'stage-approval.schema.json','EvidenceRecord':'evidence-record.schema.json','CheckpointRecord':'checkpoint-record.schema.json','ActionReceipt':'action-receipt.schema.json','CapabilityDefinition':'capability-definition.schema.json'}
RISK={'observe':0,'operate':1,'reversible':2,'confirmed':3,'external-sovereign':4}
def load(path):
    with path.open(encoding='utf-8') as f:return json.load(f)
def time(v):return datetime.fromisoformat(v.replace('Z','+00:00'))
def semantics(o):
    e=[]; k=o['kind']
    if k=='WorkOrder':
        c=o['constraints'];a=o['approvalPolicy'];i=o['isolation'];p=o['checkpointPolicy'];t=o['trigger']
        if c['canonicalWrite']:
            if a['canonicalMutation']=='forbidden':e+=['canonical write requires approval path']
            if not p['beforeCanonicalMutation'] or not p['restoreTestRequired']:e+=['canonical write requires restore-tested checkpoint']
        if i['required'] and i['mode']=='none':e+=['required isolation cannot be none']
        if c['riskCeiling']=='external-sovereign' and a['externalIrreversibleEffect']!='external-sovereign':e+=['sovereign ceiling requires sovereign path']
        if t['type'] in {'schedule','condition'} and t.get('maxFirings',0)<1:e+=['recurring trigger must be bounded']
        if t['type']=='condition' and t.get('cooldownSeconds',0)<1:e+=['condition requires cooldown']
    elif k=='WorkOrderStage':
        x=o['execution'];a=o['authority'];v=o['verification'];tier=x['riskTier']
        if tier=='external-sovereign':e+=['ordinary stage cannot execute sovereign effect']
        if x['canonicalMutation']:
            if tier!='confirmed':e+=['canonical mutation must be confirmed']
            if not x.get('artifactDigest') or not x.get('expectedStateDigest'):e+=['canonical mutation must bind exact artifact and state']
            if not v.get('checkpointRef') or not v.get('rollbackPlanRef'):e+=['canonical mutation requires checkpoint and rollback']
        if RISK[tier]>=3 and a['decision'] not in {'approval-required','allowed-with-constraints'}:e+=['confirmed stage requires approval boundary']
        if a['decision']=='allowed-with-constraints' and not a.get('approvalDecisionRef'):e+=['constrained stage requires exact approval']
    elif k=='StageApproval':
        m=o['metadata'];s=o['scope'];d=o['decision'];a=o['authority']
        if time(m['expiresAt'])<=time(m['issuedAt']):e+=['approval must expire after issuance']
        if s['requestedRiskTier']=='external-sovereign' and a['approverClass']!='external-sovereign':e+=['connector approval cannot authorize sovereign effect']
        if d['value']=='approve-with-conditions' and not d.get('conditionRefs'):e+=['conditional approval must bind conditions']
    elif k=='EvidenceRecord':
        if o['security']['authorityCeiling']!='none':e+=['evidence has no authority']
        if o['claim']['type']=='model-judgment' and o['result']['status']=='pass' and o['epistemics']['independent']:e+=['model judgment cannot be deterministic proof']
    elif k=='CheckpointRecord':
        r=o['restore'];s=o['state']
        if r.get('reversibilityClaim') and (r['testStatus']!='passed' or not r.get('testEvidenceRef') or not r['externalEffectsReversible']):e+=['reversibility requires passed restore evidence and reversible external effects']
        if s['status']=='verified' and r['testStatus']!='passed':e+=['verified checkpoint requires restore test']
    elif k=='ActionReceipt':
        x=o['effect'];s=o['state']
        if s['status']=='completed' and not s['evidenceRefs']:e+=['completed action requires evidence']
        if s['status']=='failed-after-uncertain-effect' and not x.get('reconciliationRef'):e+=['uncertain effect requires reconciliation']
        if x['class']=='non-idempotent' and x['external'] and not x.get('externalReceiptRef'):e+=['external non-idempotent effect requires receipt']
        if o['authority']['authorityCeiling']=='external-sovereign':e+=['ordinary receipt cannot claim sovereign execution']
    elif k=='CapabilityDefinition':
        s=o['security'];l=o['learning'];q=o['scope'];r=o['risk'];a=o['approval']
        if s['arbitraryShell'] or s['rawSecretAccess'] or s['selfAuthorityMutation']:e+=['capability exposes ambient authority']
        if l['directSelfPromotion']:e+=['capability cannot self-promote']
        if RISK[r['baseTier']]>RISK[r['maximumTier']]:e+=['base risk exceeds maximum']
        if q['canonicalWrite'] and a['canonicalMutation']=='forbidden':e+=['canonical capability requires approval path']
        if a['externalIrreversibleEffect']!='forbidden':e+=['ordinary capability cannot expose irreversible external effects']
    return e
def main():
    checker=FormatChecker(); schemas={}; failures=[]; count=0
    for kind,name in SCHEMAS.items():
        schema=load(CONTRACTS/name);Draft202012Validator.check_schema(schema);schemas[kind]=schema;print('schema ok:',name)
    for path in sorted(CONTRACTS.glob('extended-autonomy-*.fixtures.json')):
        bundle=load(path);kind=bundle['kind'];print('fixture bundle:',path.name)
        for case in bundle['cases']:
            count+=1;obj=case['instance'];se=list(Draft202012Validator(schemas[kind],format_checker=checker).iter_errors(obj));sm=semantics(obj) if not se else [];actual=not se and not sm
            if actual!=case['valid']:failures.append(f"{path.name}/{case['name']}: expected {case['valid']}, got {actual}: "+'; '.join([x.message for x in se]+sm))
            else:print('case',('accepted' if actual else 'rejected')+':',case['name'])
    if failures:
        print('validation failures:',file=sys.stderr)
        for f in failures:print('-',f,file=sys.stderr)
        return 1
    print(f'validated {len(schemas)} schemas and {count} semantic cases');return 0
if __name__=='__main__':raise SystemExit(main())
