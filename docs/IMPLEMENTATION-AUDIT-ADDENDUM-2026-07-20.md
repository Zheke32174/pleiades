# Implementation audit addendum — 2026-07-20

This addendum supersedes any conflicting status in `IMPLEMENTATION-AUDIT-2026-07-19.md` and records the implementation work performed during the follow-up reconciliation pass.

## Default-branch and repository-record changes completed

### Remaining broad backup CI trigger

The remaining broad private backup workflow was intent-gated to `ci/**`, `release/**`, and manual dispatch. Ordinary default-branch pushes and pull requests no longer launch it.

### Durable Android completion contracts

Previously unverified application repositories now contain repository-local completion records and draft non-publishing build-verification PRs. These records deliberately do not claim that an APK exists. Completion requires actual package, run, checksum, signing, artifact, and download evidence.

### Private Actions account blocker

Pleiades issue #38 owns the account-level diagnosis. Fresh private runs confirmed the same failure shape: jobs were created without exposed executable steps. That is an account/runner admission failure, not a test result.

## Implemented on reviewed branches, not yet promoted

### Container manager-state compensation

Container installation work compensates a failed systemd manager reload after file rollback, preserves both reload outcomes, exposes manager uncertainty after double failure, and includes deterministic tests. Promotion still depends on the stacked review.

### Termux live-state path hardening

Reviewed Termux work confines live state beneath `PLEIADES_ROOT`, refuses symlinked managed paths and locks, uses no-follow opens where supported, rechecks file identity, and retains separate operator-selected export paths. Successful workflow evidence remains bound to the exact reviewed commit.

### Factory Stack synchronization generations

The canonical Factory Stack implementation holds one tools-directory generation lock across catalog/lock reads, checkout mutation, final identity verification, and state publication; revalidates final checkout identities; and publishes a content-derived checkout-generation identity. Duplicate narrower repair work was removed once the stronger implementation was identified.

## Executable repair recorded, blocked before verification

### Factory orphan-observation index recovery

The private Factory branch contains a reviewable patch and one-shot verification workflow for recovery when an immutable observation file commits before index publication. The code is not credited as implemented because private Actions failed before exposing steps. The source patch remains durable and executable pending issue #38.

## Existing durable but unpromoted work confirmed

Pleiades, Factory, Factory Stack, Container, Termux, Windows, Connect, and Undergrowth pull requests preserve substantial prior-session implementation on GitHub even where default-branch promotion remains pending. Separate issues own gaps where no matching implementation was found.

## Reconciliation rule

Before opening a new repair for an existing issue:

1. inspect issue comments;
2. search open and stacked PRs;
3. compare the candidate branch with its base;
4. prefer the stronger validated implementation;
5. remove duplicate repair commits before leaving the session.

The correct states remain:

- recorded;
- executable but externally blocked;
- implemented on a branch;
- runner-verified on a branch;
- merged/default-branch complete;
- durable artifact or Release verified.

No narrower state should be described as a broader one.
