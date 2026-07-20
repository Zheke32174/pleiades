# Pleiades implementation audit and outstanding-work ledger

Date: 2026-07-20

## Purpose

This file is the durable bridge between architecture/review sessions and repository state. It records work that was discussed, discovered, partially implemented, implemented on an unmerged branch, or fully verified.

A conversational note is not a project record. Anything still outstanding must exist here, in a repository issue, or in a pull request with an explicit remaining-work statement.

## Completion semantics

Use these states consistently:

- **VERIFIED COMPLETE** — merged/default-branch code or documentation exists and the claimed runtime, package, release, or artifact result was actually verified.
- **IMPLEMENTED, NOT PROMOTED** — code exists in an open branch or pull request but has not reached the default branch or durable release surface.
- **RECORDED, NOT IMPLEMENTED** — the requirement exists in an issue, PR body, or this ledger, but executable work remains.
- **BLOCKED EXTERNALLY** — repository work is ready but an account, provider, hardware, credential, or policy boundary prevents verification.
- **NEEDS RE-AUDIT** — prior sessions reported a result, but the current pass could not independently retrieve the final evidence.

Workflow YAML by itself does not prove a build or release. A release is complete only when the intended downloadable asset and verification material are actually present and retrievable.

## Confirmed implemented on default branches

### Attribution and public-release documentation

- `Zheke32174/pleiades/CREDITS.md` exists and records third-party projects, organizations, licenses, usage, vendoring, modification, and local-path handling.
- `Zheke32174/pleiades-container/CREDITS.md` exists with the same attribution contract for the container substrate.
- `Zheke32174/pleiades/tools/TOOL-FRAMEWORK.md` now links to `../CREDITS.md`; the retired absolute `/workspaces/gentoo/CREDITS.md` reference is no longer the accreditation pointer.

### GitHub Actions noise containment

The July 19 workflow-containment pass implemented the following:

- quarantined the duplicated five-minute Understory relay runners;
- quarantined the two hourly Gemini scheduled-triage workflows;
- quarantined automatic Gemini event dispatch in both Underhall repositories;
- removed ambient schedules from the identified private maintenance workflows;
- intent-gated broad private CI workflows behind `ci/**`, `release/**`, or manual dispatch;
- replaced release-on-every-default-branch-push workflows with tag/manual release contracts;
- separated Android build intent from release publication intent in the Recall workflows;
- corrected `purple-team-polyglot-backup-wslbak/.github/workflows/ci.yml`, the one broad trigger that had remained after the earlier pass.

The account-level reason private GitHub-hosted Actions were previously rejected before job execution remains unresolved. It is owned durably by Pleiades issue #38:

`https://github.com/Zheke32174/pleiades/issues/38`

### Audit preservation

This ledger was committed to the Pleiades default branch so that session discoveries and implementation state no longer depend on conversation history.

Repository-local release-status records also exist in:

- `Zheke32174/recall-xed-editor-c8278404e4/RELEASE-STATUS.md`;
- `Zheke32174/recall-underward-d0ccef5ee4/RELEASE-STATUS.md`.

## Android application estate

### Yojimbo

State: **IMPLEMENTED, NOT PROMOTED**

Durable records:

- PR #2: `https://github.com/Zheke32174/understory-yojimbo/pull/2`
- PR #3: `https://github.com/Zheke32174/understory-yojimbo/pull/3`
- PR #4: `https://github.com/Zheke32174/understory-yojimbo/pull/4`
- PR #6: `https://github.com/Zheke32174/understory-yojimbo/pull/6`

PR #6 produced a successful assembled engineering-preview APK in GitHub Actions. The APK existed as an unexpired artifact during the July 19 verification pass. The release machinery remains stacked behind the runtime PR chain and is not yet merged to the default branch. A durable Releases-page publication therefore remains pending.

Completion requires:

1. resolve/rebase and merge the stacked runtime chain in order;
2. merge the engineering-preview release work;
3. run the default-branch release path;
4. verify the actual Release asset, checksum, source identity, package identity, and signing posture.

### Genji/Yojimbo rootless framework-capacity trajectory

