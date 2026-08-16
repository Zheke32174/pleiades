# Cultivating Ontological Self-Criticism in Pleiades

## Research question

How can a polycentric AI ecology use ontology to preserve important distinctions, retain dissent, revise beliefs, and notice when its own categories are distorting the territory?

The immediate failure pattern is **silent category collapse**. Examples include:

- deliberate action collapsed into conspiracy or accident;
- behavioral description collapsed into diagnosis or invalid language;
- traits collapsed into disorders;
- deliberate confusion collapsed into deception;
- emergence collapsed into accident;
- consensus collapsed into evidence.

These are not merely vocabulary disagreements. Removing the middle category changes which causal explanations the ecology is able to represent.

## Methods assimilated

### 1. Executable shapes rather than prose-only ontology

The W3C Shapes Constraint Language (SHACL) treats graph structure and constraints as machine-checkable shapes. Pleiades currently uses JSON Schema because the MODOS contracts already use JSON/YAML and deterministic Python validation. The contracts were designed so they can later project into RDF and SHACL without changing the conceptual model.

Stable baseline:

- W3C SHACL Recommendation: <https://www.w3.org/TR/shacl/>

Current evolution to watch, but not yet treat as stable canon:

- SHACL 1.2 Core working draft: <https://www.w3.org/TR/shacl12-core/>
- SHACL 1.2 Rules working draft: <https://www.w3.org/TR/shacl12-rules/>

**Assimilation:** distinction and ledger structures are schemas, not informal advice, and CI rejects malformed or semantically incomplete records.

### 2. Provenance as part of belief, not an attachment

PROV-O represents entities, activities, agents, generation, derivation, and attribution.

- W3C PROV-O Recommendation: <https://www.w3.org/TR/prov-o/>

**Assimilation:** evidence records carry source, source group, observation time, generator, derivation, reliability, and optional digests. Claims cite evidence IDs rather than copying unsupported prose into canon.

### 3. Truth maintenance and belief revision

Doyle's truth-maintenance work treats beliefs as dependency-bearing states that must change when their justifications change.

- Jon Doyle, *A Truth Maintenance System* (1979): <https://groups.csail.mit.edu/medg/people/doyle/publications/>

AGM belief revision later formalized revision, contraction, and expansion. The practical lesson for Pleiades is that accepted beliefs must remain connected to their dependencies and revision history instead of becoming inert facts.

**Assimilation:**

- claims have explicit dependencies;
- accepted claims may not depend on rejected or superseded claims;
- dependency and supersession cycles are rejected;
- defeaters specify conditions that lower confidence, suspend, reject, reopen debate, or require steward review;
- revisions name what they supersede and why.

### 4. Argumentation instead of forced consistency

Dung's abstract argumentation framework models arguments and attack relations, then evaluates acceptability without pretending disagreement never existed.

- Phan Minh Dung, *On the Acceptability of Arguments...*, Artificial Intelligence 77(2), 1995, DOI: `10.1016/0004-3702(94)00041-X`

**Assimilation:**

- agents submit support, attack, and qualification arguments;
- attacks form a graph;
- the validator computes a grounded extension for observability;
- attack cycles are legal and remain unresolved rather than being deleted;
- an accepting decision must explicitly preserve every active attack or qualification as selected reasoning or retained dissent.

This is intentionally paraconsistent in operation: contradiction is localized and recorded instead of causing arbitrary deletion or global logical explosion.

### 5. Competency questions and counterexamples

Competency questions are functional requirements for an ontology: questions the ontology must be able to answer. Research also shows their value for defining scope, testing, and pattern selection.

Relevant work:

- Wiśniewski et al., *Analysis of Ontology Competency Questions and their formalizations in SPARQL-OWL*, Journal of Web Semantics 59 (2019).
- Gangemi et al., *Automatically Drafting Ontologies from Competency Questions with FrODO* (2022), arXiv:2206.02485.
- Alharbi et al., *Investigating Open Source LLMs to Retrofit Competency Questions in Ontology Engineering* (AAAI Symposium, 2024).

**Assimilation:** every registered distinction requires multiple competency questions and counterexamples. This prevents a distinction from existing only as a label with no testable purpose or boundary cases.

### 6. Diverse first passes, confidence, and retained minority evidence

