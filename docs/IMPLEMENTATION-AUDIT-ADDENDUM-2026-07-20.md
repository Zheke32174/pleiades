# Implementation audit addendum — 2026-07-20

This addendum supersedes any conflicting status in `IMPLEMENTATION-AUDIT-2026-07-19.md` and records the implementation work performed during the follow-up reconciliation pass.

## Default-branch and repository-record changes completed

### Remaining broad backup CI trigger

`Zheke32174/purple-team-polyglot-backup-wslbak/.github/workflows/ci.yml` is now intent-gated to `ci/**`, `release/**`, and manual dispatch. Ordinary default-branch pushes and pull requests no longer launch that private backup workflow.

### Durable Android completion contracts

The two previously unverified Recall repositories now contain repository-local completion records:

- `recall-xed-editor-c8278404e4/RELEASE-STATUS.md`;
- `recall-underward-d0ccef5ee4/RELEASE-STATUS.md`.

Each repository also has a draft non-publishing build-verification PR:

- Xed PR #1 — `ci/verify-apk-20260719`;
- Underward PR #1 — `ci/verify-apks-20260719`.

These records deliberately do not claim that an APK exists. Completion requires actual package, run, checksum, signing, artifact, and download evidence.

### Private Actions account blocker

Pleiades issue #38 now owns the account-level diagnosis:

`https://github.com/Zheke32174/pleiades/issues/38`

A fresh private Factory run confirmed the same failure shape: Actions run `29710189855` created job `88252948974` with no exposed steps. That is an account/runner admission failure, not a Python test result.

## Implemented on reviewed branches, not yet promoted

### Container manager-state compensation

`pleiades-container` issue #10 is implemented on PR #9. The installer now compensates a failed systemd manager reload after file rollback, preserves both reload outcomes, exposes manager uncertainty after double failure, and has deterministic tests. The issue was closed as the implementation checkpoint; promotion still depends on the stacked PR review.

### Termux live-state path hardening

`pleiades-termux` issue #6 is implemented on PR #5 at verified commit:

`1092a2894f850b8dc679f4d146ca59d24ecdc37d`

Actions run `29709571192` passed patch application, Python compilation, full unit discovery, shell parsing, and uninstall tests before committing the repair. The runtime now confines live state beneath `PLEIADES_ROOT`, refuses symlinked managed paths and locks, uses no-follow opens where supported, rechecks file identity, and retains separate operator-selected export paths. Temporary one-shot workflows were removed after success.

### Factory Stack synchronization generations

`pleiades-factory-stack` issue #7 was already implemented more comprehensively in draft PR #8 at:

`731b987bc250b2a833433da54f7f46375f1eaf94`

The canonical implementation holds one tools-directory generation lock across catalog/lock reads, checkout mutation, final identity verification, and state publication; revalidates final checkout identities; and publishes a content-derived checkout-generation identity. CI run #47 passed at that exact head.

A narrower duplicate repair was briefly generated on PR #6 during this audit. Once PR #8 was discovered, the PR #6 branch was reset to its exact prior head `0f165883870bc3575d9b0d5aa6b8add21cc40f6f`, removing all duplicate and temporary commits. PR #8 remains the sole canonical implementation.

## Executable repair recorded, blocked before verification

### Factory orphan-observation index recovery

`pleiades-factory` issue #6 now has all of the following on PR #5's branch:

- reviewable patch: `patches/issue-6-orphan-observation-recovery.patch`;
- one-shot patch workflow;
- PR-triggered `git apply --check`/test/commit workflow;
- issue comment documenting the exact completion boundary.

The patch restores a missing observation-index entry on an exact retry when the immutable observation file was committed before index publication. Its adversarial test forces that failure window, verifies idempotent recovery, and verifies use of the recovered evidence in evaluation.

The code is not yet credited as implemented because private Actions run `29710189855` failed before exposing any steps. The source patch remains durable and executable pending issue #38.

## Existing durable but unpromoted work confirmed

The following are not conversation-only notes:

- Pleiades PR #23 implements durable signed event/acknowledgement continuity for issue #16.
- Pleiades PR #24 implements durable heartbeat continuity for issue #17 and carries successful CI evidence.
- Pleiades issue #25 owns the separate current-observation/boot-epoch read and compaction boundary; no matching implementation PR was found during this pass.
- Pleiades PRs #20–#24, Factory PR #5, Factory Stack PRs #6 and #8, Container PR #9, Termux PR #5, Windows PR #6, Connect PR #3, and Undergrowth PR #27 preserve substantial prior-session implementation on GitHub even where default-branch promotion remains pending.

## Reconciliation rule

Before opening a new repair for an existing issue:

1. inspect issue comments;
2. search open and stacked PRs;
3. compare the candidate branch with its base;
4. prefer the stronger validated implementation;
5. remove any duplicate repair commits before leaving the session.

The correct states remain:

- recorded;
- executable but externally blocked;
- implemented on a branch;
- runner-verified on a branch;
- merged/default-branch complete;
- durable artifact or Release verified.

No narrower state should be described as a broader one.
