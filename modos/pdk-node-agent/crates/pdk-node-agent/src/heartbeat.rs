use std::{
    fs,
    sync::{
        Arc,
        atomic::{AtomicU64, Ordering},
    },
    time::Duration,
};

use pdk_crypto::{LoadedSigningKey, sign_heartbeat};
use pdk_protocol::{
    PROTOCOL_VERSION,
    v1::{HealthStatus, HeartbeatPayload, NodeState},
};
use tracing::{info, warn};
use uuid::Uuid;

use crate::{
    autonomy::{AutonomyStateMachine, unix_ms},
    control_link::ControlPlaneLink,
    inventory::InventoryManager,
};

#[derive(Clone)]
pub struct HeartbeatLoop {
    domain_id: String,
    node_id: String,
    boot_id: String,
    agent_version: String,
    interval: Duration,
    sequence: Arc<AtomicU64>,
    signing_key: Arc<LoadedSigningKey>,
    inventory: InventoryManager,
    autonomy: AutonomyStateMachine,
    control: ControlPlaneLink,
}

impl HeartbeatLoop {
    pub fn new(
        domain_id: impl Into<String>,
        node_id: impl Into<String>,
        interval: Duration,
        signing_key: Arc<LoadedSigningKey>,
        inventory: InventoryManager,
        autonomy: AutonomyStateMachine,
        control: ControlPlaneLink,
    ) -> Self {
        Self {
            domain_id: domain_id.into(),
            node_id: node_id.into(),
            boot_id: read_boot_id(),
            agent_version: env!("CARGO_PKG_VERSION").to_owned(),
            interval,
            sequence: Arc::new(AtomicU64::new(0)),
            signing_key,
            inventory,
            autonomy,
            control,
        }
    }

    pub async fn run(self) {
        let mut ticker = tokio::time::interval(self.interval);
        ticker.set_missed_tick_behavior(tokio::time::MissedTickBehavior::Skip);
        let mut registered = false;
        loop {
            ticker.tick().await;
            let sequence = self.sequence.fetch_add(1, Ordering::AcqRel) + 1;
            let inventory = self.inventory.collect().await;
            let state = self.autonomy.current();
            let envelope = sign_heartbeat(
                HeartbeatPayload {
                    protocol_version: PROTOCOL_VERSION,
                    domain_id: self.domain_id.clone(),
                    node_id: self.node_id.clone(),
                    boot_id: self.boot_id.clone(),
                    sequence,
                    sent_at_unix_ms: unix_ms(),
                    agent_version: self.agent_version.clone(),
                    node_state: state as i32,
                    health: health_for_state(state) as i32,
                    inventory: Some(inventory),
                },
                &self.signing_key,
            );

            let result = if registered {
                self.control
                    .heartbeat(envelope, &self.boot_id, sequence)
                    .await
            } else {
                self.control
                    .register(envelope, &self.boot_id, sequence)
                    .await
            };
            match result {
                Ok(ack) => {
                    let Some(payload) = ack.payload else {
                        registered = false;
                        warn!(
                            sequence,
                            "verified heartbeat ACK lost its payload before state update"
                        );
                        continue;
                    };
                    self.autonomy.record_controller_ack(unix_ms());
                    if !registered {
                        registered = true;
                        info!(
                            controller_id = %payload.controller_id,
                            authority_mode = %payload.authority_mode,
                            "node registration accepted"
                        );
                    }
                }
                Err(error) => {
                    registered = false;
                    warn!(sequence, error = %error, "signed heartbeat was not acknowledged");
                }
            }
        }
    }
}

fn health_for_state(state: NodeState) -> HealthStatus {
    match state {
        NodeState::Connected => HealthStatus::Healthy,
        NodeState::DegradedAutonomous | NodeState::ReadOnlySafe | NodeState::Standalone => {
            HealthStatus::Degraded
        }
        NodeState::Quarantined | NodeState::Unspecified => HealthStatus::Unhealthy,
    }
}

fn read_boot_id() -> String {
    fs::read_to_string("/proc/sys/kernel/random/boot_id")
        .ok()
        .map(|value| value.trim().to_owned())
        .filter(|value| !value.is_empty())
        .unwrap_or_else(|| Uuid::new_v4().to_string())
}
