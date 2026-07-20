# Durable Work-Order Controller and Semantic Gateway

This directory contains the first executable runtime slice of the Pleiades Extended Autonomy Envelope.

It is deliberately narrow. The controller persists work-order admission and lifecycle state in SQLite, registers bounded semantic capabilities, enforces idempotency, records transition history and action receipts, survives process restart, and fails closed at the external-sovereign boundary.

The gateway adds a typed GPT-facing supervisory surface with exact caller and `mindId` binding. It has no shell, script, credential, filesystem, or network execution method.

The GitHub bridge adds a pure coordination membrane: it authenticates and reduces one queued `workflow_job` delivery to an authority-free proposal, and projects an authoritative Pleiades receipt into a bounded commit-status request descriptor. It does not host an endpoint, register a runner, call GitHub, read a token, or execute workflow content.

It does **not** execute commands, hold credentials, create Ghosts, mutate canonical resources, schedule live work, expose a network endpoint, or claim production readiness.

## Implemented controller behavior

- SQLite WAL state with full synchronous durability;
- immutable capability-version registration;
- rejection of arbitrary-shell and external-irreversible capabilities;
- exact request-body idempotency;
- registered-operation and risk-ceiling admission;
- canonical-write, checkpoint, approval, and isolation gates;
- explicit legal lifecycle transitions;
- idempotent transition operation tokens;
- durable cancellation and restart recovery;
- evidence-backed action receipts;
- reconciliation requirement for uncertain effects;
- append-only transition history;
- bounded capability and receipt read paths.

## Implemented gateway verbs

```text
inspect_ecology
create_work_order
get_work_order
cancel_work_order
collect_evidence
```

The remaining contracted verbs fail closed until their backends exist:

```text
approve_stage
apply_scoped_change
manage_service
restore_checkpoint
```

There is intentionally no `run_command`, `shell`, or equivalent pass-through.

## GitHub proposal ingress

`github_bridge.admit_workflow_job` takes three explicit inputs:

1. the unmodified raw request bytes;
2. the delivered headers;
3. the separately supplied webhook secret.

It verifies `X-Hub-Signature-256` with HMAC-SHA-256 and constant-time comparison before parsing JSON. Version 1 accepts only `workflow_job` deliveries whose action is `queued`. It binds:

- globally unique delivery identity and hook ID;
- exact payload SHA-256;
- stable repository ID and canonical owner/repository name;
- exact 40-hex commit SHA;
- job ID, run ID, run attempt, job name, workflow name, head branch, and bounded labels.

The result declares `authorityCeiling: none`, `arrivalOrderAuthoritative: false`, and `workflowContentExecutable: false`. Exact retry produces the same proposal. Changed content produces a different payload and proposal identity. No repository text, workflow YAML, label, branch, name, or webhook arrival order becomes executable authority.

The local body limit is one MiB, deliberately narrower than GitHub's service-wide webhook cap. A future endpoint may choose another explicit bound, but may not exceed GitHub's documented maximum or parse before signature verification.

## GitHub status projection

`github_bridge.project_commit_status` maps one authoritative Pleiades receipt to a credential-free request descriptor for GitHub's commit-status API:

- admitted, queued, pending, or running -> `pending`;
- success or succeeded -> `success`;
- declared deterministic validation, policy, contract, or test failure -> `failure`;
- infrastructure, startup, ambiguous, or unsupported failure -> `error`.

The descriptor binds an exact repository, exact commit SHA, stable `pleiades/<job-class>` context, bounded description, optional HTTPS evidence URL, and receipt digest. It does not send the request. GitHub status remains presentation-only and cannot replace the local receipt or authorize promotion.

## Test

```bash
cd modos/work-order-controller
python -m unittest -v \
  test_smoke.py \
  test_gateway.py \
  test_github_bridge.py
```

The GitHub bridge suite includes GitHub's published HMAC test vector, authenticated queued-job admission, tamper and malformed-input refusal, deterministic proposal identity, bounded status mapping, invalid target rejection, and a structural test proving the module contains no HTTP client, token environment, subprocess, shell, or raw-command surface.

The next implementation step is a deterministic `repository.test_and_report` worker that consumes admitted operation intents inside one Ghost workspace and returns typed evidence and receipts. That work remains owned by issues #28, #31, #32, and #33. A deployed webhook listener, replay store, GitHub reconciliation poller, credential-separated status publisher, rate controls, taint handling, approval persistence, service adapters, and recovery remain separately gated by issues #29 and #48.