State: **RECORDED, NOT IMPLEMENTED AS A COMPLETE SYSTEM**

The complete conversation-defined trajectory is preserved in `undergrowth` draft PR #30:

`https://github.com/Zheke32174/undergrowth/pull/30`

That record includes the Genji transformation/forge boundary, Yojimbo authority-provider boundary, Android work-profile surface, virtual/Ghost-world laboratory, safe/live versus hyper-augmentation split, implementation phases, rejection and rollback rules, and the prohibition on using the current Samsung as the framework-level experimental target.

The PR is documentation preservation only. It must not be cited as a completed rootless Xposed-/Frida-/framework-capacity implementation.

### Recall Xed Editor

State: **VERIFICATION INTENT OPEN; BUILD NOT YET VERIFIED**

Repository: `https://github.com/Zheke32174/recall-xed-editor-c8278404e4`

Durable records:

- repository-local completion contract: `RELEASE-STATUS.md`;
- build-verification branch: `ci/verify-apk-20260719`;
- draft PR #1: `https://github.com/Zheke32174/recall-xed-editor-c8278404e4/pull/1`.

The branch contains only a non-publishing CI intent marker. This audit has not yet retrieved a completed package from a durable Release or current Actions artifact, so no APK claim is made.

Completion requires retained exact-commit package output, checksum, package/signing record, workflow-run identity, artifact identity, and a verified durable Release when publication is intended.

### Recall Underward

State: **VERIFICATION INTENT OPEN; BUILD NOT YET VERIFIED**

Repository: `https://github.com/Zheke32174/recall-underward-d0ccef5ee4`

Durable records:

- repository-local completion contract: `RELEASE-STATUS.md`;
- build-verification branch: `ci/verify-apks-20260719`;
- draft PR #1: `https://github.com/Zheke32174/recall-underward-d0ccef5ee4/pull/1`.

The branch contains only a non-publishing CI intent marker. This audit has not yet retrieved the expected package set from a durable Release or current Actions artifact, so no APK-set claim is made.

Completion requires retention of every expected package output and checksum, expected-versus-produced inventory, package/signing records, exact-commit provenance, workflow-run identity, artifact identity, and verification of a durable Release when publication is intended.

### Other Android repositories

Prior sessions reported 27 durable Releases across the public and private Android repositories. That claim remains **NEEDS RE-AUDIT** until a current release-asset inventory is captured in GitHub-accessible evidence. Do not infer completion from workflow files or old notifications.

## PDK authority, continuity, and ingress

The PDK sequence is a stacked implementation graph. Every item below is durable on GitHub; none should be described as merged merely because its branch is green.

### Implemented, not promoted

- PR #7 — restart-safe grant sequence, identity, expiry, and use continuity.
- PR #10 — transactional grant admission, signed admission receipts, durable revocation tombstones, compaction-safe restriction history, and SQLite-owned mutable use budgets.
- PR #20 — shared observation-ingress batch, receipt, and delivery-stream contracts.
- PR #23 — durable controller event identity, exact retry, collision refusal, and signed acknowledgement continuity.
- PR #24 — durable heartbeat replay floors, exact retry acknowledgements, and restart-safe accepted observations.
- PR #30 — explicit grant phases: deterministic validation without active-cache mutation, transactional admission, then active installation. Final implementation branch contains only `policy.rs` and `rpc.rs`; PDK diagnostics must remain green before promotion.

### Recorded, not yet implemented completely

- issue #6 — live Alienware/Lenovo capability, partition, expiry, revocation, audit, recovery, and rollback validation.
- issue #8 — original transactional authority-coherence discovery, substantially implemented by PR #10.
- issue #9 — compose defensive-substrate PR #2 with PDK PR #5 without competing control planes or losing either CI hard gate.
- issue #11 — durable lease-expiry reconciliation state and ordered cleanup receipts.
- issue #13 — authenticated capability-revocation protocol over the existing durable tombstone primitive.
- issue #14 — atomically bind one durable capability use to its operation-intent receipt.
- issue #15 — validation/admission/cache split, implemented on draft PR #30 but not promoted.
- issue #16 — durable collision-safe controller event acknowledgements, implemented on PR #23 but not promoted.
- issue #17 — durable heartbeat continuity, implemented on PR #24 but not promoted.
- issue #18 — bind capability exercise to a stable authenticated invoker principal rather than bearer possession.
- issue #19 — substrate-neutral authenticated observation ingress shared by Windows, Android/Termux, and later sensors.
- issue #25 — durable current-observation reads, boot-epoch selection, and compaction preserving anti-replay identity.

