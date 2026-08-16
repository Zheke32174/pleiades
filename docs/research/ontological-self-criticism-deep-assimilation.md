# Deep Assimilation: Ontology Evolution, Metacognition, and Concept Discovery

## Purpose

This second research pass asks a narrower implementation question:

> How can Pleiades discover that its present concepts are inadequate, propose a better distinction without destroying useful older meanings, test the proposal across viewpoints, and promote it only after evidence-bearing review?

The first epistemic-governance layer protects distinctions and dissent once they exist. This extension adds a governed path for **discovering, revising, weakening, scoping, translating, and experimentally testing concepts themselves**.

## Research streams and design consequences

### 1. Distributed ontology change must preserve intent and history

Michel Klein's doctoral thesis, *Change Management for Distributed Ontologies* (Vrije Universiteit Amsterdam, 2004), treats ontology change as a distributed problem rather than a single-editor rewrite. Muhammad Javed's doctoral thesis, *Operational Change Management and Change Pattern Identification for Ontology Evolution* (Dublin City University, 2013), adds layered change logs, atomic and composite change operations, and mining of recurring change patterns and intent.

Primary sources:

- <https://research.vu.nl/en/publications/change-management-for-distributed-ontologies>
- <https://www.cs.vu.nl/~mcaklein/thesis/thesis.pdf>
- <https://doras.dcu.ie/18187/>
- <https://doras.dcu.ie/17822/>

**Assimilation**

- ontology mutation is represented as a proposal, not an edit;
- every proposal records its trigger, diagnosis, intent, atomic changes, composite pattern, alternatives, migration, and rollback;
- distributed viewpoints remain named rather than being silently normalized into one authorial voice;
- experimental changes stay branch-scoped until promotion.

### 2. Repair should weaken, scope, or split before it deletes

Troquard et al., *Repairing Ontologies Via Axiom Weakening* (2017), argues that restoring consistency by weakening offending axioms can preserve substantially more knowledge than simply removing them.

Primary source:

- <https://arxiv.org/abs/1711.03430>

**Assimilation**

The revision contract contains explicit operations for:

- weakening an axiom;
- scoping a concept;
- adding a concept sense;
- splitting a concept;
- introducing a distinction;
- adding a boundary object;
- revising a relation;
- deprecating only after non-destructive alternatives are documented.

The validator rejects a deprecation proposal that never considered weakening, scoping, splitting, sense-addition, relation revision, or boundary translation.

### 3. Metacognition needs a separate diagnosis layer

Kim, Islam, and Goel's two-level metacognitive architecture uses a Task-Method-Knowledge model so an agent can identify which part of its own process caused an error and revise the relevant knowledge structure. Shakarian's *Toward Artificial Metacognition* and the systematic review by Nolte et al. frame self-monitoring, regulation, and metacognitive memory as architectural capabilities rather than prompt tricks.

Primary sources:

- <https://ojs.aaai.org/index.php/AAAI/article/view/41465>
- <https://ojs.aaai.org/index.php/AAAI/article/view/42135>
- <https://arxiv.org/abs/2503.13467>

**Assimilation**

Every proposal separates:

1. **trigger** — what failed or remained unexplained;
2. **diagnosis** — task, method, knowledge, vocabulary, boundary, evidence, or coordination failure;
3. **change** — the ontology operation;
4. **proof obligations** — what must become observably better.

This prevents the ecology from responding to every failure by editing its knowledge base indiscriminately.

### 4. A missing concept can be an epistemic failure in its own right

Fricker's account of hermeneutical injustice identifies harm caused by defects in shared interpretive resources. Goetze's work on hermeneutical dissent is especially useful for Pleiades because it shows that minority interpretive resources may already exist outside the dominant shared vocabulary.

Primary sources:

- <https://academic.oup.com/book/32817/chapter-abstract/275001188>
- <https://eprints.whiterose.ac.uk/id/eprint/115077/>

**Assimilation**

A proposal may diagnose a **hermeneutical gap**, but only when it records:

