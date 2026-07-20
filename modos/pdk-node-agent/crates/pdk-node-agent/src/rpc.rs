use std::collections::BTreeMap;

use serde::Serialize;
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use tonic::{Request, Response, Status};
use tracing::{info, warn};

use pdk_protocol::v1::{
    AgentStatus, CapabilityGrantAck, GetWorkloadStatusRequest, IsolationConstraints,
    OperationIntentReceipt, SignedCapabilityGrant, SpawnWorkloadRequest, StopWorkloadRequest,
    WorkloadReceipt, WorkloadSpec, WorkloadState, node_agent_server::NodeAgent,
};
use pdk_transport::peer_identity;

use crate::{
    audit::OfflineAuditBuffer,
    authority::{AuthorityStateStore, GrantAdmission, OperationIntentCommit},
    autonomy::{AutonomyStateMachine, unix_ms},
    policy::PolicyEnforcer,
    runtime::RuntimeManager,
};

#[derive(Clone)]
pub struct NodeAgentService {
    domain_id: String,
    node_id: String,
    autonomy: AutonomyStateMachine,
    policy: PolicyEnforcer,
    runtime: RuntimeManager,
    audit: OfflineAuditBuffer,
    authority_state: AuthorityStateStore,
}

#[derive(Serialize)]
struct DecisionEvent<'a> {
    decision: &'a str,
    operation: &'a str,
    controller_id: &'a str,
    token_id: &'a str,
    workload_id: &'a str,
    detail: &'a str,
}

#[derive(Serialize)]
struct OperationIntentEvent<'a> {
    decision: &'a str,
    operation: &'a str,
    controller_id: &'a str,
    token_id: &'a str,
    workload_id: &'a str,
    request_digest_sha256: &'a str,
    detail: &'a str,
}

#[derive(Serialize)]
struct OperationOutcomeEvent<'a> {
    decision: &'a str,
    operation: &'a str,
    controller_id: &'a str,
    token_id: &'a str,
    workload_id: &'a str,
    intent_event_id: &'a str,
    request_digest_sha256: &'a str,
    detail: &'a str,
}

impl NodeAgentService {
    pub fn new(
        domain_id: impl Into<String>,
        node_id: impl Into<String>,
        autonomy: AutonomyStateMachine,
        policy: PolicyEnforcer,
        runtime: RuntimeManager,
        audit: OfflineAuditBuffer,
        authority_state: AuthorityStateStore,
    ) -> Self {
        Self {
            domain_id: domain_id.into(),
            node_id: node_id.into(),
            autonomy,
            policy,
            runtime,
            audit,
            authority_state,
        }
    }

    async fn audit_event<T: Serialize>(
        &self,
        trace_id: &str,
        event_type: &str,
        event: &T,
    ) -> Result<(), Status> {
        self.audit
            .queue_event(event_type, trace_id, event)
            .await
            .map(|_| ())
            .map_err(|error| Status::internal(format!("audit persistence failed: {error}")))
    }

    #[allow(clippy::too_many_arguments)]
    async fn commit_operation_intent(
        &self,
        controller_id: &str,
        trace_id: &str,
        request_digest_sha256: &str,
        token_id: &str,
        operation: &str,
        workload_id: &str,
        event_type: &str,
        detail: &str,
    ) -> Result<OperationIntentCommit, Status> {
        validate_trace_id(trace_id)?;
        let intent = OperationIntentEvent {
            decision: "allow",
            operation,
            controller_id,
            token_id,
            workload_id,
            request_digest_sha256,
            detail,
        };
        let prepared = self
            .audit
            .prepare_event(event_type, trace_id, &intent)
            .map_err(|error| {
                Status::internal(format!(
                    "preparing signed operation intent receipt failed: {error}"
                ))
            })?;
        self.authority_state
            .consume_use_with_intent(
                controller_id,
                trace_id,
                request_digest_sha256,
                token_id,
                operation,
                workload_id,
                unix_ms(),
                &prepared,
            )
            .await
            .map_err(|error| {
                Status::permission_denied(format!(
                    "durable capability use and intent denied: {error}"
                ))
            })
    }

