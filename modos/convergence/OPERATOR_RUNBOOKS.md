# Pleiades Convergence and Live-Transition Runbooks

These runbooks begin where autonomous repository work ends. They do not authorize a history rewrite, issue a grant, deploy a candidate, contact a node, or supply private information merely by existing.

Never paste private keys, credentials, recovery secrets, private registry contents, or identity-bearing local paths into public issues, pull requests, workflow inputs, or receipts. Public records should carry opaque references and non-placeholder digests only.

## 1. Aggregate convergence suite

### Preconditions

- Work from the exact reviewed source commit.
- Use CPython 3.12 and the dependency versions in `requirements-modos.txt`.
- Keep the checkout offline during validation after dependencies are provisioned.
- Ensure `artifacts/` is empty or archived before beginning.

### Procedure

1. Run `bash ci/run-modos-offline.sh`.
2. Confirm `artifacts/convergence-suite-receipt.json` reports `status: pass`.
3. Confirm every command in the receipt has `status: pass` and an exit code of zero.
4. Confirm `artifacts/current-tree-sensitivity-receipt.json` reports `status: clear`.
5. Confirm `artifacts/synthetic-rehearsal-receipt.json` reports `status: pass`.
6. Confirm `artifacts/intervention-frontier.json` contains no autonomous repository actions.
7. Retain all receipts by digest in the private evidence spine when selected for promotion evidence.

### Failure handling

- Do not skip a failed command.
- Repair the earliest dependency failure first.
- Re-run the entire suite after a repair; do not splice receipts from different commits.
- A hosted runner failure is not overridden by an unrecorded local claim.

## 2. Private exhaustive-registry closure

### Required operator input

- The actual private exhaustive registry from Undergrowth.
- Its provenance and source digest.
- A fresh authenticated observed repository inventory export.

### Procedure

1. Keep the private registry outside the public checkout.
2. Validate it against `modos/contracts/ecology-registry.schema.json`.
3. Run `ci/validate-ecology.py` with both `--registry` and `--observed-inventory`.
4. Require exact agreement between registry and observed inventory.
5. Compile the public and private scopes through the ecology ontology adapter.
6. Produce a combined closure receipt that binds both source digests and the resulting snapshot digest.
7. Store private artifacts in the private evidence spine; publish only authorized opaque digests and status.

### Stop conditions

- Unclassified repository.
- Missing or duplicate lifecycle membership.
- Unknown required relation target.
- Ambiguous canonical scope.
- Source-digest mismatch.
- Private data would be exposed by the proposed public receipt.

## 3. Delegated authority grant issuance and revocation

### Issuance prerequisites

- Promoted constitutional policy permits the exact domain, action, and risk tier.
- The persistent `mindId` is the intended principal.
- Issuer and public-key identity are designated.
- Grant validity, budgets, domains, permissions, and revocation path are explicit.
- The Mind is not issuing or enlarging its own grant.

### Issuance procedure

1. Generate the unsigned grant candidate without private key material.
2. Validate the grant and authority-registry closure locally.
3. Review the semantic authority diff: domains, permissions, ceiling, time, budgets, and delegation.
4. Sign only the exact canonical digest through the approved issuer process.
5. Register the issuance event and retain the signed receipt.
6. Verify that the effective grant set contains exactly the expected generation.

### Suspension or revocation

1. Classify the event as suspension or terminal revocation.
2. Bind the exact grant ID and generation.
3. Record the authorized actor, reason digest, and effective time.
4. Re-run registry closure.
5. Confirm no mandate can use the grant after the event.
6. Never rehydrate a revoked generation; issue a separately authorized new generation if appropriate.

## 4. Canary deployment

### Required operator input

- Live node identities and public-key digests.
- Capability and write-scope receipts.
- Exact predecessor and target digests.
- One selected canary node.
- Authorized mandate and active grant.

### Procedure

1. Run the convergence suite against the exact source commit.
2. Confirm the node registry contains unique hardware, service, and key identities.
3. Confirm every target node supports exact rollback.
4. Build a rollout plan whose first and only canary stage contains the selected canary.
5. Bind health gates, replay nonce, idempotency key, timeout, and maximum parallelism.
6. Close the rollout plan without contacting nodes.
7. Obtain the required authorized decision.
8. Execute only the canary stage.
9. Observe all required postconditions before allowing any later stage.
10. Stop immediately on health-gate failure or evidence ambiguity.

## 5. Rollback after failed postconditions

1. Freeze stage advancement.
2. Preserve precondition, execution, and failed-postcondition evidence.
3. Invoke only the exact rollback action named by the mandate.
4. Restore the exact predecessor digest; a merely “healthy” different state is not sufficient.
5. Verify that the executor did not alter target, scope, or authority.
6. Emit execution, rollback, and append-only audit receipts.
7. Feed the independently verified outcome into the learning spine.
8. Revoke or suspend the mandate when continued execution is unsafe.
9. Do not retry until policy classification and evidence review explicitly permit it.

