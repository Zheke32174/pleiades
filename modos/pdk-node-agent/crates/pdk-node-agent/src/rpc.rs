use serde::Serialize;
use tonic::{Request, Response, Status};
use tracing::{info, warn};

use pdk_protocol::v1::{
    AgentStatus, CapabilityGrantAck, GetWorkloadStatusRequest, SignedCapabilityGrant,
    SpawnWorkloadRequest, StopWorkloadRequest, WorkloadReceipt, node_agent_server::NodeAgent,
};
use pdk_transport::peer_identity;

use crate::{
    audit::OfflineAuditBuffer, autonomy::AutonomyStateMachine, policy::PolicyEnforcer,
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

impl NodeAgentService {
    pub fn new(
        domain_id: impl Into<String>,
        node_id: impl Into<String>,
        autonomy: AutonomyStateMachine,
        policy: PolicyEnforcer,
        runtime: RuntimeManager,
        audit: OfflineAuditBuffer,
    ) -> Self {
        Self {
            domain_id: domain_id.into(),
            node_id: node_id.into(),
            autonomy,
            policy,
            runtime,
            audit,
        }
    }

    async fn audit_decision(
        &self,
        trace_id: &str,
        event_type: &str,
        event: &DecisionEvent<'_>,
    ) -> Result<(), Status> {
        self.audit
            .queue_event(event_type, trace_id, event)
            .await
            .map(|_| ())
            .map_err(|error| Status::internal(format!("audit persistence failed: {error}")))
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
        match self
            .policy
            .cache_signed_grant(envelope, &peer.identity)
            .await
        {
            Ok(grant) => {
                let event = DecisionEvent {
                    decision: "allow",
                    operation: "push_capability_grant",
                    controller_id: &peer.identity,
                    token_id: &grant.token_id,
                    workload_id: &grant.subject_workload_id,
                    detail: "signature, domain, target, validity interval, and Connected state verified",
                };
                if let Err(error) = self
                    .audit_decision(&grant.token_id, "capability.grant.cached", &event)
                    .await
                {
                    self.policy.remove_cached_grant(&grant.token_id).await;
                    return Err(error);
                }
                info!(
                    token_id = %grant.token_id,
                    workload_id = %grant.subject_workload_id,
                    controller = %peer.identity,
                    "cached signed capability grant"
                );
                Ok(Response::new(CapabilityGrantAck {
                    token_id: grant.token_id,
                    accepted: true,
                    message: "capability grant cached".into(),
                }))
            }
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
                    .audit_decision(token_id, "capability.grant.denied", &event)
                    .await;
                Err(Status::permission_denied(error.to_string()))
            }
        }
    }

    async fn spawn_workload(
        &self,
        request: Request<SpawnWorkloadRequest>,
    ) -> Result<Response<WorkloadReceipt>, Status> {
        let peer = peer_identity(&request)?.clone();
        let request = request.into_inner();
        let workload = request
            .workload
            .as_ref()
            .ok_or_else(|| Status::invalid_argument("workload specification missing"))?;
        let authorization = self
            .policy
            .authorize_spawn(&request.capability_token_id, &request.lease_id, workload)
            .await
            .map_err(|error| Status::permission_denied(error.to_string()))?;

        let intent = DecisionEvent {
            decision: "allow",
            operation: "spawn_workload",
            controller_id: &peer.identity,
            token_id: &authorization.token_id,
            workload_id: &authorization.workload_id,
            detail: "authorized before runtime driver invocation",
        };
        self.audit_decision(&request.trace_id, "workload.spawn.authorized", &intent)
            .await?;

        let receipt = self
            .runtime
            .start(workload, &authorization.token_id, &authorization.lease_id)
            .await
            .map_err(|error| Status::internal(format!("runtime start failed: {error}")))?;
        let result = DecisionEvent {
            decision: "executed",
            operation: "spawn_workload",
            controller_id: &peer.identity,
            token_id: &authorization.token_id,
            workload_id: &authorization.workload_id,
            detail: &receipt.detail,
        };
        if let Err(error) = self
            .audit_decision(&request.trace_id, "workload.spawn.result", &result)
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
        let authorization = self
            .policy
            .authorize_stop(&request.capability_token_id, &request.workload_id)
            .await
            .map_err(|error| Status::permission_denied(error.to_string()))?;
        let intent = DecisionEvent {
            decision: "allow",
            operation: "stop_workload",
            controller_id: &peer.identity,
            token_id: &authorization.token_id,
            workload_id: &authorization.workload_id,
            detail: &request.reason,
        };
        self.audit_decision(&request.trace_id, "workload.stop.authorized", &intent)
            .await?;
        let receipt = self
            .runtime
            .stop(&request.workload_id, &request.reason)
            .await
            .map_err(|error| Status::internal(format!("runtime stop failed: {error}")))?;
        let result = DecisionEvent {
            decision: "executed",
            operation: "stop_workload",
            controller_id: &peer.identity,
            token_id: &authorization.token_id,
            workload_id: &authorization.workload_id,
            detail: &receipt.detail,
        };
        self.audit_decision(&request.trace_id, "workload.stop.result", &result)
            .await?;
        Ok(Response::new(receipt))
    }

    async fn get_workload_status(
        &self,
        request: Request<GetWorkloadStatusRequest>,
    ) -> Result<Response<WorkloadReceipt>, Status> {
        let _peer = peer_identity(&request)?;
        let request = request.into_inner();
        self.policy
            .authorize_status(&request.capability_token_id, &request.workload_id)
            .await
            .map_err(|error| Status::permission_denied(error.to_string()))?;
        let receipt = self
            .runtime
            .status(&request.workload_id)
            .await
            .map_err(|error| Status::not_found(error.to_string()))?;
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
