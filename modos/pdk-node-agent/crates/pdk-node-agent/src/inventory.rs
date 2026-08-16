use std::{ffi::OsStr, path::Path, time::Duration};

use pdk_protocol::v1::{
    CpuInventory, DiskInventory, MemoryInventory, NetworkInterfaceInventory, NodeInventory,
    RuntimeCapability,
};
use sysinfo::{Disks, Networks, System};
use tokio::process::Command;

use crate::autonomy::unix_ms;

#[derive(Clone)]
pub struct InventoryManager {
    power_class: String,
    trust_zone: String,
}

impl InventoryManager {
    pub fn new(power_class: impl Into<String>, trust_zone: impl Into<String>) -> Self {
        Self {
            power_class: power_class.into(),
            trust_zone: trust_zone.into(),
        }
    }

    pub async fn collect(&self) -> NodeInventory {
        let mut system = System::new_all();
        system.refresh_all();
        tokio::time::sleep(Duration::from_millis(250)).await;
        system.refresh_cpu_usage();
        system.refresh_memory();

        let disks = Disks::new_with_refreshed_list();
        let networks = Networks::new_with_refreshed_list();
        let cpus = system.cpus();
        let cpu_brand = cpus
            .first()
            .map(|cpu| cpu.brand().to_owned())
            .unwrap_or_else(|| "unknown".to_owned());

        let runtimes = vec![
            probe_runtime(
                "systemd",
                &["/usr/bin/systemctl", "/bin/systemctl"],
                &["--version"],
            )
            .await,
            probe_runtime(
                "podman",
                &["/usr/bin/podman", "/bin/podman"],
                &["--version"],
            )
            .await,
            probe_runtime("libvirt", &["/usr/bin/virsh", "/bin/virsh"], &["--version"]).await,
        ];

        NodeInventory {
            collected_at_unix_ms: unix_ms(),
            hostname: System::host_name().unwrap_or_else(|| "unknown".into()),
            os_name: System::name().unwrap_or_else(|| "unknown".into()),
            os_version: System::os_version().unwrap_or_else(|| "unknown".into()),
            kernel_version: System::kernel_version().unwrap_or_else(|| "unknown".into()),
            architecture: System::cpu_arch(),
            uptime_seconds: System::uptime(),
            cpu: Some(CpuInventory {
                architecture: System::cpu_arch(),
                logical_cores: cpus.len().try_into().unwrap_or(u32::MAX),
                physical_cores: System::physical_core_count()
                    .unwrap_or(cpus.len())
                    .try_into()
                    .unwrap_or(u32::MAX),
                brand: cpu_brand,
                global_usage_milli_percent: (system.global_cpu_usage().clamp(0.0, 100.0) * 1_000.0)
                    .round() as u32,
            }),
            memory: Some(MemoryInventory {
                total_bytes: system.total_memory(),
                available_bytes: system.available_memory(),
                used_bytes: system.used_memory(),
            }),
            disks: disks
                .iter()
                .map(|disk| DiskInventory {
                    name: os_to_string(disk.name()),
                    file_system: os_to_string(disk.file_system()),
                    mount_point: disk.mount_point().display().to_string(),
                    total_bytes: disk.total_space(),
                    available_bytes: disk.available_space(),
                    read_only: disk.is_read_only(),
                    removable: disk.is_removable(),
                })
                .collect(),
            network_interfaces: networks
                .iter()
                .map(|(name, data)| NetworkInterfaceInventory {
                    name: name.clone(),
                    total_received_bytes: data.total_received(),
                    total_transmitted_bytes: data.total_transmitted(),
                })
                .collect(),
            runtimes,
            gpu_present: gpu_present(),
            power_class: self.power_class.clone(),
            trust_zone: self.trust_zone.clone(),
        }
    }
}

async fn probe_runtime(name: &str, candidates: &[&str], args: &[&str]) -> RuntimeCapability {
    let Some(executable) = candidates
        .iter()
        .find(|candidate| Path::new(candidate).is_file())
    else {
        return RuntimeCapability {
            name: name.to_owned(),
            available: false,
            version: String::new(),
            probe_detail: "executable not found at an approved absolute path".into(),
        };
    };

    let result = tokio::time::timeout(
        Duration::from_secs(2),
        Command::new(executable).args(args).output(),
    )
    .await;
    match result {
        Ok(Ok(output)) => {
            let stdout = String::from_utf8_lossy(&output.stdout);
            let stderr = String::from_utf8_lossy(&output.stderr);
            let line = stdout
                .lines()
                .chain(stderr.lines())
                .find(|line| !line.trim().is_empty())
                .unwrap_or_default()
                .trim()
                .to_owned();
            RuntimeCapability {
                name: name.to_owned(),
                available: output.status.success(),
                version: line,
                probe_detail: format!("direct argv probe via {executable}"),
            }
        }
        Ok(Err(error)) => RuntimeCapability {
            name: name.to_owned(),
            available: false,
            version: String::new(),
            probe_detail: format!("probe failed: {error}"),
        },
        Err(_) => RuntimeCapability {
            name: name.to_owned(),
            available: false,
            version: String::new(),
            probe_detail: "probe timed out".into(),
        },
    }
}

fn gpu_present() -> bool {
    [
        "/dev/nvidia0",
        "/dev/dri/renderD128",
        "/sys/class/drm/card0/device/vendor",
    ]
    .iter()
    .any(|path| Path::new(path).exists())
}

fn os_to_string(value: &OsStr) -> String {
    value.to_string_lossy().into_owned()
}
