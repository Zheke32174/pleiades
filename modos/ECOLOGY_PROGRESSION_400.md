# Pleiades Ecology — Organic Progression Points 301–400

These points were derived from the exact checkpoint-300 evidence and its remaining trust gap. Checkpoint 300 could bind opaque references and digests, but a digest alone did not prove who issued the evidence, whether the issuer was authorized for that input, whether the evidence remained fresh, whether a key or grant had been revoked, or whether a reviewable plan had satisfied the exact authorization path required before mandate construction.

This checkpoint remains repository-side verification. It does not supply real private evidence, publish private keys, issue a grant, construct a mandate, authorize a live transition, contact a node, rewrite history, or execute anything.

Status vocabulary:

- `implemented` — present on `governance/operational-trust-preflight-v1` as code, contract, fixture, deterministic receipt, test, workflow, documentation, or packaging surface;
- `provisional` — implemented but awaiting the aggregate receipt for the exact final checkpoint head;
- `blocked` — requires real sovereign identities, real public keys and signatures, real private/live evidence, a real grant, live infrastructure, mandate construction, or elapsed observation;
- `specified` — intentionally reserved for derivation from later real receipts.

## Phase AB — Preserve checkpoint 300 and expose the trust gap

301. `implemented` Freeze checkpoint 300 at evidence commit `073c9262ad009d7d5f47f01407d94ac7780d9d53`.
302. `implemented` Create a stacked successor branch rather than mutating the proven checkpoint-300 head.
303. `implemented` Preserve the checkpoint-300 rollback and review seam.
304. `implemented` Distinguish digest identity from evidence legitimacy.
305. `implemented` Identify missing issuer identity and issuer-scope proof.
306. `implemented` Identify missing key-integrity and signature proof.
307. `implemented` Identify missing freshness, expiry, and clock-skew proof.
308. `implemented` Identify missing principal, key, attestation, approval, and grant revocation proof.
309. `implemented` Identify the missing transition from review readiness to mandate-construction eligibility.
310. `implemented` Preserve the rule that trust verification cannot itself create authority.

## Phase AC — Operational authority registry

311. `implemented` Define `OperationalAuthorityRegistry` as a Draft 2020-12 contract.
312. `implemented` Keep the registry subordinate to promoted constitutional policy.
313. `implemented` Define typed operational principals and principal status.
314. `implemented` Define explicit roles, evidence-input scopes, decision scopes, executor capabilities, and conflict domains.
315. `implemented` Define Ed25519 public-key identities and exact public-key digests.
316. `implemented` Define bounded key validity and key lifecycle status.
317. `implemented` Define per-input evidence policies for classification, issuer role, freshness, clock skew, and attestor count.
318. `implemented` Define per-decision policies for domain, action, risk, authorization mode, quorum, audit, grant, executor, and rollback.
319. `implemented` Define typed revocations for principals, keys, attestations, approvals, and grants.
320. `implemented` Require the registry to remain closure-only, non-executing, non-issuing, and non-self-modifying.

## Phase AD — Signed evidence attestations

321. `implemented` Define `EvidenceAttestation` as a canonical signed statement.
322. `implemented` Bind every attestation to the exact operator-candidate digest.
323. `implemented` Bind the exact operator input ID and classification.
324. `implemented` Bind artifact reference, artifact digest, and receipt digest.
325. `implemented` Bind issuer principal and public-key identity.
326. `implemented` Bind explicit issue and expiry times.
327. `implemented` Bind a unique 256-bit nonce.
328. `implemented` Require Ed25519 as the exact signature algorithm.
329. `implemented` Keep attestations evidence-only with no authorization or execution effect.
330. `implemented` Commit only synthetic public keys and signatures; retain no private-key material.

## Phase AE — Evidence trust verification

331. `implemented` Add strict duplicate-key and non-finite-number rejection.
332. `implemented` Add deterministic canonical JSON and SHA-256 identities.
333. `implemented` Validate registry, candidate, attestations, and generated receipt against governed schemas.
334. `implemented` Require every supplied candidate input to have a matching evidence policy.
335. `implemented` Reject attestations for absent candidate inputs.
336. `implemented` Require exact candidate, classification, artifact, and receipt cross-bindings.
337. `implemented` Require the attestation issuer to resolve to an active principal.
338. `implemented` Require the issuer to be scoped to the exact input and permitted issuer role.
339. `implemented` Require the key to belong to the issuer and remain active.
340. `implemented` Verify canonical Ed25519 signatures using the governed public key.

## Phase AF — Freshness and revocation closure