    async fn record_runtime_failure(
        &self,
        trace_id: &str,
        event_type: &str,
        event: &OperationOutcomeEvent<'_>,
        runtime_error: &str,
    ) -> Status {
        match self.audit_event(trace_id, event_type, event).await {
            Ok(()) => Status::internal(runtime_error.to_owned()),
            Err(audit_error) => Status::internal(format!(
                "{runtime_error}; linked failure outcome persistence also failed: {audit_error}"
            )),
        }
    }
}

#[tonic::async_trait]
impl NodeAgent for NodeAgentService {
    async fn push_capability_grant(
        &self,
        request: Request<SignedCapabilityGrant>,
    ) -> Result<Response<CapabilityGrantAck>, Status> {
        let peer = peer_identity(&request)?.clone();
        let envelope = request.into_inner();
        let candidate = match self.policy.validate_signed_grant(envelope, &peer.identity) {
            Ok(candidate) => candidate,
            Err(error) => {
                let token_id = "rejected";
                let event = DecisionEvent {
                    decision: "deny",
                    operation: "push_capability_grant",
                    controller_id: &peer.identity,
                    token_id,
                    workload_id: "unknown",
                    detail: "grant failed deterministic validation",
                };
                let _ = self
                    .audit_event(token_id, "capability.grant.denied", &event)
                    .await;
                return Err(Status::permission_denied(error.to_string()));
            }
        };
        let grant = candidate.payload().clone();
        let signature_base64 = candidate.signature_base64().to_owned();
        let event = DecisionEvent {
            decision: "allow",
            operation: "push_capability_grant",
            controller_id: &peer.identity,
            token_id: &grant.token_id,
            workload_id: &grant.subject_workload_id,
            detail: "deterministically validated, transactionally admitted with signed receipt, then installed into the active policy cache",
        };
        let prepared = self
            .audit
            .prepare_event("capability.grant.admitted", &grant.token_id, &event)
            .map_err(|error| {
                Status::internal(format!(
                    "preparing signed capability admission receipt failed: {error}"
                ))
            })?;
        let admission = self
            .authority_state
            .admit_grant(&grant, &signature_base64, &prepared)
            .await
            .map_err(|error| {
                Status::failed_precondition(format!(
                    "transactional capability admission failed: {error}"
                ))
            })?;
        let admission_state = match admission {
            GrantAdmission::New { .. } => "new",
            GrantAdmission::Recovered { .. } => "recovered",
            GrantAdmission::Idempotent { .. } => "idempotent",
        };
        self.policy
            .install_durably_admitted_grant(candidate)
            .await
            .map_err(|error| {
                Status::failed_precondition(format!(
                    "durably admitted capability could not be installed into active policy: {error}"
                ))
            })?;
        info!(
            token_id = %grant.token_id,
            workload_id = %grant.subject_workload_id,
            controller = %peer.identity,
            admission_state,
            "committed signed capability grant before active policy installation"
        );
        Ok(Response::new(CapabilityGrantAck {
            token_id: grant.token_id,
            accepted: true,
            message: format!(
                "capability grant transactionally admitted and activated ({admission_state})"
            ),
        }))
    }