## 6. Emergency safe mode and recovery quorum

### Entry conditions

- Partial Mind loss.
- Severe node loss.
- Control-link integrity failure.
- Evidence of unsafe active authority.
- Recovery cannot proceed safely through the ordinary path.

### Safe-mode procedure

1. Enter the promoted safe-mode ceiling.
2. Permit only containment, isolation, rollback, and evidence preservation.
3. Expire emergency authority automatically within the configured maximum window.
4. Preserve all dissent and degraded-state observations.
5. Require the configured recovery quorum before restoring broader operation.
6. Resolve every grant against the registry; do not infer authority from cached state.
7. Rehydrate active grants only. Never restore revoked generations.
8. Require post-event review before returning to ordinary autonomous operation.

## 7. Public-history rewrite authorization and recovery

A history rewrite is a sovereign repository action. Current-tree redaction does not authorize it.

### Decision

1. Review issue `github:Zheke32174/pleiades#42` and the privacy-preserving reachable-history scan.
2. Approve or decline the rewrite explicitly.
3. If declined, retain the release blocker and do not claim clean public history.
4. If approved, sign the exact rewrite plan digest and affected-ref inventory.

### Approved rewrite preparation

1. Freeze merges and branch creation for affected refs.
2. Export all refs and record their old commit identities privately.
3. Identify every affected open PR, release ref, and collaborator clone.
4. Prepare replacements without including removed sensitive strings in public artifacts.
5. Test the rewrite in an isolated mirror.
6. Run the full reachable-history sensitivity scan against the mirror.
7. Confirm release and rollback plans before any force update.

### Force update and recovery

1. Force-update only the authorized ref set.
2. Rebase or recreate affected open branches deliberately.
3. Re-run all convergence, release, and sensitivity gates.
4. Notify collaborators to replace stale clones rather than merge old history.
5. Retain the private rewrite provenance and old/new ref map.
6. If validation fails, restore the authorized pre-rewrite refs from the private recovery map.

## 8. Evidence archival and retention

- Public receipts contain only public-safe evidence and opaque digests.
- Private execution evidence, private registry data, signed grants, and rewrite maps belong in private retention.
- Preserve append-only ordering and original digests.
- Apply visibility and retention classes from the learning spine.
- Corrections reference earlier evidence; they do not erase it.
- Contradictions remain visible until resolved by later evidence.
- Expiration of a hosted workflow artifact does not invalidate a separately retained matching digest.
- Never treat narrative summaries as a substitute for source evidence.

## 9. Sustained bounded-autonomy observation

### Authorization

- Define the exact duration before starting.
- Define permitted domains, grants, nodes, and risk ceilings.
- Define health, rollback, policy-violation, and recovery metrics.
- Define who may terminate the interval early.

### Observation

1. Record every proposal, decision, mandate, execution, rollback, correction, and outcome.
2. Verify that no model acts as an independent sovereign principal.
3. Verify that no executor acquires decision authority.
4. Verify grant expiry, suspension, and revocation behavior.
5. Exercise safe rollback under at least one authorized bounded failure condition when appropriate.
6. Compare simulated and observed outcomes.
7. Track calibration error and competence by domain/action/risk tier.
8. Require ordinary-person comparison for user-facing changes.
9. Stop on constitutional drift, authority escape, unrecoverable state, or evidence discontinuity.

### Completion

- The full authorized duration has elapsed.
- Evidence continuity is intact.
- Every consequential action has a matching authorization and outcome.
- Recovery and rollback remain usable.
- Any authority-adjustment recommendation remains proposal-only until separately authorized.

## 10. Operator acceptance checklist

The operator accepts the transition only when every applicable item is true:

- [ ] Exact source commit identified.
- [ ] Aggregate convergence suite passed.
- [ ] Contract catalog and stack closure passed.
- [ ] Current public tree is sensitivity-clear.
- [ ] Reachable-history status is honestly recorded.
- [ ] Reproducible package and SBOM receipts match the reviewed commit.
- [ ] Synthetic two-scope rehearsal passed.
- [ ] Actual private ecology and observed inventory were supplied privately and closed.
- [ ] Signing issuer and public-key identity were designated.
- [ ] Live node identities, capabilities, keys, and rollback predecessors were verified.
- [ ] First delegated grant was reviewed and issued through the constitutional process.
- [ ] Canary and stop conditions were selected.
- [ ] Live-loop execution was explicitly authorized.
- [ ] First live loop completed with matching admission, observation, rollback or success, and learning receipts.
- [ ] Sustained observation interval was authorized and completed.
- [ ] Final evidence was reviewed for maintain, narrow, suspend, or growth disposition.

Unchecked sovereign or live items remain operator interventions. Repository automation must stop rather than infer consent.