- recurring residual cases that the current ontology handles badly;
- the false binary or missing middle, when applicable;
- consequences of the present misclassification;
- candidate concepts or scoped interpretations;
- counterexamples proving the new concept is not merely a synonym.

The validator requires at least two recurring residuals before a hermeneutical-gap diagnosis can drive concept formation.

### 5. Shared work does not require uniform meaning

Star and Griesemer's boundary-object framework explains how heterogeneous communities cooperate around shared objects while retaining different local interpretations. Star's later clarification warns against reducing boundary objects to vague interpretive flexibility. Concept-pluralist work by Sawyer and Dobler similarly argues against assuming one engineered concept must replace every prior use.

Primary sources:

- <https://journals.sagepub.com/doi/10.1177/030631289019003001>
- <https://journals.sagepub.com/doi/pdf/10.1177/0162243910377624>
- <https://www.tandfonline.com/doi/full/10.1080/0020174X.2021.1986424>
- <https://www.tandfonline.com/doi/abs/10.1080/0020174X.2022.2086171>

**Assimilation**

The proposal contract supports:

- a shared core;
- multiple scoped local interpretations;
- invariants each viewpoint must preserve;
- explicit translation rules;
- loss warnings when translating between viewpoints.

An `add-boundary-object` proposal is invalid unless it preserves at least two local interpretations and a translation rule. The goal is interoperability without dishonest semantic uniformity.

### 6. Uncertainty must be measured over meanings, not just wording

Farquhar et al. show that semantic entropy can identify confabulation by clustering generations according to meaning rather than lexical form. Emerging work on semantic-preserving interventions and cross-model disagreement suggests that within-model consistency and between-model disagreement capture different uncertainty modes.

Primary and emerging sources:

- Farquhar et al., *Detecting Hallucinations in Large Language Models Using Semantic Entropy*, Nature (2024): <https://www.nature.com/articles/s41586-024-07421-0>
- Li et al., *ESI: Epistemic Uncertainty Quantification Via Semantic-Preserving Intervention* (2025 preprint): <https://arxiv.org/abs/2510.13103>
- Hamidieh et al., *Complementing Self-Consistency With Cross-Model Disagreement* (2026 preprint): <https://arxiv.org/abs/2604.17112>

**Assimilation**

Revision triggers may record:

- semantic entropy;
- within-model variation;
- cross-model disagreement;
- answer agreement;
- reasoning alignment.

A large gap between cross-model disagreement and within-model variation is reported as likely epistemic uncertainty rather than sampling noise. The contract does not pretend these metrics prove truth; they decide when the ecology must abstain, retrieve more evidence, or consider ontology revision.

### 7. Consensus can conceal reasoning misalignment

Multi-agent debate can improve reasoning, but the literature increasingly shows that agent count and visible consensus are not enough. Controlled studies find that diversity and intrinsic reasoning strength matter more than many debate mechanics, while majority pressure can suppress correct minority reasoning. Recent work on the “consistency illusion” shows that answer-level agreement can rise even when reasoning paths become less aligned.

Primary and emerging sources:

- Du et al., ICML 2024: <https://proceedings.mlr.press/v235/du24e.html>
- Smit et al., ICML 2024: <https://proceedings.mlr.press/v235/smit24a.html>
- Liang et al., divergent-thinking debate: <https://arxiv.org/abs/2305.19118>
- Wu et al., controlled debate study (2025 preprint): <https://arxiv.org/abs/2511.07784>
- Wang and Yang, *The Consistency Illusion* (2026 preprint): <https://arxiv.org/abs/2606.08457>

**Assimilation**

- independent first passes are a proof obligation;
- evidence source groups are counted separately from agent votes;
- answer agreement and reasoning alignment are audited separately;
- high agreement with low reasoning alignment produces a consistency-illusion signal;
- an experimental or approved proposal must state how it prevents majority pressure from erasing a sound minority path.

### 8. Belief revision is a group dynamic, not only an individual update

Work on partial epistemic-state revision and belief-revision games models uncertain inputs and repeated belief interaction among agents.

Primary sources:

- Ma, Liu, and Benferhat, AAAI 2010: <https://ojs.aaai.org/index.php/AAAI/article/view/7585>
- Schwind et al., AAAI 2015: <https://ojs.aaai.org/index.php/AAAI/article/view/9415>

