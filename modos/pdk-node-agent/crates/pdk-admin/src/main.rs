use std::{collections::HashMap, fs, path::{Path, PathBuf}, time::{SystemTime, UNIX_EPOCH}};

use anyhow::{bail, Context, Result};
use clap::{Parser, Subcommand};
use pdk_crypto::{load_signing_key, sign_capability};
use pdk_protocol::{
    v1::{
        node_agent_client::NodeAgentClient, CapabilityAction, CapabilityGrantPayload,
        GetWorkloadStatusRequest, IsolationConstraints, SignedCapabilityGrant,
        SpawnWorkloadRequest, StopWorkloadRequest, WorkloadSpec,
    },
    PROTOCOL_VERSION,
};
use pdk_transport::{client_tls, TlsFileConfig};
use serde::Deserialize;
use tonic::transport::{Channel, Endpoint};
use uuid::Uuid;

#[derive(Debug, Parser)]
struct Args {
    #[arg(long, default_value = "/etc/pleiades/pdk-admin.toml")]
    config: PathBuf,
    #[command(subcommand)]
    command: Command,
}

#[derive(Debug, Subcommand)]
enum Command {
    Run {
        #[arg(long)]
        node: String,
        #[arg(long)]
        workload_id: String,
        #[arg(long)]
        executable: String,
        #[arg(long = "arg")]
        args: Vec<String>,
        #[arg(long = "env", value_parser = parse_key_value)]
        environment: Vec<(String, String)>,
        #[arg(long, default_value_t = 300)]
        lease_seconds: u64,
        #[arg(long, default_value_t = 0)]
        memory_max_bytes: u64,
        #[arg(long, default_value_t = 0)]
        cpu_quota_percent: u32,
        #[arg(long, default_value_t = true, action = clap::ArgAction::Set)]
        network_denied: bool,
    },
    Status {
        #[arg(long)]
        node: String,
        #[arg(long)]
        workload_id: String,
        #[arg(long, default_value_t = 60)]
        lease_seconds: u64,
    },
    Stop {
        #[arg(long)]
        node: String,
        #[arg(long)]
        workload_id: String,
        #[arg(long, default_value = "operator request")]
        reason: String,
        #[arg(long, default_value_t = 60)]
        lease_seconds: u64,
    },
}

#[derive(Clone, Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct AdminConfig {
    domain_id: String,
    controller_id: String,
    signing_key_file: PathBuf,
    tls: TlsFileConfig,
    nodes: Vec<NodeEndpoint>,
}

#[derive(Clone, Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct NodeEndpoint {
    node_id: String,
    uri: String,
    server_name: String,
}

impl AdminConfig {
    fn load(path: &Path) -> Result<Self> {
        let raw = fs::read_to_string(path)
            .with_context(|| format!("reading admin config {}", path.display()))?;
        toml::from_str(&raw).context("parsing admin configuration")
    }

    fn node(&self, node_id: &str) -> Result<&NodeEndpoint> {
        self.nodes
            .iter()
            .find(|node| node.node_id == node_id)
            .with_context(|| format!("node endpoint {node_id} not configured"))
    }
}

