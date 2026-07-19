use std::{collections::HashMap, sync::Arc};

use ed25519_dalek::VerifyingKey;

use crate::{
    config::ControllerConfig, heartbeat_store::ControllerHeartbeatStore,
    store::ControllerStateStore,
};
use pdk_crypto::LoadedSigningKey;

#[derive(Clone)]
pub struct TrustedNodeKey {
    pub key_id: String,
    pub verifying_key: VerifyingKey,
}

#[derive(Clone)]
pub struct ControllerState {
    pub config: Arc<ControllerConfig>,
    pub signing_key: Arc<LoadedSigningKey>,
    pub trusted_node_keys: Arc<HashMap<String, TrustedNodeKey>>,
    pub store: ControllerStateStore,
    pub heartbeat_store: ControllerHeartbeatStore,
}
