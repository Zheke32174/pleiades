use std::{fs, path::Path};

use anyhow::{Context, Result};
use pdk_transport::{PeerBindingConfig, TlsFileConfig};
use serde::Deserialize;

#[derive(Clone, Copy, Debug, Default, Deserialize, Eq, PartialEq)]
#[serde(rename_all = "kebab-case")]
pub enum StartupMode {
    #[default]
    Managed,
    Standalone,
    Quarantined,
}

#[derive(Clone, Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct NodeAgentConfig {
    pub domain_id: String,
    pub node_id: String,
    pub listen: String,
    pub control_plane_uri: String,
    pub control_plane_server_name: String,
    pub signing_key_file: std::path::PathBuf,
    pub state_database: std::path::PathBuf,
    pub power_class: String,
    pub trust_zone: String,
    #[serde(default)]
    pub startup_mode: StartupMode,
    pub heartbeat_interval_seconds: u64,
    pub heartbeat_timeout_seconds: u64,
    pub read_only_timeout_seconds: u64,
    pub lease_sweep_interval_seconds: u64,
    pub max_clock_skew_seconds: u64,
    pub tls: TlsFileConfig,
    pub trusted_controllers: Vec<TrustedControllerConfig>,
    pub mtls_peers: Vec<PeerBindingConfig>,
}

#[derive(Clone, Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct TrustedControllerConfig {
    pub controller_id: String,
    pub key_id: String,
    pub public_key_base64: String,
    pub enabled: bool,
}

impl NodeAgentConfig {
    pub fn load(path: &Path) -> Result<Self> {
        let raw = fs::read_to_string(path)
            .with_context(|| format!("reading node-agent config {}", path.display()))?;
        let config: Self = toml::from_str(&raw).context("parsing node-agent configuration")?;
        config.validate()?;
        Ok(config)
    }

    fn validate(&self) -> Result<()> {
        anyhow::ensure!(
            !self.domain_id.trim().is_empty(),
            "domain_id cannot be empty"
        );
        anyhow::ensure!(!self.node_id.trim().is_empty(), "node_id cannot be empty");
        anyhow::ensure!(
            self.heartbeat_interval_seconds > 0,
            "heartbeat_interval_seconds must be positive"
        );
        anyhow::ensure!(
            self.heartbeat_timeout_seconds > self.heartbeat_interval_seconds,
            "heartbeat_timeout_seconds must exceed heartbeat_interval_seconds"
        );
        anyhow::ensure!(
            self.read_only_timeout_seconds >= self.heartbeat_timeout_seconds,
            "read_only_timeout_seconds must be at least heartbeat_timeout_seconds"
        );
        anyhow::ensure!(
            self.lease_sweep_interval_seconds > 0,
            "lease_sweep_interval_seconds must be positive"
        );
        if self.startup_mode == StartupMode::Managed {
            anyhow::ensure!(
                !self.trusted_controllers.iter().all(|controller| !controller.enabled),
                "managed startup requires at least one enabled trusted controller"
            );
        }
        Ok(())
    }
}