    async fn spawn_workload(
        &self,
        request: Request<SpawnWorkloadRequest>,
    ) -> Result<Response<WorkloadReceipt>, Status> {
        let peer = peer_identity(&request)?.clone();
        let request = request.into_inner();
        let request_digest = spawn_request_digest(&peer.identity, &request)?;
        let workload = request
            .workload
            .as_ref()
            .ok_or_else(|| Status::invalid_argument("workload specification missing"))?;
        let authorization = self
            .policy
            .authorize_spawn(&request.capability_token_id, &request.lease_id, workload)
            .await
            .map_err(|error| Status::permission_denied(error.to_string()))?;
        let commit = self
            .commit_operation_intent(
                &peer.identity,
                &request.trace_id,
                &request_digest,
                &authorization.token_id,
                "spawn_workload",
                &authorization.workload_id,
                "workload.spawn.intent",
                "authorized capability use and runtime start intent committed atomically",
            )
            .await?;
        let intent = operation_intent_receipt(&request.trace_id, &request_digest, &commit);
        if commit.replayed() {
            return Ok(Response::new(intent_only_receipt(
                "spawn_workload",
                &authorization.workload_id,
                intent,
            )));
        }

        let mut receipt = match self
            .runtime
            .start(workload, &authorization.token_id, &authorization.lease_id)
            .await
        {
            Ok(receipt) => receipt,
            Err(error) => {
                let detail = format!("runtime start failed: {error}");
                let outcome = OperationOutcomeEvent {
                    decision: "failed",
                    operation: "spawn_workload",
                    controller_id: &peer.identity,
                    token_id: &authorization.token_id,
                    workload_id: &authorization.workload_id,
                    intent_event_id: commit.event_id(),
                    request_digest_sha256: &request_digest,
                    detail: &detail,
                };
                return Err(self
                    .record_runtime_failure(
                        &request.trace_id,
                        "workload.spawn.result",
                        &outcome,
                        &detail,
                    )
                    .await);
            }
        };
        receipt.intent = Some(intent);
        let outcome = OperationOutcomeEvent {
            decision: "executed",
            operation: "spawn_workload",
            controller_id: &peer.identity,
            token_id: &authorization.token_id,
            workload_id: &authorization.workload_id,
            intent_event_id: commit.event_id(),
            request_digest_sha256: &request_digest,
            detail: &receipt.detail,
        };
        if let Err(error) = self
            .audit_event(&request.trace_id, "workload.spawn.result", &outcome)
            .await
        {
            warn!(workload_id = %authorization.workload_id, "audit failed after start; terminating workload fail-closed");
            let _ = self
                .runtime
                .stop(
                    &authorization.workload_id,
                    "post-start audit persistence failure",
                )
                .await;
            return Err(error);
        }
        Ok(Response::new(receipt))
    }

    async fn stop_workload(
        &self,
        request: Request<StopWorkloadRequest>,
    ) -> Result<Response<WorkloadReceipt>, Status> {
        let peer = peer_identity(&request)?.clone();
        let request = request.into_inner();
        let request_digest = stop_request_digest(&peer.identity, &request)?;
        let authorization = self
            .policy
            .authorize_stop(&request.capability_token_id, &request.workload_id)
            .await
            .map_err(|error| Status::permission_denied(error.to_string()))?;
        let commit = self
            .commit_operation_intent(
                &peer.identity,
                &request.trace_id,
                &request_digest,
                &authorization.token_id,
                "stop_workload",
                &authorization.workload_id,
                "workload.stop.intent",
                &request.reason,
            )
            .await?;
        let intent = operation_intent_receipt(&request.trace_id, &request_digest, &commit);
        if commit.replayed() {
            return Ok(Response::new(intent_only_receipt(
                "stop_workload",
                &authorization.workload_id,
                intent,
            )));
        }

        let mut receipt = match self
            .runtime
            .stop(&request.workload_id, &request.reason)
            .await
        {
            Ok(receipt) => receipt,
            Err(error) => {
                let detail = format!("runtime stop failed: {error}");
                let outcome = OperationOutcomeEvent {
                    decision: "failed",
                    operation: "stop_workload",
                    controller_id: &peer.identity,
                    token_id: &authorization.token_id,
                    workload_id: &authorization.workload_id,
                    intent_event_id: commit.event_id(),
                    request_digest_sha256: &request_digest,
                    detail: &detail,
                };
                return Err(self
                    .record_runtime_failure(
                        &request.trace_id,
                        "workload.stop.result",
                        &outcome,
                        &detail,
                    )
                    .await);
            }
        };
        receipt.intent = Some(intent);
        let outcome = OperationOutcomeEvent {
            decision: "executed",
            operation: "stop_workload",
            controller_id: &peer.identity,
            token_id: &authorization.token_id,
            workload_id: &authorization.workload_id,
            intent_event_id: commit.event_id(),
            request_digest_sha256: &request_digest,
            detail: &receipt.detail,
        };
        self.audit_event(&request.trace_id, "workload.stop.result", &outcome)
            .await?;
        Ok(Response::new(receipt))
    }

