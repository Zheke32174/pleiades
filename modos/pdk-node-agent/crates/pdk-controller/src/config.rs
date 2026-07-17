use std::{fs, path::Path};

use anyhow::{Context, Result};
use pdk_transport::{PeerBindingConfig, TlsFileConfig};
use serde::Deserialize;

#[derive(Clone, Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ControllerConfig {
    pub domain_id: String,
    pub controller_id: String,
    pub authority_mode: String,
    pub bind: String,
    pub signing_key_file: std::path::PathBuf,
    pub tls: TlsFileConfig,
    pub max_clock_skew_seconds: u64,
    pub suggested_heartbeat_interval_seconds: u64,
    pub trusted_nodes: Vec<TrustedNodeConfig>,
    pub mtls_peers: Vec<PeerBindingConfig>,
}

#[derive(Clone, Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct TrustedNodeConfig {
    pub node_id: String,
    pub key_id: String,
    pub public_key_base64: String,
    pub enabled: bool,
}

impl ControllerConfig {
    pub fn load(path: &Path) -> Result<Self> {
        let raw = fs::read_to_string(path)
            .with_context(|| format!("reading controller config {}", path.display()))?;
        let config: Self = toml::from_str(&raw).context("parsing controller configuration")?;
        anyhow::ensure!(!config.domain_id.trim().is_empty(), "domain_id cannot be empty");
        anyhow::ensure!(
            !config.controller_id.trim().is_empty(),
            "controller_id cannot be empty"
        );
        anyhow::ensure!(
            config.authority_mode == "single-authoritative-controller",
            "this Epoch 2 skeleton supports only single-authoritative-controller mode"
        );
        anyhow::ensure!(
            config.suggested_heartbeat_interval_seconds > 0,
            "suggested_heartbeat_interval_seconds must be positive"
        );
        Ok(config)
    }
}