## Factory evidence and source provenance

- `pleiades-factory` issue #4 and PR #5 — **IMPLEMENTED, NOT PROMOTED** immutable, content-addressed evidence generations.
- `pleiades-factory` issue #6 — **RECORDED, NOT IMPLEMENTED** recovery of an observation committed before index publication.
- `pleiades-factory-stack` issue #5 and PR #6 — **IMPLEMENTED, NOT PROMOTED** transactional locks and honest dirty-source identity.
- `pleiades-factory-stack` issue #7 — **RECORDED, NOT IMPLEMENTED** serialization of synchronization and state binding to one checkout generation.
- Pleiades PR #22 — **IMPLEMENTED, NOT PROMOTED** immutable review-eligibility generations and conservative evidence aggregation contract.

## Cognition and objective-runtime boundaries

### Automaton

State: **IMPLEMENTED, NOT PROMOTED AS A BOUNDARY CORRECTION**

- `automaton` PR #2: `https://github.com/Zheke32174/automaton/pull/2`

The PR corrects the fork from an inaccurately proposal-only runtime declaration to a reference-only component with no authority. It records `Conway-Research/automaton` as upstream provenance and prohibits launching the repository itself as a MODOS workload. Useful mechanisms must be extracted or rebuilt behind bounded adapters and separate promotion evidence.

No Automaton runtime mechanism has thereby become a promoted Pleiades implementation.

### Developing Mind reproduction

State: **IMPLEMENTED, NOT PROMOTED**

- PR #2: `https://github.com/Zheke32174/developing-mind-reproduction/pull/2` — publication is opt-in, proposal-branch-only, and refuses `main`/`master`.
- PR #4: `https://github.com/Zheke32174/developing-mind-reproduction/pull/4` — daily governance derives from typed action outcomes, verification, rollback/refinement evidence, unresolved failures, and normalized record identity rather than Markdown existence or fixed synthetic traces.

PR #4 remains stacked and must obtain executed green CI before its governance result may be described as runner-validated. A passing governance record remains evidence for orchestration, not a promotion transaction.

### System Soul Core

State: **BOUNDARY DECLARED ON DEFAULT BRANCH; RUNTIME RE-AUDIT REQUIRED**

- merged PR #1: `https://github.com/Zheke32174/system-soul-core/pull/1`

The component declaration preserves persistent identity, scoped memory, handoff continuity, and the principle that a durable cognitive assembly does not gain ambient domain authority. This audit has not yet established a separate complete runtime-hardening receipt for every implementation path in that repository.

### Understory objective runtime

State: **IMPLEMENTED, NOT PROMOTED; LIVE RUNTIME VALIDATION OUTSTANDING**

- historical admission/approval/migration receipt: Understory PR #32;
- current-master runner policy/custody implementation: Understory PR #34;
- remaining fake-backend, cancellation, restart, process-ownership, duplicate-execution, and live migration work: Understory issue #33.

PR #34 enforces review-first behavior inside the historical runner path, removes shell-string verification from the effective policy boundary, adds deterministic file verification, atomic private custody, symlink refusal, quarantine receipts, and a service launcher that loads policy before providers. It does not prove real provider execution or live-estate migration.

## Private ontology, inheritance, and recovery

- `undergrowth` PR #19 — **IMPLEMENTED, NOT PROMOTED** private resource spine and repository ontology.
- `undergrowth` PR #24 — **RECORDED DESIGN** separating ecology membership from runtime inheritance.
- `undergrowth` PR #27 — **IMPLEMENTED, NOT PROMOTED** inert default inheritance, explicit profiles, sensitive-estate receipts, and third-party setup containment.
- `undergrowth` PR #30 — **RECORDED CANON** for Genji/Yojimbo rootless framework-capacity work.
- `undercity` PR #5 — **IMPLEMENTED, NOT PROMOTED** staged and digest-bound rootfs recovery plus atomic encrypted configuration custody. A real production-archive restore remains a disposable-VM gate.

