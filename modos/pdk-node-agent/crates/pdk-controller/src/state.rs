use std::{collections::HashMap, sync::Arc};

use ed25519_dalek::VerifyingKey;
use pdk_protocol::v1::{DomainEventPayload, HeartbeatPayload};
use tokio::sync::RwLock;

use crate::config::ControllerConfig;
use pdk_crypto::LoadedSigningKey;

#[derive(Clone)]
pub struct TrustedNodeKey {
    pub key_id: String,
    pub verifying_key: VerifyingKey,
}

#[derive(Clone, Debug)]
pub struct NodeObservation {
    pub heartbeat: HeartbeatPayload,
    pub accepted_at_unix_ms: u64,
}

#[derive(Clone)]
pub struct ControllerState {
    pub config: Arc<ControllerConfig>,
    pub signing_key: Arc<LoadedSigningKey>,
    pub trusted_node_keys: Arc<HashMap<String, TrustedNodeKey>>,
    pub replay: Arc<RwLock<HashMap<(String, String), u64>>>,
    pub observations: Arc<RwLock<HashMap<String, NodeObservation>>>,
    pub accepted_events: Arc<RwLock<HashMap<String, DomainEventPayload>>>,
}
