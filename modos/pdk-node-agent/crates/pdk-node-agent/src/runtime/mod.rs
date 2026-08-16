mod systemd;

use std::{collections::HashMap, sync::Arc};

use anyhow::{Context, Result, bail};
use async_trait::async_trait;
use pdk_protocol::v1::{WorkloadReceipt, WorkloadSpec};
use tokio::sync::RwLock;

pub use systemd::SystemdDriver;

#[derive(Clone, Debug)]
pub struct PreparedWorkload {
    pub workload: WorkloadSpec,
    pub runtime_object_id: String,
}

#[derive(Clone, Debug)]
pub struct RuntimeHandle {
    pub workload_id: String,
    pub runtime: String,
    pub runtime_object_id: String,
}

#[async_trait]
pub trait RuntimeDriver: Send + Sync {
    fn name(&self) -> &'static str;
    async fn prepare(&self, workload: &WorkloadSpec) -> Result<PreparedWorkload>;
    async fn start(&self, prepared: PreparedWorkload) -> Result<RuntimeHandle>;
    async fn status(&self, handle: &RuntimeHandle) -> Result<WorkloadReceipt>;
    async fn stop(&self, handle: &RuntimeHandle, reason: &str) -> Result<WorkloadReceipt>;
    async fn cleanup(&self, handle: &RuntimeHandle) -> Result<()>;
}

#[derive(Clone)]
pub struct RuntimeManager {
    driver: Arc<dyn RuntimeDriver>,
    active: Arc<RwLock<HashMap<String, ActiveWorkload>>>,
}

#[derive(Clone)]
struct ActiveWorkload {
    handle: RuntimeHandle,
    token_id: String,
}

impl RuntimeManager {
    pub fn new(driver: Arc<dyn RuntimeDriver>) -> Self {
        Self {
            driver,
            active: Arc::new(RwLock::new(HashMap::new())),
        }
    }

    pub async fn start(
        &self,
        workload: &WorkloadSpec,
        token_id: &str,
        _lease_id: &str,
    ) -> Result<WorkloadReceipt> {
        if self.active.read().await.contains_key(&workload.workload_id) {
            bail!(
                "workload {} is already known to the runtime manager",
                workload.workload_id
            );
        }
        let prepared = self.driver.prepare(workload).await?;
        let handle = self.driver.start(prepared).await?;
        let active = ActiveWorkload {
            handle: handle.clone(),
            token_id: token_id.to_owned(),
        };
        self.active
            .write()
            .await
            .insert(workload.workload_id.clone(), active);
        match self.driver.status(&handle).await {
            Ok(receipt) => Ok(receipt),
            Err(error) => {
                let _ = self
                    .driver
                    .stop(&handle, "runtime status failed immediately after start")
                    .await;
                let _ = self.driver.cleanup(&handle).await;
                self.active.write().await.remove(&workload.workload_id);
                Err(error)
                    .context("workload started but could not be observed; stopped fail-closed")
            }
        }
    }

    pub async fn status(&self, workload_id: &str) -> Result<WorkloadReceipt> {
        let active = self
            .active
            .read()
            .await
            .get(workload_id)
            .cloned()
            .with_context(|| format!("workload {workload_id} is not locally registered"))?;
        self.driver.status(&active.handle).await
    }

    pub async fn stop(&self, workload_id: &str, reason: &str) -> Result<WorkloadReceipt> {
        let active = self
            .active
            .read()
            .await
            .get(workload_id)
            .cloned()
            .with_context(|| format!("workload {workload_id} is not locally registered"))?;
        let receipt = self.driver.stop(&active.handle, reason).await?;
        self.active.write().await.remove(workload_id);
        if let Err(error) = self.driver.cleanup(&active.handle).await {
            tracing::warn!(workload_id, error = %error, "runtime cleanup failed after stop");
        }
        Ok(receipt)
    }

    pub async fn stop_by_token(
        &self,
        token_id: &str,
        reason: &str,
    ) -> Vec<(String, Result<WorkloadReceipt>)> {
        let workload_ids = self
            .active
            .read()
            .await
            .iter()
            .filter_map(|(workload_id, active)| {
                (active.token_id == token_id).then_some(workload_id.clone())
            })
            .collect::<Vec<_>>();
        let mut results = Vec::with_capacity(workload_ids.len());
        for workload_id in workload_ids {
            let result = self.stop(&workload_id, reason).await;
            results.push((workload_id, result));
        }
        results
    }
}
