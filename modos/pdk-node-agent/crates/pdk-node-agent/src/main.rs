mod audit;
mod autonomy;
mod config;
mod control_link;
mod heartbeat;
mod inventory;
mod leases;
mod policy;
mod reconciliation;
mod rpc;
mod runtime;

use std::{net::SocketAddr, path::PathBuf, sync::Arc, time::Duration};

use anyhow::{Context, Result};
use clap::Parser;
use pdk_crypto::load_signing_key;
use pdk_protocol::v1::node_agent_server::NodeAgentServer;
use pdk_transport::{CertificateIdentityInterceptor, PeerRegistry, server_tls};
use serde::Serialize;
use tonic::transport::Server;
use tracing::info;
use tracing_subscriber::EnvFilter;

use crate::{
    audit::OfflineAuditBuffer,
    autonomy::AutonomyStateMachine,
    config::NodeAgentConfig,
    control_link::ControlPlaneLink,
    heartbeat::HeartbeatLoop,
    inventory::InventoryManager,
    leases::LeaseManager,
    policy::{PolicyEnforcer, build_trusted_controller_keys},
    reconciliation::ReconciliationWorker,
    rpc::NodeAgentService,
    runtime::{RuntimeManager, SystemdDriver},
};

#[derive(Debug, Parser)]
struct Args {
    #[arg(long, default_value = "/etc/pleiades/pdk-node-agent.toml")]
    config: PathBuf,
}

#[derive(Serialize)]
struct AgentLifecycleEvent<'a> {
    node_id: &'a str,
    version: &'a str,
    runtime: &'a str,
    authority_mode: &'a str,
}

#[tokio::main]
async fn main() -> Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter(EnvFilter::try_from_default_env().unwrap_or_else(|_| "info".into()))
        .init();

    let args = Args::parse();
    let config = Arc::new(NodeAgentConfig::load(&args.config)?);
    let bind: SocketAddr = config
        .listen
        .parse()
        .with_context(|| format!("invalid node-agent listen address {}", config.listen))?;
    let signing_key = Arc::new(load_signing_key(&config.signing_key_file)?);
    let trusted_controllers = build_trusted_controller_keys(&config.trusted_controllers)?;

    let autonomy = AutonomyStateMachine::new(
        Duration::from_secs(config.heartbeat_timeout_seconds),
        Duration::from_secs(config.read_only_timeout_seconds),
    );
    let audit = OfflineAuditBuffer::open(
        &config.state_database,
        config.domain_id.clone(),
        config.node_id.clone(),
        signing_key.clone(),
    )
    .await?;
    let policy = PolicyEnforcer::new(
        config.domain_id.clone(),
        config.node_id.clone(),
        autonomy.clone(),
        config.max_clock_skew_seconds,
        trusted_controllers.clone(),
    );
    let control = ControlPlaneLink::new(
        &config.control_plane_uri,
        &config.control_plane_server_name,
        &config.tls,
        config.domain_id.clone(),
        config.node_id.clone(),
        trusted_controllers,
    )?;
    let inventory = InventoryManager::new(config.power_class.clone(), config.trust_zone.clone());
    let systemd_driver = Arc::new(SystemdDriver::connect().await?);
    let runtime = RuntimeManager::new(systemd_driver);

    let lifecycle = AgentLifecycleEvent {
        node_id: &config.node_id,
        version: env!("CARGO_PKG_VERSION"),
        runtime: "systemd-transient-unit-over-dbus",
        authority_mode: "single-authoritative-controller-no-quorum",
    };
    audit
        .queue_event("node.agent.started", "startup", &lifecycle)
        .await
        .context("persisting node-agent startup event")?;

    let peer_registry = PeerRegistry::new(config.mtls_peers.clone())?;
    let interceptor =
        CertificateIdentityInterceptor::new(peer_registry).requiring_role("controller");
    let tls = server_tls(&config.tls)?;
    let rpc_service = NodeAgentService::new(
        config.domain_id.clone(),
        config.node_id.clone(),
        autonomy.clone(),
        policy.clone(),
        runtime.clone(),
        audit.clone(),
    );

    let autonomy_task = tokio::spawn(autonomy.clone().monitor());
    let heartbeat_task = tokio::spawn(
        HeartbeatLoop::new(
            config.domain_id.clone(),
            config.node_id.clone(),
            Duration::from_secs(config.heartbeat_interval_seconds),
            signing_key,
            inventory,
            autonomy.clone(),
            control.clone(),
        )
        .run(),
    );
    let reconciliation_task =
        tokio::spawn(ReconciliationWorker::new(autonomy.clone(), audit.clone(), control).run());
    let lease_task = tokio::spawn(
        LeaseManager::new(
            Duration::from_secs(config.lease_sweep_interval_seconds),
            policy,
            runtime,
            audit,
        )
        .run(),
    );

    info!(
        bind = %bind,
        domain_id = %config.domain_id,
        node_id = %config.node_id,
        "PDK node kernel agent ready"
    );

    let server_result = Server::builder()
        .tls_config(tls)?
        .add_service(NodeAgentServer::with_interceptor(rpc_service, interceptor))
        .serve_with_shutdown(bind, shutdown_signal())
        .await
        .context("serving PDK node-agent gRPC API");

    autonomy_task.abort();
    heartbeat_task.abort();
    reconciliation_task.abort();
    lease_task.abort();
    server_result
}

async fn shutdown_signal() {
    if let Err(error) = tokio::signal::ctrl_c().await {
        tracing::error!(error = %error, "failed to install Ctrl-C handler");
    }
}
