# MODOS Epistemic Governance

This directory contains the executable layer for **ontological self-criticism** in Pleiades.

It does not attempt to make the ontology perfectly complete or permanently correct. It makes category use and ontology evolution auditable and prevents several destructive shortcuts:

- silently treating one term as equivalent to another;
- forcing category-sensitive claims into a false binary;
- promoting claims without provenance or explicit decisions;
- erasing active dissent during convergence;
- keeping accepted claims alive after their dependencies have been rejected;
- treating correlated agreement as independent evidence;
- rewriting the ontology without diagnosing what actually failed;
- deleting concepts before testing weakening, scoping, splitting, or plural interpretation.

## Files

- `distinctions.json` — registered non-equivalences, middle spaces, collapse hazards, competency questions, and counterexamples.
- `epistemic-ledger.example.json` — reference claim/evidence/argument/decision ledger.
- `ontology-revision-proposal.example.json` — reference anomaly-driven ontology revision experiment.
- `../contracts/distinction-registry.schema.json` — structural contract for distinction registries.
- `../contracts/epistemic-ledger.schema.json` — structural contract for epistemic ledgers.
- `../contracts/ontology-revision-proposal.schema.json` — structural contract for governed ontology mutation.
- `../../ci/validate_epistemic_governance.py` — network-independent claim and dissent validator.
- `../../ci/validate_ontology_revision.py` — network-independent ontology revision validator.
- `../../ci/test_epistemic_governance.py` — regression tests for silent collapse, erased dissent, dangling references, and revision cycles.
- `../../ci/test_ontology_revision.py` — regression tests for unsupported concept invention, deletion-first repair, collapsed boundary objects, and evidence-poor promotion.

## Operational rule for claims

Agents may propose claims. They may not promote category-sensitive claims unless they:

1. identify the distinction being preserved;
2. record plausible alternatives;
3. name the collapse risk and mitigation;
4. attach provenance-bearing evidence;
5. expose attacks and qualifications;
6. retain unresolved dissent in the promotion record.

## Operational rule for ontology changes

Agents may propose ontology changes. They may not mutate canon directly. A proposal must:

1. record the recurring anomaly, failed classification, user correction, uncertainty signal, or external research trigger;
2. diagnose whether the failure belongs to task, method, knowledge, vocabulary, boundary, evidence, or coordination;
3. prefer weakening, scoping, splitting, sense addition, relation revision, or boundary translation before deprecation;
4. preserve multiple scoped interpretations when uniform meaning is not justified;
5. include alternatives, competency questions, counterexamples, migration, rollback, and retained dissent;
6. remain branch-scoped while experimental;
7. earn promotion through independent evidence, independent first passes, explicit review, and observable improvement.

The validators prove these records are present and internally coherent. They do **not** prove that a proposition or proposed concept is true.

## Validate locally

Validate the distinction registry and epistemic ledger:

```bash
python ci/validate_epistemic_governance.py \
  --distinctions modos/ontology/distinctions.json \
  --distinction-schema modos/contracts/distinction-registry.schema.json \
  --ledger modos/ontology/epistemic-ledger.example.json \
  --ledger-schema modos/contracts/epistemic-ledger.schema.json
```

Validate the ontology revision proposal:

```bash
python ci/validate_ontology_revision.py \
  --proposal modos/ontology/ontology-revision-proposal.example.json \
  --schema modos/contracts/ontology-revision-proposal.schema.json
```

Run both semantic regression suites:

```bash
python -m unittest \
  ci/test_epistemic_governance.py \
  ci/test_ontology_revision.py -v
```
