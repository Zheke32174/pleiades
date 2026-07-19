use std::time::{SystemTime, UNIX_EPOCH};

use pdk_crypto::{
    sign_event_ack, sign_heartbeat_ack, signed_domain_event_digest_sha256,
    signed_heartbeat_digest_sha256, verify_domain_event, verify_heartbeat,
};
use pdk_protocol::{
    PROTOCOL_VERSION,
    v1::{
        EventAckPayload, HeartbeatAckPayload, SignedDomainEvent, SignedEventAck, SignedHeartbeat,
        SignedHeartbeatAck, control_plane_server::ControlPlane,
    },
};
use pdk_transport::peer_identity;
use tonic::{Request, Response, Status};
use tracing::{error, info};
use uuid::Uuid;

use crate::{
    heartbeat_store::HeartbeatAdmissionError, state::ControllerState,
    store::EventAdmissionError,
};

#[derive(Clone)]
pub struct ControlPlaneService {
    state: ControllerState,
}

impl ControlPlaneService {
    pub fn new(state: ControllerState) -> Self {
        Self { state }
    }

    async fn accept_heartbeat(
        &self,
        request: Request<SignedHeartbeat>,
    ) -> Result<Response<SignedHeartbeatAck>, Status> {
        let peer = peer_identity(&request)?.clone();
        let envelope = request.into_inner();
        let heartbeat = envelope
            .payload
            .as_ref()
            .ok_or_else(|| Status::invalid_argument("heartbeat payload missing"))?;

        if heartbeat.protocol_version != PROTOCOL_VERSION {
            return Err(Status::failed_precondition("unsupported protocol version"));
        }
        if heartbeat.domain_id != self.state.config.domain_id {
            return Err(Status::permission_denied(
                "heartbeat belongs to another domain",
            ));
        }
        if peer.identity != heartbeat.node_id {
            return Err(Status::permission_denied(
                "mTLS node identity does not match signed heartbeat node_id",
            ));
        }

        let trusted = self
            .state
            .trusted_node_keys
            .get(&heartbeat.node_id)
            .ok_or_else(|| Status::unauthenticated("node signing key is not enrolled"))?;
        if envelope.key_id != trusted.key_id {
            return Err(Status::unauthenticated("heartbeat key_id is not enrolled"));
        }
        verify_heartbeat(&envelope, &trusted.verifying_key)
            .map_err(|error| Status::unauthenticated(error.to_string()))?;

        match self.state.heartbeat_store.retry_ack(&envelope).await {
            Ok(Some(ack)) => {
                info!(
                    node_id = %heartbeat.node_id,
                    sequence = heartbeat.sequence,
                    disposition = "idempotent",
                    peer_fingerprint = %peer.certificate_sha256,
                    "recovered durable signed heartbeat acknowledgement"
                );
                return Ok(Response::new(ack));
            }
            Ok(None) => {}
            Err(HeartbeatAdmissionError::Collision) => {
                return Err(Status::already_exists(
                    "heartbeat sequence collides with different signed content",
                ));
            }
            Err(HeartbeatAdmissionError::Replay { .. }) => {
                return Err(Status::already_exists("heartbeat sequence replayed"));
            }
            Err(HeartbeatAdmissionError::Storage(storage_error)) => {
                error!(
                    node_id = %heartbeat.node_id,
                    sequence = heartbeat.sequence,
                    error = %storage_error,
                    "failed durable heartbeat retry lookup"
                );
                return Err(Status::unavailable(
                    "controller could not read durable heartbeat state",
                ));
            }
        }

        let now = unix_ms();
        let max_skew = self
            .state
            .config
            .max_clock_skew_seconds
            .saturating_mul(1_000);
        if now.abs_diff(heartbeat.sent_at_unix_ms) > max_skew {
            return Err(Status::unauthenticated(
                "heartbeat timestamp outside allowed skew",
            ));
        }

        let heartbeat_digest = signed_heartbeat_digest_sha256(&envelope);
        let candidate_ack = sign_heartbeat_ack(
            HeartbeatAckPayload {
                ack_id: Uuid::new_v4().to_string(),
                domain_id: self.state.config.domain_id.clone(),
                controller_id: self.state.config.controller_id.clone(),
                node_id: heartbeat.node_id.clone(),
                boot_id: heartbeat.boot_id.clone(),
                accepted_sequence: heartbeat.sequence,
                accepted_at_unix_ms: now,
                suggested_interval_seconds: self.state.config.suggested_heartbeat_interval_seconds,
                authority_mode: self.state.config.authority_mode.clone(),
                heartbeat_digest_sha256: heartbeat_digest.clone(),
            },
            &self.state.signing_key,
        );
        let admission = match self
            .state
            .heartbeat_store
            .admit_new(&envelope, &candidate_ack)
            .await
        {
            Ok(admission) => admission,
            Err(HeartbeatAdmissionError::Collision) => {
                return Err(Status::already_exists(
                    "heartbeat sequence collides with different signed content",
                ));
            }
            Err(HeartbeatAdmissionError::Replay { .. }) => {
                return Err(Status::already_exists("heartbeat sequence replayed"));
            }
            Err(HeartbeatAdmissionError::Storage(storage_error)) => {
                error!(
                    node_id = %heartbeat.node_id,
                    sequence = heartbeat.sequence,
                    error = %storage_error,
                    "failed durable heartbeat admission"
                );
                return Err(Status::unavailable(
                    "controller could not durably admit signed heartbeat",
                ));
            }
        };
        let disposition = admission.disposition();
        let ack = admission.into_ack();
        info!(
            node_id = %heartbeat.node_id,
            sequence = heartbeat.sequence,
            heartbeat_digest = %heartbeat_digest,
            disposition,
            peer_fingerprint = %peer.certificate_sha256,
            "durably accepted signed node heartbeat"
        );
        Ok(Response::new(ack))
    }
}