Multi-agent debate can improve factuality and reasoning, but homogeneous agents can merely reproduce correlated error. More recent work emphasizes diverse initial views and calibrated confidence rather than debate volume alone.

Relevant work:

- Du et al., *Improving Factuality and Reasoning in Language Models through Multiagent Debate*, ICML 2024: <https://proceedings.mlr.press/v235/du24e.html>
- Zhu et al., *Demystifying Multi-Agent Debate: The Role of Confidence and Diversity* (2026), arXiv:2601.19921.

**Assimilation:**

- claims and arguments record source agents and confidence;
- evidence records include source groups so copied evidence is not counted as independent;
- high-confidence claims relying on one source group generate warnings;
- dissent remains addressable after convergence;
- the design favors independent first-pass contributions before shared-workspace updating.

## Implemented architecture

### Distinction registry

`modos/ontology/distinctions.json` records:

- terms that overlap but are not equivalent;
- their level of analysis;
- legitimate middle spaces;
- forbidden directional collapses;
- competency questions;
- counterexamples;
- evidence references.

The initial registry contains six recurring distinctions:

1. deliberate vs conspiratorial;
2. description vs diagnosis;
3. trait vs disorder;
4. confusion vs deception;
5. emergence vs accident;
6. consensus vs evidence.

### Epistemic ledger

`modos/ontology/epistemic-ledger.example.json` models:

- provenance-bearing evidence;
- claims and confidence;
- level of analysis and assertion mode;
- category sensitivity;
- alternatives and defeaters;
- claim dependencies and revision;
- argument attacks;
- promotion decisions and retained dissent.

### Deterministic validator

`ci/validate_epistemic_governance.py` rejects:

- duplicate or dangling IDs;
- invalid collapse declarations;
- unknown distinction/evidence/claim/argument references;
- evidence, dependency, or supersession cycles;
- category-sensitive claims without alternatives, preserved distinctions, or collapse mitigation;
- promoted claims without evidence or explicit accepting decisions;
- promoted claims depending on dead claims;
- accepting decisions that silently omit active dissent.

It reports:

- registry coverage;
- claim and evidence counts;
- promoted and category-sensitive claims;
- grounded accepted arguments;
- unresolved active arguments;
- warnings about high-confidence claims with low source independence.

### Regression tests and CI

`ci/test_epistemic_governance.py` includes negative tests proving that CI catches:

- silent distinction collapse;
- erased dissent;
- dependency cycles;
- unknown distinctions;
- and accidental deletion of argument cycles.

`.github/workflows/modos-epistemic-governance.yml` compiles the validator, runs the tests, validates the reference artifacts, and uploads an epistemic-governance receipt.

## Placement in the Pleiades mind

This layer belongs between Atlas and Forge:

1. cognitive organs make independent first-pass contributions;
2. Atlas records claims, evidence, alternatives, attacks, confidence, and distinctions;
3. the epistemic validator proves structural and semantic integrity;
4. debate and evidence weighting update the shared belief state;
5. Forge may promote an action or canon change only through an explicit decision retaining provenance and dissent;
6. outcomes return as new evidence, potentially activating defeaters or ontology revision.

Models remain proposal-bearing cognitive organs. The persistent recurrent organization remains the mind.

## What this first pass does not do

- It does not infer clinical, moral, or institutional truth from labels.
- It does not assume every conflict can or should be resolved.
- It does not yet execute RDF/SPARQL competency queries.
- It does not yet score argument quality beyond declared confidence and evidence structure.
- It does not automatically mutate canon.
- It does not let consensus substitute for evidence.

## Next implementation stages

1. **Atlas adapter:** emit ledger records from typed shared-workspace messages.
2. **Independent-first-pass gate:** cryptographically or procedurally separate initial contributions from later debate rounds.
3. **RDF/SHACL projection:** export the JSON contracts to RDF and validate with stable SHACL; evaluate SHACL 1.2 rules after standardization.
4. **Competency-query harness:** bind natural-language competency questions to deterministic queries and expected fixtures.
5. **Belief-maintenance daemon:** activate defeaters and revise dependent claims when evidence changes.
6. **Ontology-drift monitor:** detect recurring unclassifiable cases, collapse warnings, and confidence degradation as candidates for new distinctions.
7. **Promotion evaluation:** require machine-measurable, steward-verifiable, and ordinary-person-noticeable improvement before ontology changes become canon.
