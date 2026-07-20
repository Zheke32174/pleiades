# Executive Memory, Evidence, and Learning Spine

This tranche implements progression points 71–80 from
`modos/ECOLOGY_PROGRESSION_100.md`.

`learning_spine.py` closes one append-only batch of executive memory records.
It does not train a model, delete history, or mutate authority.

## Immutable record classes

The spine persists:

- observations;
- decisions;
- mandates;
- outcomes;
- corrections;
- provenance records.

Every record binds content and evidence digests, domain, objective, semantic
tags, source identity, verification state, visibility, and retention class.
Narrative summaries remain separate from evidence digests.

## Retrieval indexes

The closure receipt emits:

- an episodic index keyed by domain and objective;
- a deterministic semantic-tag index;
- provenance edges;
- correction edges;
- retention and visibility metadata.

These indexes are deterministic review artefacts, not mutable memory authority.

## Corrections and contradictions

Corrections reference earlier records without deleting or rewriting them. A
corrected record remains in the evidence history and is marked as corrected.

Conflicting verified claims are preserved as unresolved contradictions. The
spine does not silently choose the most recent narrative or discard minority
evidence.

## Feedback safety

Only independently verified `outcome` records may enter the feedback manifest.
Observations, decisions, mandates, corrections, and provenance records are never
training examples merely because they exist. Unverified and self-generated Mind
outcomes are refused.

The feedback manifest declares `trainingApplied: false`. A later governed
training or adaptation system must consume it through its own proposal,
evaluation, and promotion gates.

## Validation

```bash
python ci/validate-learning-spine.py
python modos/governance/test_learning_spine.py
```

Locally reproduced:

- three contract definitions validated;
- one deterministic learning-spine engine exercised;
- twelve adversarial tests passed;
- one golden digest reproduced;
- executable files passed bytecode compilation.

## Deliberate boundary

This tranche does not write to a live database, perform vector embedding,
modify a model, create a training run, erase a record, resolve a contradiction,
or expand authority.
