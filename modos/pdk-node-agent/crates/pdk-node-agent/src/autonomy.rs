use std::{
    sync::{
        Arc,
        atomic::{AtomicU64, Ordering},
    },
    time::{Duration, SystemTime, UNIX_EPOCH},
};

use pdk_protocol::v1::NodeState;
use tokio::sync::watch;
use tracing::{info, warn};

#[derive(Clone)]
pub struct AutonomyStateMachine {
    state_tx: watch::Sender<NodeState>,
    last_ack_unix_ms: Arc<AtomicU64>,
    heartbeat_timeout: Duration,
    read_only_timeout: Duration,
}

impl AutonomyStateMachine {
    pub fn new(heartbeat_timeout: Duration, read_only_timeout: Duration) -> Self {
        let (state_tx, _) = watch::channel(NodeState::DegradedAutonomous);
        Self {
            state_tx,
            last_ack_unix_ms: Arc::new(AtomicU64::new(0)),
            heartbeat_timeout,
            read_only_timeout,
        }
    }

    pub fn subscribe(&self) -> watch::Receiver<NodeState> {
        self.state_tx.subscribe()
    }

    pub fn current(&self) -> NodeState {
        *self.state_tx.borrow()
    }

    pub fn last_ack_unix_ms(&self) -> u64 {
        self.last_ack_unix_ms.load(Ordering::Acquire)
    }

    pub fn record_controller_ack(&self, observed_locally_at_unix_ms: u64) {
        self.last_ack_unix_ms
            .store(observed_locally_at_unix_ms, Ordering::Release);
        match self.current() {
            NodeState::Standalone | NodeState::Quarantined => {}
            _ => self.transition(NodeState::Connected, "authenticated controller ACK"),
        }
    }

    pub fn quarantine(&self, reason: &str) {
        self.transition(NodeState::Quarantined, reason);
    }

    pub fn enter_standalone(&self, reason: &str) {
        self.transition(NodeState::Standalone, reason);
    }

    pub fn enter_read_only_safe(&self, reason: &str) {
        if !matches!(
            self.current(),
            NodeState::Quarantined | NodeState::Standalone
        ) {
            self.transition(NodeState::ReadOnlySafe, reason);
        }
    }

    pub fn allows_new_global_grant(&self) -> bool {
        self.current() == NodeState::Connected
    }

    pub fn allows_status_read(&self) -> bool {
        !matches!(self.current(), NodeState::Quarantined)
    }

    pub fn allows_workload_stop(&self) -> bool {
        matches!(
            self.current(),
            NodeState::Connected | NodeState::DegradedAutonomous | NodeState::ReadOnlySafe
        )
    }

    pub fn allows_cached_workload_operation(&self, singleton_destructive: bool) -> bool {
        match self.current() {
            NodeState::Connected => true,
            NodeState::DegradedAutonomous => !singleton_destructive,
            NodeState::ReadOnlySafe | NodeState::Standalone | NodeState::Quarantined => false,
            NodeState::Unspecified => false,
        }
    }

    pub async fn monitor(self) {
        let mut interval = tokio::time::interval(Duration::from_secs(1));
        interval.set_missed_tick_behavior(tokio::time::MissedTickBehavior::Skip);
        loop {
            interval.tick().await;
            if matches!(
                self.current(),
                NodeState::Standalone | NodeState::Quarantined
            ) {
                continue;
            }
            let last_ack = self.last_ack_unix_ms();
            if last_ack == 0 {
                self.transition(
                    NodeState::DegradedAutonomous,
                    "controller has not yet authenticated the node",
                );
                continue;
            }
            let elapsed_ms = unix_ms().saturating_sub(last_ack);
            if elapsed_ms >= duration_ms(self.read_only_timeout) {
                self.enter_read_only_safe("controller ACK timeout exceeded read-only threshold");
            } else if elapsed_ms >= duration_ms(self.heartbeat_timeout) {
                self.transition(
                    NodeState::DegradedAutonomous,
                    "controller ACK timeout exceeded autonomy threshold",
                );
            }
        }
    }

    fn transition(&self, next: NodeState, reason: &str) {
        let current = self.current();
        if current == next {
            return;
        }
        if self.state_tx.send(next).is_ok() {
            if matches!(next, NodeState::Quarantined | NodeState::ReadOnlySafe) {
                warn!(from = ?current, to = ?next, reason, "node autonomy state changed");
            } else {
                info!(from = ?current, to = ?next, reason, "node autonomy state changed");
            }
        }
    }
}

fn duration_ms(duration: Duration) -> u64 {
    duration.as_millis().try_into().unwrap_or(u64::MAX)
}

pub fn unix_ms() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis()
        .try_into()
        .unwrap_or(u64::MAX)
}
