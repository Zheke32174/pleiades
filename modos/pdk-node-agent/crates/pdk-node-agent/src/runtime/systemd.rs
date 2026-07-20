use std::path::Path;

use anyhow::{Context, Result, bail};
use async_trait::async_trait;
use pdk_protocol::v1::{IsolationConstraints, WorkloadReceipt, WorkloadSpec, WorkloadState};
use zbus::Connection;
use zvariant::{OwnedObjectPath, OwnedValue, Value};

use super::{PreparedWorkload, RuntimeDriver, RuntimeHandle};

#[zbus::proxy(
    interface = "org.freedesktop.systemd1.Manager",
    default_service = "org.freedesktop.systemd1",
    default_path = "/org/freedesktop/systemd1"
)]
trait SystemdManager {
    #[zbus(name = "StartTransientUnit")]
    fn start_transient_unit(
        &self,
        name: String,
        mode: String,
        properties: Vec<(String, OwnedValue)>,
        aux: Vec<(String, Vec<(String, OwnedValue)>)>,
    ) -> zbus::Result<OwnedObjectPath>;

    #[zbus(name = "StopUnit")]
    fn stop_unit(&self, name: String, mode: String) -> zbus::Result<OwnedObjectPath>;

    #[zbus(name = "GetUnit")]
    fn get_unit(&self, name: String) -> zbus::Result<OwnedObjectPath>;

    #[zbus(name = "ResetFailedUnit")]
    fn reset_failed_unit(&self, name: String) -> zbus::Result<()>;
}

#[zbus::proxy(
    interface = "org.freedesktop.systemd1.Unit",
    default_service = "org.freedesktop.systemd1"
)]
trait SystemdUnit {
    #[zbus(property)]
    fn active_state(&self) -> zbus::Result<String>;

    #[zbus(property)]
    fn sub_state(&self) -> zbus::Result<String>;
}

#[derive(Clone)]
pub struct SystemdDriver {
    connection: Connection,
}

impl SystemdDriver {
    pub async fn connect() -> Result<Self> {
        let connection = Connection::system()
            .await
            .context("connecting directly to the system D-Bus")?;
        Ok(Self { connection })
    }

    async fn manager(&self) -> Result<SystemdManagerProxy<'_>> {
        SystemdManagerProxy::new(&self.connection)
            .await
            .context("creating systemd manager proxy")
    }

    async fn unit_proxy(&self, unit_name: &str) -> Result<SystemdUnitProxy<'_>> {
        let manager = self.manager().await?;
        let path = manager
            .get_unit(unit_name.to_owned())
            .await
            .with_context(|| format!("resolving systemd unit {unit_name}"))?;
        SystemdUnitProxy::builder(&self.connection)
            .path(path)?
            .build()
            .await
            .with_context(|| format!("creating systemd unit proxy for {unit_name}"))
    }
}

