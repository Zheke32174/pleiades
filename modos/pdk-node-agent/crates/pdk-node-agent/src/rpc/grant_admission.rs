use tonic::{Request, Response, Status};
use tracing::{info, warn};

use pdk_protocol::v1::{CapabilityGrantAck, SignedCapabilityGrant};
use pdk_transport::peer_identity;

use super::{DecisionEvent, NodeAgentService};
use crate::{authority::GrantAdmission, policy::GrantInstallOutcome};

impl NodeAgentService {
    pub(super) async fn admit_capability_grant(
        &self,
        request: Request<SignedCapabilityGrant>,
    ) -> Result<Response<CapabilityGrantAck>, Status> {
        let peer = peer_identity(&request)?.clone();
        let envelope = request.into_inner();

        let validated = match self.policy.validate_signed_grant(envelope, &peer.identity) {
            Ok(validated) => validated,
            Err(error) => {
                let event = DecisionEvent {
                    decision: "deny",
                    operation: "push_capability_grant",
                    controller_id: &peer.identity,
                    token_id: "rejected",
                    workload_id: "unknown",
                    detail: "grant failed deterministic validation",
                };
                let _ = self
                    .audit_decision("rejected", "capability.grant.denied", &event)
                    .await;
                return Err(Status::permission_denied(error.to_string()));
            }
        };

        let grant = validated.payload().clone();
        let signature_base64 = validated.signature_base64().to_owned();
        let event = DecisionEvent {
            decision: "allow",
            operation: "push_capability_grant",
            controller_id: &peer.identity,
            token_id: &grant.token_id,
            workload_id: &grant.subject_workload_id,
            detail: "deterministically validated candidate prepared for atomic durable authority and signed admission receipt",
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

        let activation = self
            .policy
            .install_committed_grant(validated)
            .await
            .map_err(|error| {
                Status::failed_precondition(format!(
                    "durably admitted capability was not activated: {error}"
                ))
            })?;
        let activation_state = match activation {
            GrantInstallOutcome::Installed => "installed",
            GrantInstallOutcome::Idempotent => "idempotent",
            GrantInstallOutcome::Superseded { highest_sequence } => {
                warn!(
                    token_id = %grant.token_id,
                    grant_sequence = grant.grant_sequence,
                    highest_sequence,
                    "durably admitted capability candidate was superseded before cache activation"
                );
                return Err(Status::failed_precondition(format!(
                    "durably admitted capability sequence {} is superseded by active sequence {}",
                    grant.grant_sequence, highest_sequence
                )));
            }
        };

        info!(
            token_id = %grant.token_id,
            workload_id = %grant.subject_workload_id,
            controller = %peer.identity,
            admission_state,
            activation_state,
            "committed signed capability grant before active-cache installation"
        );
        Ok(Response::new(CapabilityGrantAck {
            token_id: grant.token_id,
            accepted: true,
            message: format!(
                "capability grant durably admitted ({admission_state}) and activated ({activation_state})"
            ),
        }))
    }
}
