use std::time::Duration;

use tracing::{info, warn};

use crate::{
    audit::OfflineAuditBuffer, autonomy::AutonomyStateMachine, control_link::ControlPlaneLink,
};
use pdk_protocol::v1::NodeState;

#[derive(Clone)]
pub struct ReconciliationWorker {
    autonomy: AutonomyStateMachine,
    audit: OfflineAuditBuffer,
    control: ControlPlaneLink,
}

impl ReconciliationWorker {
    pub fn new(
        autonomy: AutonomyStateMachine,
        audit: OfflineAuditBuffer,
        control: ControlPlaneLink,
    ) -> Self {
        Self {
            autonomy,
            audit,
            control,
        }
    }

    pub async fn run(self) {
        let mut state_rx = self.autonomy.subscribe();
        loop {
            while *state_rx.borrow() != NodeState::Connected {
                if state_rx.changed().await.is_err() {
                    return;
                }
            }

            match self.audit.next().await {
                Ok(Some(event)) => {
                    let event_id = event
                        .payload
                        .as_ref()
                        .map(|payload| payload.event_id.clone())
                        .unwrap_or_default();
                    match self.control.submit_event(event).await {
                        Ok(ack) => {
                            let acked = ack
                                .payload
                                .as_ref()
                                .map(|payload| payload.event_id.as_str())
                                .unwrap_or_default();
                            match self.audit.acknowledge(acked).await {
                                Ok(true) => {
                                    info!(event_id = %acked, "cleared event after signed ACK")
                                }
                                Ok(false) => {
                                    warn!(event_id = %acked, "signed ACK referenced an event not in the local queue")
                                }
                                Err(error) => {
                                    warn!(event_id = %acked, error = %error, "could not clear acknowledged event")
                                }
                            }
                        }
                        Err(error) => {
                            if !event_id.is_empty() {
                                let _ = self
                                    .audit
                                    .mark_attempt_failed(&event_id, &error.to_string())
                                    .await;
                            }
                            warn!(event_id = %event_id, error = %error, "audit reconciliation paused");
                            tokio::time::sleep(Duration::from_secs(2)).await;
                        }
                    }
                }
                Ok(None) => tokio::time::sleep(Duration::from_millis(500)).await,
                Err(error) => {
                    warn!(error = %error, "could not read offline audit queue");
                    tokio::time::sleep(Duration::from_secs(2)).await;
                }
            }
        }
    }
}