## Host and edge adapters

- `pleiades-container` issue #8 and PR #9 — transactional host binding and ambient nspawn-settings refusal.
- `pleiades-container` issue #10 — **implemented on PR #9 and closed as completed**. The branch performs a compensating manager reload, preserves both failure results, reports uncertainty on double failure, and includes deterministic tests. The implementation is still unmerged.
- `pleiades-termux` issue #3 and Pleiades issue #19 — authenticated delivery/acknowledgement design.
- `pleiades-termux` PR #5 — delivery-stream continuity without transport.
- `pleiades-termux` issue #6 — symlink-safe state and lock handling.
- `pleiades-windows` PR #6 — typed canonical WSL lifecycle argv and shell-injection removal.
- `pleiades-connect` PR #3 — signed short-lived SSH route assertions.

## Distribution and release hardening

- `pleiades-factory-stack` PR #4 — deterministic tagged source release, checksums, SPDX inventory, and exact-commit receipt.
- `pleiades-termux` PR #4 — honest source release, retention, licensing, and removal controls.
- `pleiades-windows` PR #4 — installable/distributable observer contract.
- `pleiades-container` PR #6 — distributable and reviewable container substrate.

## Outstanding work that was previously easy to mistake for implementation

1. **Release workflow present, but no release asset verified.** Applies currently to Yojimbo, Recall Xed, and Recall Underward until evidence says otherwise.
2. **Open PR exists, but change is not on the default branch.** The stacked Pleiades/MODOS, cognition, Factory, adapter, and recovery graphs must not be described as merged implementation.
3. **Issue specifies a repair, but no code has landed.** Pleiades issues #11, #13, #14, #18, #25; Factory issue #6; Factory Stack issue #7; Termux issue #6; and Understory issue #33 are current examples.
4. **A documentation canon exists, but the system does not.** Undergrowth PR #30 preserves the Genji/Yojimbo design; it is not the implementation.
5. **A component declaration exists, but runtime paths may remain unaudited.** System Soul Core and other early Epoch declarations require code-surface review before stronger claims.
6. **Actions failure noise was contained, but the private Actions account restriction was not diagnosed at the account banner/billing/policy layer.** Pleiades issue #38 owns that work.
7. **Prior release counts require a current asset inventory.** Do not preserve old numbers as fact without retrievable evidence.
8. **Live-hardware validations remain separate from repository CI.** Pleiades issue #6 and the repository-specific device/VM issues cannot be completed by documentation or static tests alone.

## Implementation order

1. Keep every newly discovered gap durable in an issue, PR, or this ledger before ending a review session.
2. Finish exact, narrow correctness repairs on already-reviewed stacks before opening broad new waves.
3. Complete and green Pleiades PR #30, then continue the authority stack with issue #14 or #13 according to dependency order.
4. Obtain executed green validation for Developing Mind PR #4 and Understory PR #34.
5. Finish the current-observation/boot-epoch read boundary in Pleiades issue #25.
6. Produce and retain verified Xed and Underward Android build outputs through draft PRs #1 in their respective repositories.
7. Merge and publish the Yojimbo engineering-preview stack after review.
8. Resolve Pleiades issue #38 and run one private canary from each workflow family.
9. Capture a machine-readable Android release/artifact inventory rather than relying on remembered counts.
10. Continue Pleiades issue #4 repository-by-repository with explicit dispositions: canonical, active-supporting, upstream/reference, archive, or delete candidate.

## Rule for future sessions

Before claiming a task is finished, record all four identities where applicable:

- repository and default-branch commit;
- pull request or issue that owns the change;
- workflow run/test evidence;
- durable artifact or Release asset identity.

When any identity is absent, state the narrower truth: recorded, implemented on a branch, built as an artifact, or verified complete.
