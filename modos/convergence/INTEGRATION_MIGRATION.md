# Pleiades Governance Stack Integration Migration

This plan integrates the stacked ontology/governance work without erasing review boundaries or silently rewriting public history.

## Current stack

```text
#52 ontology compiler
→ #53 promotion evidence
→ #55 delegated executive authority
→ #56 control plane
→ #57 workspace and emergency recovery
→ #58 distributed admission
→ #59 learning spine
→ #60 constitutional evolution
→ #61 ecology integration readiness
→ convergence branch
```

The convergence branch semantically reconciles the stack with current `main` and records those resolutions in `mainline-collision-map.json`.

## Commit-preservation policy

- Preserve the existing reviewed slice commits while evidence review is active.
- Do not squash away the boundaries between ontology, authority, execution, learning, constitution, and convergence.
- A later release branch may use a reviewed consolidation commit, but the original PR and commit identities remain durable provenance.
- Do not force-update the default branch or rewrite historical commits as part of ordinary integration.
- Issue #42 history remediation is a separate sovereign transaction.

## Integration order

1. Validate PR #52 against its recorded base and exact head.
2. Validate #53 through #61 in stack order using `stack-manifest.json`.
3. Review the convergence collision map and mainline imports.
4. Run the complete convergence suite at the convergence head.
5. Require a clear current-tree sensitivity receipt.
6. Run the synthetic end-to-end rehearsal.
7. Build the reproducible validation package and SBOM.
8. Confirm the intervention-frontier receipt contains no autonomous repository actions.
9. Review the remaining operator/private/live blockers.
10. Merge through the repository's normal reviewed pull-request process only after all required repository evidence passes.

## Pull-request handling

Two review strategies are valid, selected by the maintainer:

### Sequential promotion

Merge each PR in stack order. After every merge, rebase or retarget only the next immediate child, re-run its tests, and verify that its semantic diff remains unchanged.

Use this when preserving small review units is more important than reducing merge operations.

### Converged promotion

Review the complete convergence PR as the integration surface while retaining the earlier PRs as provenance and specialized review records. Merge the two-parent converged commit after all aggregate evidence passes, then close superseded child PRs with explicit references to the integrated commit.

Use this when the stack has become too deep for reliable sequential GitHub retargeting.

## Rebase rules

- Never mass-rebase every open child simultaneously.
- Rebase one dependency edge at a time.
- Compare semantic receipts and golden digests before and after each rebase.
- Treat changed generated digests as a review event, not harmless churn.
- Preserve unresolved blockers in candidate and stack manifests.
- Do not infer that a green descendant validates a modified ancestor.

## History-rewrite interaction

If issue #42 is approved for history rewrite before integration:

1. freeze this stack;
2. execute the separately authorized rewrite in an isolated mirror;
3. rescan reachable history;
4. recreate or deliberately rebase each affected branch in stack order;
5. update the stack manifest with new exact SHAs;
6. reproduce every convergence receipt;
7. do not reuse pre-rewrite signatures or attestations for new commit identities.

If the rewrite is declined or deferred, the stack may remain reviewable but no release may claim sensitivity-clear reachable public history.

## Completion evidence

Integration is complete only when all of these identities exist:

- merged/default-branch commit;
- owning pull request or explicit supersession record;
- passing convergence-suite receipt;
- current-tree sensitivity-clear receipt;
- accurate reachable-history status;
- validation package and SBOM digests;
- exact artifact or release identities when publication occurs.

Anything narrower remains implemented on a branch, runner-verified on a branch, or externally blocked—not default-branch complete.