341. `implemented` Verify public-key bytes reproduce the registered key digest.
342. `implemented` Require canonical base64 for public keys and signatures.
343. `implemented` Reject future-dated attestations outside configured clock skew.
344. `implemented` Reject invalid attestation issue/expiry ordering.
345. `implemented` Reject attestations signed outside key validity.
346. `implemented` Reject expired attestations.
347. `implemented` Reject attestations older than the per-input freshness ceiling.
348. `implemented` Reject effective principal, key, or attestation revocation.
349. `implemented` Require configured distinct-attestor counts for every supplied input.
350. `implemented` Emit one deterministic trust receipt with authority ceiling `none`.

## Phase AG — Transition authorization candidate

351. `implemented` Define `TransitionAuthorizationCandidate` as a preflight-only contract.
352. `implemented` Bind the exact operator candidate and compilation receipt.
353. `implemented` Bind the exact trusted-evidence receipt.
354. `implemented` Bind one exact compiled preparation-plan digest.
355. `implemented` Bind decision type, domain, action, risk tier, and authorization mode.
356. `implemented` Bind distinct proposer and executor principals.
357. `implemented` Bind one exact executor capability.
358. `implemented` Bind one exact delegated-grant identity and digest.
359. `implemented` Bind predecessor, target, and rollback digests.
360. `implemented` Bind signed approval, rejection, abstention, and audit contributions without constructing a mandate.

## Phase AH — Policy, grant, and executor preflight

361. `implemented` Require each transition decision to resolve to exactly one operational policy.
362. `implemented` Reject authorization-mode drift from the selected policy.
363. `implemented` Require an active scoped proposer.
364. `implemented` Require an active scoped executor distinct from the proposer.
365. `implemented` Require the executor capability to match policy exactly.
366. `implemented` Require the executor principal to possess that exact capability.
367. `implemented` Reproduce and bind the complete delegated-grant digest.
368. `implemented` Verify active grant status, validity interval, domain, permission, risk ceiling, and rollback requirement.
369. `implemented` Reject effective grant revocation.
370. `implemented` Require the delegated grant subject to participate in the counted approval set when policy requires a grant.

## Phase AI — Quorum, separation of duties, and rollback proof

371. `implemented` Verify every approval signature against the exact authorization candidate and contribution.
372. `implemented` Reject duplicate approval IDs, nonces, and repeated principal contributions.
373. `implemented` Require approval principals and keys to remain active and in scope.
374. `implemented` Reject approvals signed outside key validity or after effective revocation.
375. `implemented` Preserve independent first-pass contributions.
376. `implemented` Require conflict declaration and recusal behavior.
377. `implemented` Prevent the proposer from approving when policy forbids it.
378. `implemented` Prevent the executor from approving when policy forbids it.
379. `implemented` Enforce role-specific quorum, independent audit, and reject thresholds.
380. `implemented` Require rollback to restore the exact predecessor and target to differ from the predecessor.

## Phase AJ — Adversarial proof, workflow, and packaging

381. `implemented` Pin a synthetic operational authority registry with no real private identities.
382. `implemented` Pin eight signed synthetic evidence attestations.
383. `implemented` Pin the trusted-evidence receipt and all statement digests.
384. `implemented` Pin a signed mixed-quorum transition authorization candidate.
385. `implemented` Pin the transition-preflight receipt at `eligible-for-mandate-construction`.
386. `implemented` Add eleven adversarial evidence-trust tests.
387. `implemented` Add fourteen adversarial transition-preflight tests.
388. `implemented` Add one aggregate operational-trust validator and focused read-only workflow.
389. `implemented` Add the five contracts to governance, review routing, the aggregate suite, and the reproducible package.
390. `provisional` Reproduce all 38 aggregate commands and the offline package on the exact final checkpoint-400 head.

## Phase AK — Real operational trust and live-transition frontier

391. `blocked` Promote a real operational authority registry under the constitutional hierarchy.
392. `blocked` Register real active principals, public keys, issuer scopes, executor capabilities, and revocation channels.
393. `blocked` Supply real signed attestations for the private ecology and authenticated observed inventory.
394. `blocked` Supply real signed attestations for live nodes, capability ceilings, rollback predecessors, canary, and observation plans.
395. `blocked` Supply a real sovereign issue-#42 decision and its valid signature/quorum evidence.
396. `blocked` Review, sign, issue, and register the first real delegated grant.
397. `blocked` Produce a real transition authorization candidate with required human, Mind, and independent-audit contributions.
398. `blocked` Construct the exact admission mandate from an eligible preflight receipt through a separately governed step.
399. `blocked` Execute and observe the live canary, rollback, learning, and sustained-autonomy loop with complete receipts.
400. `specified` Derive points 401–500 only from the exact final checkpoint-400 receipt plus real registry, attestation, preflight, mandate, execution, rollback, and observation receipts.

## Current interpretation

Points 301–389 are implemented repository preparation. Point 390 remains provisional until the 38-command hosted aggregate suite validates the exact final branch head. Points 391–399 remain genuinely sovereign, private, cryptographic, live, or time-dependent. Point 400 prevents the fifth hundred from being invented before those real receipts exist.
