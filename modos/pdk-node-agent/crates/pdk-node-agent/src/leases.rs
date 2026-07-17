use std::time::Duration;

use serde::Serialize;
use tracing::{info, warn};

use crate::{
    audit::OfflineAuditBuffer,
    autonomy::unix_ms,
    policy::PolicyEnforcer,
    runtime::RuntimeManager,
};

#[derive(Clone)]
pub struct LeaseManager {
    interval: Duration,
    policy: PolicyEnforcer,
    runtime: RuntimeManager,
    audit: OfflineAuditBuffer,
}

#[derive(Serialize)]
struct LeaseExpiryEvent<'a> {
    token_id: &'a str,
    lease_id: &'a str,
    workload_id: &'a str,
    stop_result: &'a str,
}

impl LeaseManager {
    pub fn new(
        interval: Duration,
        policy: PolicyEnforcer,
        runtime: RuntimeManager,
        audit: OfflineAuditBuffer,
    ) -> Self {
        Self {
            interval,
            policy,
            runtime,
            audit,
        }
    }

    pub async fn run(self) {
        let mut ticker = tokio::time::interval(self.interval);
        ticker.set_missed_tick_behavior(tokio::time::MissedTickBehavior::Skip);
        loop {
            ticker.tick().await;
            let expired = self.policy.purge_expired(unix_ms()).await;
            for grant in expired {
                let reason = "capability lease expired";
                let results = self.runtime.stop_by_token(&grant.token_id, reason).await;
                if results.is_empty() {
                    info!(token_id = %grant.token_id, lease_id = %grant.lease_id, "purged expired capability without an active workload");
                    let _ = self
                        .audit
                        .queue_event(
                            "capability.expired",
                            "lease-sweeper",
                            &LeaseExpiryEvent {
                                token_id: &grant.token_id,
                                lease_id: &grant.lease_id,
                                workload_id: &grant.subject_workload_id,
                                stop_result: "no active workload",
                            },
                        )
                        .await;
                    continue;
                }
                for (workload_id, result) in results {
                    let stop_result = match &result {
                        Ok(receipt) => receipt.detail.clone(),
                        Err(error) => error.to_string(),
                    };
                    let _ = self
                        .audit
                        .queue_event(
                            "lease.expired.workload_terminated",
                            "lease-sweeper",
                            &LeaseExpiryEvent {
                                token_id: &grant.token_id,
                                lease_id: &grant.lease_id,
                                workload_id: &workload_id,
                                stop_result: &stop_result,
                            },
                        )
                        .await;
                    match result {
                        Ok(_) => info!(workload_id = %workload_id, token_id = %grant.token_id, "terminated workload after lease expiry"),
                        Err(error) => warn!(workload_id = %workload_id, token_id = %grant.token_id, error = %error, "failed to terminate workload after lease expiry"),
                    }
                }
            }
        }
    }
}
