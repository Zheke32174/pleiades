# MODOS Epistemic Governance

This directory contains the first executable layer for **ontological self-criticism** in Pleiades.

It does not attempt to make the ontology perfectly complete or permanently correct. It makes category use auditable and prevents several destructive shortcuts:

- silently treating one term as equivalent to another;
- forcing category-sensitive claims into a false binary;
- promoting claims without provenance or explicit decisions;
- erasing active dissent during convergence;
- keeping accepted claims alive after their dependencies have been rejected;
- treating correlated agreement as independent evidence.

## Files

- `distinctions.json` — registered non-equivalences, middle spaces, collapse hazards, competency questions, and counterexamples.
- `epistemic-ledger.example.json` — reference claim/evidence/argument/decision ledger.
- `../contracts/distinction-registry.schema.json` — structural contract for distinction registries.
- `../contracts/epistemic-ledger.schema.json` — structural contract for epistemic ledgers.
- `../../ci/validate_epistemic_governance.py` — network-independent semantic validator.
- `../../ci/test_epistemic_governance.py` — regression tests for silent collapse, erased dissent, dangling references, and revision cycles.

## Operational rule

Agents may propose claims and ontology changes. They may not promote category-sensitive claims unless they:

1. identify the distinction being preserved;
2. record plausible alternatives;
3. name the collapse risk and mitigation;
4. attach provenance-bearing evidence;
5. expose attacks and qualifications;
6. retain unresolved dissent in the promotion record.

The validator proves these records are present and internally coherent. It does **not** prove that a proposition is true.

## Validate locally

```bash
python ci/validate_epistemic_governance.py \
  --distinctions modos/ontology/distinctions.json \
  --distinction-schema modos/contracts/distinction-registry.schema.json \
  --ledger modos/ontology/epistemic-ledger.example.json \
  --ledger-schema modos/contracts/epistemic-ledger.schema.json
```

Run the semantic regression suite with:

```bash
python -m unittest ci/test_epistemic_governance.py -v
```
