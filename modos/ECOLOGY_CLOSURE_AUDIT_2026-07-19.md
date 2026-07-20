# Ecology closure audit — 2026-07-19

This ledger prevents repair findings from existing only in review sessions. Every unresolved item below is represented by an issue or draft pull request on GitHub.

Status meanings:

- **implemented draft** — concrete branch or pull request exists;
- **tracked** — issue exists but implementation remains;
- **evidence gate** — implementation exists but live or device validation remains;
- **runner blocked** — implementation exists but hosted validation did not execute.

## PDK and authority

- Implemented draft: `Zheke32174/pleiades#10` transactional authority continuity.
- Tracked: `Zheke32174/pleiades#15` separate grant validation, durable admission, and cache installation.
- Tracked: `Zheke32174/pleiades#14` atomic capability-use and authorization-intent receipts.
- Tracked: `Zheke32174/pleiades#13` authenticated capability revocation.
- Tracked: `Zheke32174/pleiades#11` durable lease-expiry reconciliation.
- Tracked: `Zheke32174/pleiades#18` stable invoker-principal capability binding.
- Evidence gate: `Zheke32174/pleiades#6` Alienware–Lenovo lease and autonomy matrix.
- Tracked: `Zheke32174/pleiades#9` lean defensive substrate and PDK integration.

## Controller and ingress continuity

- Implemented draft and green: `Zheke32174/pleiades#23` durable exact signed-event admission and acknowledgement.
- Implemented draft and green: `Zheke32174/pleiades#24` durable heartbeat continuity.
- Tracked: `Zheke32174/pleiades#25` current-observation reads, boot epochs, and retention.
- Implemented contract and green: `Zheke32174/pleiades#20` shared observation-ingress batches, receipts, and stream state.
- Tracked continuation: `Zheke32174/pleiades#19`, `Zheke32174/pleiades-termux#3`, and `Zheke32174/pleiades-windows#3`.

## Factory and source provenance

- Implemented public contract and green: `Zheke32174/pleiades#22` immutable review-eligibility generations.
- Implemented draft, runner blocked: `Zheke32174/pleiades-factory#5` immutable evidence ledger.
- Tracked: `Zheke32174/pleiades-factory#6` orphan observation/index recovery.
- Tracked parent design: `Zheke32174/pleiades-factory#4`.
- Implemented draft and green: `Zheke32174/pleiades-factory-stack#6` transactional source locks and honest dirty state.
- Tracked: `Zheke32174/pleiades-factory-stack#7` serialized synchronization and one checkout-state generation.
- Tracked in `Zheke32174/pleiades-factory-stack#5`: exact remote-ref/annotated-tag identity and recursive dependency locks.

## Inheritance and Understory

- Implemented draft: `Zheke32174/undergrowth#27` inert default inheritance with explicit compatibility and sensitive-repository gates.
- Tracked: `Zheke32174/undergrowth#28` re-source receipt and stale-success invalidation.
- Tracked resolver continuation: `Zheke32174/undergrowth#26`.
- Profile design: `Zheke32174/undergrowth#24`.
- Tracked/evidence gate: `Zheke32174/understory#33` legacy objective migration and review-first runner containment.

## Adapter and substrate follow-ups

- Implemented draft and green: `Zheke32174/pleiades-container#9`; tracked manager-state compensation: `Zheke32174/pleiades-container#10`.
- Implemented draft and green: `Zheke32174/pleiades-windows#6`; tracked exact-object status validation: `Zheke32174/pleiades-windows#7`.
- Implemented draft and green: `Zheke32174/pleiades-termux#5`; tracked state-path and lock symlink refusal: `Zheke32174/pleiades-termux#6`.
- Tracked exact route retry identity: `Zheke32174/pleiades-connect#5`.
- Evidence gate: `Zheke32174/pleiades-connect#4`.

## Additional public-repository findings

All are durable GitHub issues:

- `Zheke32174/notebook-rollout#2` — selector false success.
- `Zheke32174/DevPulse#2` — Git failure classification and ahead-count correctness.
- `Zheke32174/mem-watchdog#2` — blocking RED alert suspends sampling.
- `Zheke32174/developing-mind-reproduction#3` — governance based on simulated rather than actual evidence.
- `Zheke32174/colab-gpu-node#2` — mixed unchecked restore generations.
- `Zheke32174/scandroid#11` — unsigned mutable endpoint discovery.
- `Zheke32174/FactoryScope#2` — observability versus mutation authority.
- `Zheke32174/fixxy-deck-app#2` — WebView origin validation.
- `Zheke32174/mcp-smart-typer#2` — masked CI failures and false package provenance.
- `Zheke32174/backend-tester#2` — over-authorized backend health probes.
- `Zheke32174/alien#4` — untrusted archive extraction validation.

## Immediate implementation order

1. Windows exact-object snapshot validation.
2. Termux state-path and lock symlink refusal.
3. Container compensating manager reload.
4. Factory orphan observation/index repair and executable validation receipt.
5. Factory Stack synchronization serialization.
6. PDK durable current-observation and boot-epoch read semantics.
7. PDK invoker binding, atomic intent receipts, authenticated revocation, and expiry reconciliation.
8. Reviewable Understory runner replacement modules.
9. Smaller public-repository correctness issues before the larger archive, restore, and endpoint-identity repairs.

## Closure rule

An item leaves this ledger only when it is implemented with attributable validation, explicitly superseded, closed with a recorded reason, or retained as a named live/device evidence gate. This ledger authorizes no merge, release, deployment, device mutation, or default-branch change.