#[tokio::main]
async fn main() -> Result<()> {
    let args = Args::parse();
    let config = AdminConfig::load(&args.config)?;
    let signing_key = load_signing_key(&config.signing_key_file)?;

    match args.command {
        Command::Run {
            node,
            workload_id,
            executable,
            args,
            environment,
            lease_seconds,
            memory_max_bytes,
            cpu_quota_percent,
            network_denied,
        } => {
            let endpoint = config.node(&node)?;
            let mut client = connect(endpoint, &config.tls)?;
            let isolation = isolation(network_denied, memory_max_bytes, cpu_quota_percent);
            let grant = grant(
                &config,
                &signing_key,
                endpoint,
                &workload_id,
                lease_seconds,
                vec![
                    CapabilityAction::SpawnWorkload,
                    CapabilityAction::StatusWorkload,
                    CapabilityAction::StopWorkload,
                ],
                isolation.clone(),
            );
            let token_id = grant.payload.as_ref().context("generated grant payload missing")?.token_id.clone();
            let lease_id = grant.payload.as_ref().context("generated grant payload missing")?.lease_id.clone();
            push_grant(&mut client, grant).await?;
            let receipt = client
                .spawn_workload(SpawnWorkloadRequest {
                    trace_id: Uuid::new_v4().to_string(),
                    capability_token_id: token_id,
                    lease_id,
                    workload: Some(WorkloadSpec {
                        workload_id,
                        executable,
                        args,
                        environment: environment.into_iter().collect::<HashMap<_, _>>(),
                        working_directory: String::new(),
                        isolation: Some(isolation),
                        singleton_destructive: false,
                    }),
                })
                .await
                .context("requesting bounded workload start")?
                .into_inner();
            println!("{receipt:#?}");
        }
        Command::Status {
            node,
            workload_id,
            lease_seconds,
        } => {
            let endpoint = config.node(&node)?;
            let mut client = connect(endpoint, &config.tls)?;
            let grant = grant(
                &config,
                &signing_key,
                endpoint,
                &workload_id,
                lease_seconds,
                vec![CapabilityAction::StatusWorkload],
                isolation(true, 0, 0),
            );
            let token_id = grant.payload.as_ref().context("generated grant payload missing")?.token_id.clone();
            push_grant(&mut client, grant).await?;
            let receipt = client
                .get_workload_status(GetWorkloadStatusRequest {
                    trace_id: Uuid::new_v4().to_string(),
                    capability_token_id: token_id,
                    workload_id,
                })
                .await
                .context("reading workload status")?
                .into_inner();
            println!("{receipt:#?}");
        }
        Command::Stop {
            node,
            workload_id,
            reason,
            lease_seconds,
        } => {
            let endpoint = config.node(&node)?;
            let mut client = connect(endpoint, &config.tls)?;
            let grant = grant(
                &config,
                &signing_key,
                endpoint,
                &workload_id,
                lease_seconds,
                vec![CapabilityAction::StopWorkload],
                isolation(true, 0, 0),
            );
            let token_id = grant.payload.as_ref().context("generated grant payload missing")?.token_id.clone();
            push_grant(&mut client, grant).await?;
            let receipt = client
                .stop_workload(StopWorkloadRequest {
                    trace_id: Uuid::new_v4().to_string(),
                    capability_token_id: token_id,
                    workload_id,
                    reason,
                })
                .await
                .context("requesting workload stop")?
                .into_inner();
            println!("{receipt:#?}");
        }
    }
    Ok(())
}

fn connect(endpoint: &NodeEndpoint, tls: &TlsFileConfig) -> Result<NodeAgentClient<Channel>> {
    let endpoint = Endpoint::from_shared(endpoint.uri.clone())
        .context("parsing node-agent URI")?
        .tls_config(client_tls(tls, &endpoint.server_name)?)?;
    Ok(NodeAgentClient::new(endpoint.connect_lazy()))
}

fn grant(
    config: &AdminConfig,
    key: &pdk_crypto::LoadedSigningKey,
    endpoint: &NodeEndpoint,
    workload_id: &str,
    lease_seconds: u64,
    actions: Vec<CapabilityAction>,
    isolation: IsolationConstraints,
) -> SignedCapabilityGrant {
    let now = unix_ms();
    sign_capability(
        CapabilityGrantPayload {
            protocol_version: PROTOCOL_VERSION,
            token_id: Uuid::new_v4().to_string(),
            domain_id: config.domain_id.clone(),
            issuer_id: config.controller_id.clone(),
            subject_workload_id: workload_id.to_owned(),
            target_node_id: endpoint.node_id.clone(),
            lease_id: Uuid::new_v4().to_string(),
            actions: actions.into_iter().map(|action| action as i32).collect(),
            issued_at_unix_ms: now,
            not_before_unix_ms: now.saturating_sub(1_000),
            expires_at_unix_ms: now.saturating_add(lease_seconds.saturating_mul(1_000)),
            policy_version: "epoch2-local-policy-v1".into(),
            nonce: Uuid::new_v4().to_string(),
            maximum_isolation: Some(isolation),
            singleton_destructive: false,
        },
        key,
    )
}

async fn push_grant(
    client: &mut NodeAgentClient<Channel>,
    grant: SignedCapabilityGrant,
) -> Result<()> {
    let ack = client
        .push_capability_grant(grant)
        .await
        .context("pushing signed capability grant")?
        .into_inner();
    if !ack.accepted {
        bail!("node rejected capability grant: {}", ack.message);
    }
    Ok(())
}

fn isolation(
    network_denied: bool,
    memory_max_bytes: u64,
    cpu_quota_percent: u32,
) -> IsolationConstraints {
    IsolationConstraints {
        network_denied,
        read_only_root: true,
        private_tmp: true,
        protect_home: true,
        no_new_privileges: true,
        dynamic_user: true,
        restrict_suid_sgid: true,
        restrict_address_families: true,
        memory_max_bytes,
        cpu_quota_percent,
        cgroup_slice: "pleiades-workloads.slice".into(),
    }
}

fn parse_key_value(value: &str) -> Result<(String, String), String> {
    let (key, value) = value
        .split_once('=')
        .ok_or_else(|| "environment must be KEY=VALUE".to_owned())?;
    if key.is_empty() || key.contains('=') || key.contains('\0') || value.contains('\0') {
        return Err("environment contains an invalid key or NUL byte".into());
    }
    Ok((key.to_owned(), value.to_owned()))
}

fn unix_ms() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis()
        .try_into()
        .unwrap_or(u64::MAX)
}