#[async_trait]
impl RuntimeDriver for SystemdDriver {
    fn name(&self) -> &'static str {
        "systemd-transient-unit"
    }

    async fn prepare(&self, workload: &WorkloadSpec) -> Result<PreparedWorkload> {
        validate_workload(workload)?;
        Ok(PreparedWorkload {
            workload: workload.clone(),
            runtime_object_id: unit_name(&workload.workload_id),
        })
    }

    async fn start(&self, prepared: PreparedWorkload) -> Result<RuntimeHandle> {
        let manager = self.manager().await?;
        let properties = build_properties(&prepared.workload)?;
        manager
            .start_transient_unit(
                prepared.runtime_object_id.clone(),
                "fail".into(),
                properties,
                Vec::new(),
            )
            .await
            .with_context(|| {
                format!(
                    "starting systemd transient unit {}",
                    prepared.runtime_object_id
                )
            })?;
        Ok(RuntimeHandle {
            workload_id: prepared.workload.workload_id,
            runtime: self.name().into(),
            runtime_object_id: prepared.runtime_object_id,
        })
    }

    async fn status(&self, handle: &RuntimeHandle) -> Result<WorkloadReceipt> {
        let proxy = self.unit_proxy(&handle.runtime_object_id).await?;
        let active_state = proxy.active_state().await.context("reading ActiveState")?;
        let sub_state = proxy.sub_state().await.context("reading SubState")?;
        Ok(WorkloadReceipt {
            workload_id: handle.workload_id.clone(),
            runtime: handle.runtime.clone(),
            runtime_object_id: handle.runtime_object_id.clone(),
            state: map_state(&active_state) as i32,
            observed_at_unix_ms: crate::autonomy::unix_ms(),
            detail: format!("systemd ActiveState={active_state}, SubState={sub_state}"),
            intent: None,
        })
    }

    async fn stop(&self, handle: &RuntimeHandle, reason: &str) -> Result<WorkloadReceipt> {
        let manager = self.manager().await?;
        manager
            .stop_unit(handle.runtime_object_id.clone(), "replace".into())
            .await
            .with_context(|| format!("stopping systemd unit {}", handle.runtime_object_id))?;
        Ok(WorkloadReceipt {
            workload_id: handle.workload_id.clone(),
            runtime: handle.runtime.clone(),
            runtime_object_id: handle.runtime_object_id.clone(),
            state: WorkloadState::Stopped as i32,
            observed_at_unix_ms: crate::autonomy::unix_ms(),
            detail: format!("stop requested through systemd D-Bus: {reason}"),
            intent: None,
        })
    }

    async fn cleanup(&self, handle: &RuntimeHandle) -> Result<()> {
        let manager = self.manager().await?;
        if let Err(error) = manager
            .reset_failed_unit(handle.runtime_object_id.clone())
            .await
        {
            tracing::debug!(
                unit = %handle.runtime_object_id,
                error = %error,
                "systemd unit was not failed or had already been collected"
            );
        }
        Ok(())
    }
}

fn validate_workload(workload: &WorkloadSpec) -> Result<()> {
    if workload.workload_id.is_empty() || workload.workload_id.len() > 128 {
        bail!("workload_id must contain 1..=128 bytes");
    }
    if !workload
        .workload_id
        .chars()
        .all(|character| character.is_ascii_alphanumeric() || matches!(character, '-' | '_' | '.'))
    {
        bail!("workload_id may contain only ASCII letters, digits, '.', '-', and '_'");
    }
    let executable = Path::new(&workload.executable);
    if !executable.is_absolute() {
        bail!("workload executable must be an absolute path");
    }
    if workload.executable.contains('\0') || workload.args.iter().any(|arg| arg.contains('\0')) {
        bail!("workload argv contains a NUL byte");
    }
    if !workload.working_directory.is_empty()
        && !Path::new(&workload.working_directory).is_absolute()
    {
        bail!("working_directory must be empty or absolute");
    }
    for (name, value) in &workload.environment {
        if name.is_empty() || name.contains('=') || name.contains('\0') || value.contains('\0') {
            bail!("environment contains an invalid key or NUL byte");
        }
    }
    Ok(())
}