**Assimilation**

A proposal records alternative operations and their status rather than flattening revision into one winning edit. This is deliberately compatible with later simulation of how candidate concepts propagate through Atlas, agents, repositories, and user-facing language before promotion.

## Implemented second-wave artifacts

### Ontology revision proposal contract

`modos/contracts/ontology-revision-proposal.schema.json` defines:

- anomaly and uncertainty triggers;
- metacognitive failure-layer diagnosis;
- hermeneutical-gap and false-binary records;
- atomic and composite ontology operations;
- weakening, scoping, splitting, sense-addition, boundary-object, relation-revision, and deprecation paths;
- scoped interpretations and translation-loss warnings;
- rejected, active, and deferred alternatives;
- competency questions, counterexamples, migration, rollback, independent-first-pass, diversity, dissent, and ordinary-person tests;
- branch-scoped experiment and promotion review.

### Reference proposal

`modos/ontology/ontology-revision-proposal.example.json` applies the contract to the deliberate/conspiratorial false binary. It preserves conspiracy and accident while introducing distributed institutional intention, parallel incentive alignment, and anticipated emergence as testable middle concepts.

The example intentionally contains:

- high answer agreement;
- low reasoning alignment;
- cross-model disagreement much greater than within-model variation.

The validator therefore reports uncertainty and a possible consistency illusion while still accepting the proposal as a structurally valid **experiment**, not canon.

### Deterministic revision validator

`ci/validate_ontology_revision.py` rejects:

- hermeneutical-gap claims based on a single residual;
- concept-forming operations with no resulting concepts;
- boundary objects with only one local interpretation;
- translation rules referencing nonexistent viewpoints;
- deprecation without a documented non-destructive alternative;
- approved proposals without independent first passes, evidence diversity, arguments, decision provenance, migration, or rollback;
- high-consensus/low-reasoning-alignment proposals with no mitigation;
- semantic-uncertainty, cross-model-disagreement, or reasoning-misalignment triggers lacking their corresponding metrics.

### Regression suite

`ci/test_ontology_revision.py` contains negative tests for:

- unsupported hermeneutical-gap claims;
- collapsed boundary objects;
- deletion-first repair;
- evidence-poor promotion;
- unmitigated consistency illusion;
- dangling translation viewpoints;
- unscoped experimental mutation.

## Architectural placement

The new loop extends the Atlas–Forge boundary:

1. organs produce independent first-pass claims;
2. Atlas accumulates unresolved residuals, failed classifications, semantic uncertainty, and disagreement;
3. the metacognitive layer diagnoses whether the failure belongs to task, method, knowledge, vocabulary, boundary, evidence, or coordination;
4. an ontology revision proposal is generated on an isolated branch;
5. candidate concepts are tested against competency questions, counterexamples, multiple viewpoints, migration, and rollback;
6. Forge may authorize an experiment;
7. only measured improvement plus steward review may promote the change;
8. rejected proposals remain evidence for future revision rather than disappearing.

## What remains deliberately unimplemented

- automatic canon mutation;
- automatic generation of new diagnostic or moral labels;
- treating semantic entropy as a truth score;
- majority-vote promotion;
- deleting old concepts merely because a new one performs better in one scope;
- assuming all viewpoints can be translated without semantic loss;
- training directly on the ecology's own conclusions without external outcome evidence.

## Next deep implementation targets

1. Atlas adapter that emits revision triggers from residual clusters and user corrections.
2. Meaning-cluster service for semantic entropy and cross-model disagreement.
3. Reasoning-alignment auditor that compares claims, evidence, and causal paths rather than hidden chain-of-thought.
4. Change-pattern miner over ontology proposal history.
5. Sandbox propagation simulator for measuring downstream impact before promotion.
6. Boundary-object registry for cross-domain terms with scoped meanings.
7. Defeater daemon that reopens accepted concepts when outcomes violate competency tests.
8. Promotion benchmark combining machine measurement, steward verification, and blind ordinary-person distinction tests.
