mod config;
mod rpc;
mod state;
mod store;

use std::{collections::HashMap, net::SocketAddr, path::PathBuf, sync::Arc};

use anyhow::{Context, Result, bail};
use clap::Parser;
use config::ControllerConfig;
use pdk_crypto::{decode_verifying_key, load_signing_key};
use pdk_protocol::v1::control_plane_server::ControlPlaneServer;
use pdk_transport::{CertificateIdentityInterceptor, PeerRegistry, server_tls};
use rpc::ControlPlaneService;
use state::{ControllerState, TrustedNodeKey};
use store::ControllerStateStore;
use tokio::sync::RwLock;
use tonic::transport::Server;
use tracing::info;
use tracing_subscriber::EnvFilter;

#[derive(Debug, Parser)]
struct Args {
    #[arg(long, default_value = "/etc/pleiades/pdk-controller.toml")]
    config: PathBuf,
}

#[tokio::main]
async fn main() -> Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter(EnvFilter::try_from_default_env().unwrap_or_else(|_| "info".into()))
        .init();

    let args = Args::parse();
    let config = ControllerConfig::load(&args.config)?;
    let bind: SocketAddr = config
        .bind
        .parse()
        .with_context(|| format!("invalid controller bind address {}", config.bind))?;
    let signing_key = Arc::new(load_signing_key(&config.signing_key_file)?);
    let trusted_node_keys = Arc::new(build_node_key_store(&config)?);
    let store = ControllerStateStore::open(&config.state_database_file).await?;
    let peer_registry = PeerRegistry::new(config.mtls_peers.clone())?;
    let interceptor = CertificateIdentityInterceptor::new(peer_registry).requiring_role("node");
    let tls = server_tls(&config.tls)?;

    let state = ControllerState {
        config: Arc::new(config),
        signing_key,
        trusted_node_keys,
        replay: Arc::new(RwLock::new(HashMap::new())),
        observations: Arc::new(RwLock::new(HashMap::new())),
        store,
    };

    info!(
        bind = %bind,
        domain_id = %state.config.domain_id,
        controller_id = %state.config.controller_id,
        authority_mode = %state.config.authority_mode,
        state_database = %state.config.state_database_file.display(),
        "PDK control plane ready"
    );

    Server::builder()
        .tls_config(tls)?
        .add_service(ControlPlaneServer::with_interceptor(
            ControlPlaneService::new(state),
            interceptor,
        ))
        .serve(bind)
        .await
        .context("serving PDK control plane")?;
    Ok(())
}

fn build_node_key_store(config: &ControllerConfig) -> Result<HashMap<String, TrustedNodeKey>> {
    let mut store = HashMap::new();
    for node in &config.trusted_nodes {
        if !node.enabled {
            continue;
        }
        if store.contains_key(&node.node_id) {
            bail!("duplicate trusted node ID {}", node.node_id);
        }
        store.insert(
            node.node_id.clone(),
            TrustedNodeKey {
                key_id: node.key_id.clone(),
                verifying_key: decode_verifying_key(&node.public_key_base64)
                    .with_context(|| format!("decoding public key for {}", node.node_id))?,
            },
        );
    }
    Ok(store)
}
