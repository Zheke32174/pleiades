# Factory Operator Architecture

## Overview
The Factory Operator is a self-orchestrating loop that drives the Pleiades hivemind by executing tasks from the Task Master. It acts as a high-level orchestrator that interfaces between external tasking systems and the internal `pleiades-request-broker`.

## Components

### 1. Operator Loop (Factory Loop)
A persistent systemd service (`pleiades-factory-operator.service`) that runs inside the Gentoo container.
Cycle:
1. **Poll**: Retrieve pending tasks from `taskmaster` (using the MCP extension or local state).
2. **Analyze**: Classify the task based on the **HITL Approval Taxonomy**.
3. **Propose**: Write a proposal to `/run/pleiades/alien/outbox/` for human review if required.
4. **Gate**: Wait for a signed approval signal in `/run/pleiades/alien/inbox/`.
5. **Dispatch**: Convert the task into a Pleiades request and write to `/run/pleiades/requests/`.
6. **Log**: Capture the result from `/run/pleiades/results/` and log a receipt to `PLEIADES_STATE.md`.

### 2. HITL Approval Taxonomy
Tasks are classified by their risk level, which determines the required approval flow.

| Level | Classification | Action Types | Flow |
|---|---|---|---|
| **L0** | `SAFE` | Status queries, read-only introspection | **Auto-proceed** |
| **L1** | `BUFFERED` | Local file writes in non-critical paths | **HITL (One-click)** |
| **L2** | `RISKY` | Process management, service restarts | **HITL (Detailed review)** |
| **L3** | `CRITICAL` | Security policy changes, crypto operations | **HITL (MFA/Signed signal)** |
| **L4** | `OUTWARD` | Git push, external network interactions | **HITL (Strict isolation)** |

### 3. Integration Points

#### Task Master (External)
- Source of work items.
- Provides structured task definitions.

#### Request Broker (Internal)
- The gatekeeper for privileged actions inside the container.
- The Operator must adhere to the broker's policy (`/etc/pleiades/pleiades-swarm-policy.json`).

#### PLEIADES_STATE.md (Audit)
- Durable log of all operator activities.
- Includes evidence hashes and approval timestamps.

## Implementation Details
- **Binary**: `/usr/local/sbin/factory_operator_daemon`
- **Service**: `pleiades-factory-operator.service`
- **Configuration**: `/etc/pleiades/operator.conf`
- **State**: `/run/pleiades/operator_state`