#[tonic::async_trait]
impl ControlPlane for ControlPlaneService {
    async fn register_node(
        &self,
        request: Request<SignedHeartbeat>,
    ) -> Result<Response<SignedHeartbeatAck>, Status> {
        self.accept_heartbeat(request).await
    }

    async fn heartbeat(
        &self,
        request: Request<SignedHeartbeat>,
    ) -> Result<Response<SignedHeartbeatAck>, Status> {
        self.accept_heartbeat(request).await
    }

    async fn submit_event(
        &self,
        request: Request<SignedDomainEvent>,
    ) -> Result<Response<SignedEventAck>, Status> {
        let peer = peer_identity(&request)?.clone();
        let envelope = request.into_inner();
        let event = envelope
            .payload
            .as_ref()
            .ok_or_else(|| Status::invalid_argument("event payload missing"))?;
        if event.protocol_version != PROTOCOL_VERSION {
            return Err(Status::failed_precondition(
                "unsupported event protocol version",
            ));
        }
        if event.domain_id != self.state.config.domain_id {
            return Err(Status::permission_denied("event belongs to another domain"));
        }
        if event.source_node_id != peer.identity {
            return Err(Status::permission_denied(
                "mTLS identity does not match event source node",
            ));
        }
        let trusted = self
            .state
            .trusted_node_keys
            .get(&event.source_node_id)
            .ok_or_else(|| Status::unauthenticated("event signer not enrolled"))?;
        if envelope.key_id != trusted.key_id {
            return Err(Status::unauthenticated("event key_id is not enrolled"));
        }
        verify_domain_event(&envelope, &trusted.verifying_key)
            .map_err(|error| Status::unauthenticated(error.to_string()))?;

        if event.event_id.is_empty() || event.event_type.is_empty() || event.trace_id.is_empty() {
            return Err(Status::invalid_argument(
                "event_id, event_type, and trace_id are required",
            ));
        }
        let now = unix_ms();
        let max_skew = self
            .state
            .config
            .max_clock_skew_seconds
            .saturating_mul(1_000);
        if event.created_at_unix_ms > now.saturating_add(max_skew) {
            return Err(Status::unauthenticated(
                "event timestamp is too far in the future",
            ));
        }

        let event_id = event.event_id.clone();
        let source_node_id = event.source_node_id.clone();
        let event_digest = signed_domain_event_digest_sha256(&envelope);
        let candidate_ack = sign_event_ack(
            EventAckPayload {
                ack_id: Uuid::new_v4().to_string(),
                domain_id: self.state.config.domain_id.clone(),
                controller_id: self.state.config.controller_id.clone(),
                event_id: event_id.clone(),
                accepted_at_unix_ms: now,
                source_node_id: source_node_id.clone(),
                event_digest_sha256: event_digest.clone(),
            },
            &self.state.signing_key,
        );
        let admission = match self
            .state
            .store
            .admit_event(&envelope, &candidate_ack)
            .await
        {
            Ok(admission) => admission,
            Err(EventAdmissionError::Collision) => {
                return Err(Status::already_exists(
                    "event_id collides with different signed event content",
                ));
            }
            Err(EventAdmissionError::Storage(storage_error)) => {
                error!(
                    event_id = %event_id,
                    source = %source_node_id,
                    error = %storage_error,
                    "failed durable signed event admission"
                );
                return Err(Status::unavailable(
                    "controller could not durably admit signed event",
                ));
            }
        };
        let disposition = admission.disposition();
        let ack = admission.into_ack();
        info!(
            event_id = %event_id,
            source = %source_node_id,
            event_digest = %event_digest,
            disposition,
            peer_fingerprint = %peer.certificate_sha256,
            "durably accepted signed domain event"
        );
        Ok(Response::new(ack))
    }
}

fn unix_ms() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis()
        .try_into()
        .unwrap_or(u64::MAX)
}