    async fn get_workload_status(
        &self,
        request: Request<GetWorkloadStatusRequest>,
    ) -> Result<Response<WorkloadReceipt>, Status> {
        let peer = peer_identity(&request)?.clone();
        let request = request.into_inner();
        let request_digest = status_request_digest(&peer.identity, &request)?;
        let authorization = self
            .policy
            .authorize_status(&request.capability_token_id, &request.workload_id)
            .await
            .map_err(|error| Status::permission_denied(error.to_string()))?;
        let commit = self
            .commit_operation_intent(
                &peer.identity,
                &request.trace_id,
                &request_digest,
                &authorization.token_id,
                "status_workload",
                &authorization.workload_id,
                "workload.status.intent",
                "authorized capability use and runtime status read intent committed atomically",
            )
            .await?;
        let intent = operation_intent_receipt(&request.trace_id, &request_digest, &commit);
        if commit.replayed() {
            return Ok(Response::new(intent_only_receipt(
                "status_workload",
                &authorization.workload_id,
                intent,
            )));
        }

        let mut receipt = match self.runtime.status(&request.workload_id).await {
            Ok(receipt) => receipt,
            Err(error) => {
                let detail = format!("runtime status failed: {error}");
                let outcome = OperationOutcomeEvent {
                    decision: "failed",
                    operation: "status_workload",
                    controller_id: &peer.identity,
                    token_id: &authorization.token_id,
                    workload_id: &authorization.workload_id,
                    intent_event_id: commit.event_id(),
                    request_digest_sha256: &request_digest,
                    detail: &detail,
                };
                let status = self
                    .record_runtime_failure(
                        &request.trace_id,
                        "workload.status.result",
                        &outcome,
                        &detail,
                    )
                    .await;
                return Err(Status::not_found(status.message().to_owned()));
            }
        };
        receipt.intent = Some(intent);
        let outcome = OperationOutcomeEvent {
            decision: "observed",
            operation: "status_workload",
            controller_id: &peer.identity,
            token_id: &authorization.token_id,
            workload_id: &authorization.workload_id,
            intent_event_id: commit.event_id(),
            request_digest_sha256: &request_digest,
            detail: &receipt.detail,
        };
        self.audit_event(&request.trace_id, "workload.status.result", &outcome)
            .await?;
        Ok(Response::new(receipt))
    }

    async fn get_agent_status(
        &self,
        request: Request<()>,
    ) -> Result<Response<AgentStatus>, Status> {
        let _peer = peer_identity(&request)?;
        let pending = self
            .audit
            .pending_count()
            .await
            .map_err(|error| Status::internal(error.to_string()))?;
        Ok(Response::new(AgentStatus {
            domain_id: self.domain_id.clone(),
            node_id: self.node_id.clone(),
            node_state: self.autonomy.current() as i32,
            last_controller_ack_unix_ms: self.autonomy.last_ack_unix_ms(),
            cached_capability_count: self.policy.cached_count().await,
            pending_audit_event_count: pending,
        }))
    }
}

fn validate_trace_id(trace_id: &str) -> Result<(), Status> {
    if trace_id.is_empty() || trace_id.len() > 128 || trace_id.chars().any(char::is_control) {
        return Err(Status::invalid_argument(
            "trace_id must contain 1..=128 non-control characters",
        ));
    }
    Ok(())
}