fn build_properties(workload: &WorkloadSpec) -> Result<Vec<(String, OwnedValue)>> {
    let isolation = workload.isolation.clone().unwrap_or_else(default_isolation);
    let mut properties = Vec::new();
    push(
        &mut properties,
        "Description",
        format!("Pleiades workload {}", workload.workload_id),
    )?;
    push(&mut properties, "Type", "exec".to_owned())?;
    push(
        &mut properties,
        "CollectMode",
        "inactive-or-failed".to_owned(),
    )?;
    push(&mut properties, "DynamicUser", isolation.dynamic_user)?;
    push(&mut properties, "PrivateTmp", isolation.private_tmp)?;
    push(&mut properties, "PrivateNetwork", isolation.network_denied)?;
    push(
        &mut properties,
        "NoNewPrivileges",
        isolation.no_new_privileges,
    )?;
    push(
        &mut properties,
        "RestrictSUIDSGID",
        isolation.restrict_suid_sgid,
    )?;
    push(
        &mut properties,
        "ProtectSystem",
        if isolation.read_only_root {
            "strict"
        } else {
            "full"
        }
        .to_owned(),
    )?;
    push(
        &mut properties,
        "ProtectHome",
        if isolation.protect_home {
            "yes"
        } else {
            "read-only"
        }
        .to_owned(),
    )?;
    push(&mut properties, "ProtectKernelTunables", true)?;
    push(&mut properties, "ProtectKernelModules", true)?;
    push(&mut properties, "ProtectControlGroups", true)?;
    push(&mut properties, "LockPersonality", true)?;
    push(&mut properties, "RestrictRealtime", true)?;
    push(&mut properties, "CapabilityBoundingSet", 0_u64)?;
    push(&mut properties, "AmbientCapabilities", 0_u64)?;

    if isolation.restrict_address_families {
        let families = if isolation.network_denied {
            vec!["AF_UNIX".to_owned()]
        } else {
            vec![
                "AF_UNIX".to_owned(),
                "AF_INET".to_owned(),
                "AF_INET6".to_owned(),
            ]
        };
        push(&mut properties, "RestrictAddressFamilies", families)?;
    }
    if isolation.memory_max_bytes > 0 {
        push(&mut properties, "MemoryMax", isolation.memory_max_bytes)?;
    }
    if isolation.cpu_quota_percent > 0 {
        let quota_usec_per_sec = u64::from(isolation.cpu_quota_percent).saturating_mul(10_000);
        push(&mut properties, "CPUQuotaPerSecUSec", quota_usec_per_sec)?;
    }
    if !isolation.cgroup_slice.is_empty() {
        push(&mut properties, "Slice", isolation.cgroup_slice.clone())?;
    }
    if !workload.working_directory.is_empty() {
        push(
            &mut properties,
            "WorkingDirectory",
            workload.working_directory.clone(),
        )?;
    }
    if !workload.environment.is_empty() {
        let mut environment = workload
            .environment
            .iter()
            .map(|(key, value)| format!("{key}={value}"))
            .collect::<Vec<_>>();
        environment.sort();
        push(&mut properties, "Environment", environment)?;
    }

    let mut argv = Vec::with_capacity(workload.args.len() + 1);
    argv.push(workload.executable.clone());
    argv.extend(workload.args.iter().cloned());
    let exec_start = vec![(workload.executable.clone(), argv, false)];
    push(&mut properties, "ExecStart", exec_start)?;
    Ok(properties)
}

fn default_isolation() -> IsolationConstraints {
    IsolationConstraints {
        network_denied: true,
        read_only_root: true,
        private_tmp: true,
        protect_home: true,
        no_new_privileges: true,
        dynamic_user: true,
        restrict_suid_sgid: true,
        restrict_address_families: true,
        memory_max_bytes: 0,
        cpu_quota_percent: 0,
        cgroup_slice: "pleiades-workloads.slice".into(),
    }
}

fn push<T>(properties: &mut Vec<(String, OwnedValue)>, name: &str, value: T) -> Result<()>
where
    T: Into<Value<'static>> + zvariant::DynamicType,
{
    let value = Value::new(value)
        .try_into_owned()
        .context("converting systemd D-Bus property into owned variant")?;
    properties.push((name.to_owned(), value));
    Ok(())
}

fn unit_name(workload_id: &str) -> String {
    format!("pleiades-{workload_id}.service")
}

fn map_state(active_state: &str) -> WorkloadState {
    match active_state {
        "active" | "activating" | "reloading" => WorkloadState::Running,
        "inactive" | "deactivating" => WorkloadState::Stopped,
        "failed" => WorkloadState::Failed,
        _ => WorkloadState::Unknown,
    }
}