fn operation_intent_receipt(
    trace_id: &str,
    request_digest_sha256: &str,
    commit: &OperationIntentCommit,
) -> OperationIntentReceipt {
    OperationIntentReceipt {
        event_id: commit.event_id().to_owned(),
        trace_id: trace_id.to_owned(),
        request_digest_sha256: request_digest_sha256.to_owned(),
        committed_use: commit.consumed_use(),
        replayed: commit.replayed(),
    }
}

fn intent_only_receipt(
    operation: &str,
    workload_id: &str,
    intent: OperationIntentReceipt,
) -> WorkloadReceipt {
    WorkloadReceipt {
        workload_id: workload_id.to_owned(),
        runtime: "pdk-operation-intent".into(),
        runtime_object_id: String::new(),
        state: WorkloadState::Prepared as i32,
        observed_at_unix_ms: unix_ms(),
        detail: format!(
            "exact {operation} retry returned the original durable intent; runtime was not reinvoked"
        ),
        intent: Some(intent),
    }
}

fn spawn_request_digest(
    controller_id: &str,
    request: &SpawnWorkloadRequest,
) -> Result<String, Status> {
    let workload = request
        .workload
        .as_ref()
        .ok_or_else(|| Status::invalid_argument("workload specification missing"))?;
    digest_value(&json!({
        "schema": "pleiades.pdk.operation-request/v1",
        "operation": "spawn_workload",
        "controller_id": controller_id,
        "capability_token_id": request.capability_token_id,
        "lease_id": request.lease_id,
        "workload": canonical_workload(workload),
    }))
}

fn stop_request_digest(
    controller_id: &str,
    request: &StopWorkloadRequest,
) -> Result<String, Status> {
    digest_value(&json!({
        "schema": "pleiades.pdk.operation-request/v1",
        "operation": "stop_workload",
        "controller_id": controller_id,
        "capability_token_id": request.capability_token_id,
        "workload_id": request.workload_id,
        "reason": request.reason,
    }))
}

fn status_request_digest(
    controller_id: &str,
    request: &GetWorkloadStatusRequest,
) -> Result<String, Status> {
    digest_value(&json!({
        "schema": "pleiades.pdk.operation-request/v1",
        "operation": "status_workload",
        "controller_id": controller_id,
        "capability_token_id": request.capability_token_id,
        "workload_id": request.workload_id,
    }))
}

fn canonical_workload(workload: &WorkloadSpec) -> Value {
    let environment = workload
        .environment
        .iter()
        .map(|(key, value)| (key.as_str(), value.as_str()))
        .collect::<BTreeMap<_, _>>();
    json!({
        "workload_id": workload.workload_id,
        "executable": workload.executable,
        "args": workload.args,
        "environment": environment,
        "working_directory": workload.working_directory,
        "isolation": canonical_isolation(workload.isolation.as_ref()),
        "singleton_destructive": workload.singleton_destructive,
    })
}

fn canonical_isolation(isolation: Option<&IsolationConstraints>) -> Value {
    match isolation {
        Some(value) => json!({
            "network_denied": value.network_denied,
            "read_only_root": value.read_only_root,
            "private_tmp": value.private_tmp,
            "protect_home": value.protect_home,
            "no_new_privileges": value.no_new_privileges,
            "dynamic_user": value.dynamic_user,
            "restrict_suid_sgid": value.restrict_suid_sgid,
            "restrict_address_families": value.restrict_address_families,
            "memory_max_bytes": value.memory_max_bytes,
            "cpu_quota_percent": value.cpu_quota_percent,
            "cgroup_slice": value.cgroup_slice,
        }),
        None => Value::Null,
    }
}

fn digest_value<T: Serialize>(value: &T) -> Result<String, Status> {
    let encoded = serde_json::to_vec(value).map_err(|error| {
        Status::internal(format!("canonical request serialization failed: {error}"))
    })?;
    Ok(format!("sha256:{:x}", Sha256::digest(encoded)))
}
