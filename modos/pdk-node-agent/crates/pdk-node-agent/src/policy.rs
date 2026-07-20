mod grant_admission;

use std::{collections::HashMap, sync::Arc};

use anyhow::{Context, Result, anyhow, bail};
use ed25519_dalek::VerifyingKey;
use pdk_protocol::v1::{
    CapabilityAction, CapabilityGrantPayload, IsolationConstraints, NodeState, OfflinePolicy,
    SignedCapabilityGrant, WorkloadSpec,
};
use tokio::sync::RwLock;

pub use grant_admission::{GrantInstallOutcome, ValidatedGrant};
use grant_admission::validate_grant_time;

use crate::{autonomy::AutonomyStateMachine, config::TrustedControllerConfig};

#[derive(Clone)]
pub struct TrustedControllerKey {
    pub key_id: String,
    pub verifying_key: VerifyingKey,
}

#[derive(Clone)]
pub struct PolicyEnforcer {
    domain_id: String,
    node_id: String,
    autonomy: AutonomyStateMachine,
    max_clock_skew_ms: u64,
    trusted_controllers: Arc<HashMap<String, TrustedControllerKey>>,
    grants: Arc<RwLock<HashMap<String, CachedGrant>>>,
    highest_sequences: Arc<RwLock<HashMap<String, u64>>>,
}

#[derive(Clone)]
struct CachedGrant {
    envelope: SignedCapabilityGrant,
    payload: CapabilityGrantPayload,
}

#[derive(Clone, Debug)]
pub struct Authorization {
    pub token_id: String,
    pub lease_id: String,
    pub workload_id: String,
}

impl PolicyEnforcer {
    pub fn new(
        domain_id: impl Into<String>,
        node_id: impl Into<String>,
        autonomy: AutonomyStateMachine,
        max_clock_skew_seconds: u64,
        trusted_controllers: HashMap<String, TrustedControllerKey>,
    ) -> Self {
        Self {
            domain_id: domain_id.into(),
            node_id: node_id.into(),
            autonomy,
            max_clock_skew_ms: max_clock_skew_seconds.saturating_mul(1_000),
            trusted_controllers: Arc::new(trusted_controllers),
            grants: Arc::new(RwLock::new(HashMap::new())),
            highest_sequences: Arc::new(RwLock::new(HashMap::new())),
        }
    }

    pub fn validate_signed_grant(
        &self,
        envelope: SignedCapabilityGrant,
        authenticated_controller_id: &str,
    ) -> Result<ValidatedGrant> {
        grant_admission::validate_signed_grant(
            &self.domain_id,
            &self.node_id,
            &self.autonomy,
            self.max_clock_skew_ms,
            &self.trusted_controllers,
            envelope,
            authenticated_controller_id,
        )
    }

    pub async fn install_committed_grant(
        &self,
        validated: ValidatedGrant,
    ) -> Result<GrantInstallOutcome> {
        let token_id = validated.payload.token_id.clone();
        let sequence = validated.payload.grant_sequence;
        let sequence_key = validated.sequence_key.clone();
        let signature = validated.envelope.signature_base64.clone();

        // Every installation path keeps this lock order. Candidate validation
        // acquires neither lock and therefore cannot change active authority.
        let mut grants = self.grants.write().await;
        if let Some(existing) = grants.get(&token_id) {
            if existing.envelope.signature_base64 != signature {
                bail!("token ID collision with different signed content");
            }
            if existing.payload != validated.payload {
                bail!("token ID collision with different decoded payload");
            }
            return Ok(GrantInstallOutcome::Idempotent);
        }

        let mut highest_sequences = self.highest_sequences.write().await;
        if let Some(highest) = highest_sequences.get(&sequence_key).copied() {
            if sequence < highest {
                return Ok(GrantInstallOutcome::Superseded {
                    highest_sequence: highest,
                });
            }
            if sequence == highest {
                bail!(
                    "capability grant sequence {} collides with a different active token",
                    sequence
                );
            }
        }

        grants.insert(
            token_id,
            CachedGrant {
                envelope: validated.envelope,
                payload: validated.payload,
            },
        );
        highest_sequences.insert(sequence_key, sequence);
        Ok(GrantInstallOutcome::Installed)
    }

    pub async fn remove_active_grant(&self, token_id: &str) -> bool {
        // Expiry, revocation, and compaction must not lower the installed
        // sequence floor and reopen rollback.
        self.grants.write().await.remove(token_id).is_some()
    }

    pub async fn authorize_spawn(
        &self,
        token_id: &str,
        lease_id: &str,
        workload: &WorkloadSpec,
    ) -> Result<Authorization> {
        let grant = self
            .authorize_with(token_id, CapabilityAction::SpawnWorkload, |grant| {
                if grant.lease_id != lease_id {
                    bail!("lease ID does not match capability token");
                }
                if grant.subject_workload_id != workload.workload_id {
                    bail!("capability token subject does not match workload ID");
                }
                if workload.singleton_destructive && !grant.singleton_destructive {
                    bail!("capability does not authorize singleton destructive execution");
                }
                enforce_isolation_floor(
                    workload.isolation.as_ref(),
                    grant.maximum_isolation.as_ref(),
                )
            })
            .await?;
        Ok(Authorization {
            token_id: grant.token_id,
            lease_id: grant.lease_id,
            workload_id: workload.workload_id.clone(),
        })
    }

    pub async fn authorize_stop(&self, token_id: &str, workload_id: &str) -> Result<Authorization> {
        let grant = self
            .authorize_with(token_id, CapabilityAction::StopWorkload, |grant| {
                if grant.subject_workload_id != workload_id {
                    bail!("capability token subject does not match workload ID");
                }
                Ok(())
            })
            .await?;
        Ok(Authorization {
            token_id: grant.token_id,
            lease_id: grant.lease_id,
            workload_id: workload_id.to_owned(),
        })
    }

    pub async fn authorize_status(
        &self,
        token_id: &str,
        workload_id: &str,
    ) -> Result<Authorization> {
        let grant = self
            .authorize_with(token_id, CapabilityAction::StatusWorkload, |grant| {
                if grant.subject_workload_id != workload_id {
                    bail!("capability token subject does not match workload ID");
                }
                Ok(())
            })
            .await?;
        Ok(Authorization {
            token_id: grant.token_id,
            lease_id: grant.lease_id,
            workload_id: workload_id.to_owned(),
        })
    }

    pub async fn purge_expired(&self, now_unix_ms: u64) -> Vec<CapabilityGrantPayload> {
        let mut expired = Vec::new();
        let mut grants = self.grants.write().await;
        grants.retain(|_, cached| {
            let keep = cached.payload.expires_at_unix_ms > now_unix_ms;
            if !keep {
                expired.push(cached.payload.clone());
            }
            keep
        });
        expired
    }

    pub async fn cached_count(&self) -> u64 {
        self.grants
            .read()
            .await
            .len()
            .try_into()
            .unwrap_or(u64::MAX)
    }

    #[cfg(test)]
    async fn highest_installed_sequence(&self, sequence_key: &str) -> Option<u64> {
        self.highest_sequences
            .read()
            .await
            .get(sequence_key)
            .copied()
    }

    async fn authorize_with<F>(
        &self,
        token_id: &str,
        action: CapabilityAction,
        validate_subject: F,
    ) -> Result<CapabilityGrantPayload>
    where
        F: FnOnce(&CapabilityGrantPayload) -> Result<()>,
    {
        let grants = self.grants.read().await;
        let cached = grants
            .get(token_id)
            .context("capability token is not cached")?;
        validate_grant_time(&cached.payload, crate::autonomy::unix_ms(), self.max_clock_skew_ms)?;
        if !cached.payload.actions.contains(&(action as i32)) {
            bail!("capability token does not authorize requested action");
        }
        enforce_offline_policy(&cached.payload, self.autonomy.current(), action)?;
        validate_subject(&cached.payload)?;
        Ok(cached.payload.clone())
    }
}

pub fn build_trusted_controller_keys(
    configs: &[TrustedControllerConfig],
) -> Result<HashMap<String, TrustedControllerKey>> {
    let mut keys = HashMap::new();
    for config in configs.iter().filter(|config| config.enabled) {
        let verifying_key = pdk_crypto::decode_verifying_key(&config.public_key_base64)
            .with_context(|| format!("decoding controller key for {}", config.controller_id))?;
        if keys
            .insert(
                config.controller_id.clone(),
                TrustedControllerKey {
                    key_id: config.key_id.clone(),
                    verifying_key,
                },
            )
            .is_some()
        {
            bail!("duplicate trusted controller ID {}", config.controller_id);
        }
    }
    Ok(keys)
}

fn enforce_offline_policy(
    grant: &CapabilityGrantPayload,
    state: NodeState,
    action: CapabilityAction,
) -> Result<()> {
    let policy = OfflinePolicy::try_from(grant.offline_policy)
        .map_err(|_| anyhow!("unsupported capability offline policy"))?;
    let allowed = match state {
        NodeState::Connected => true,
        NodeState::DegradedAutonomous => match policy {
            OfflinePolicy::Deny | OfflinePolicy::Unspecified => false,
            OfflinePolicy::FinishCurrent => matches!(
                action,
                CapabilityAction::StopWorkload | CapabilityAction::StatusWorkload
            ),
            OfflinePolicy::BoundedCache => match action {
                CapabilityAction::SpawnWorkload => !grant.singleton_destructive,
                CapabilityAction::StopWorkload | CapabilityAction::StatusWorkload => true,
                _ => false,
            },
        },
        NodeState::ReadOnlySafe => {
            matches!(
                policy,
                OfflinePolicy::FinishCurrent | OfflinePolicy::BoundedCache
            ) && matches!(
                action,
                CapabilityAction::StopWorkload | CapabilityAction::StatusWorkload
            )
        }
        NodeState::Standalone | NodeState::Quarantined | NodeState::Unspecified => false,
    };
    if !allowed {
        bail!(
            "node state {:?} and offline policy {:?} deny requested capability action {:?}",
            state,
            policy,
            action
        );
    }
    Ok(())
}

// maximum_isolation is interpreted as the mandatory isolation floor carried by the grant.
fn enforce_isolation_floor(
    requested: Option<&IsolationConstraints>,
    required: Option<&IsolationConstraints>,
) -> Result<()> {
    let Some(required) = required else {
        return Ok(());
    };
    let requested = requested.context("workload omitted required isolation constraints")?;
    require_bool(
        requested.network_denied,
        required.network_denied,
        "network_denied",
    )?;
    require_bool(
        requested.read_only_root,
        required.read_only_root,
        "read_only_root",
    )?;
    require_bool(requested.private_tmp, required.private_tmp, "private_tmp")?;
    require_bool(
        requested.protect_home,
        required.protect_home,
        "protect_home",
    )?;
    require_bool(
        requested.no_new_privileges,
        required.no_new_privileges,
        "no_new_privileges",
    )?;
    require_bool(
        requested.dynamic_user,
        required.dynamic_user,
        "dynamic_user",
    )?;
    require_bool(
        requested.restrict_suid_sgid,
        required.restrict_suid_sgid,
        "restrict_suid_sgid",
    )?;
    require_bool(
        requested.restrict_address_families,
        required.restrict_address_families,
        "restrict_address_families",
    )?;
    if required.memory_max_bytes > 0
        && (requested.memory_max_bytes == 0
            || requested.memory_max_bytes > required.memory_max_bytes)
    {
        bail!("requested memory limit is weaker than capability isolation floor");
    }
    if required.cpu_quota_percent > 0
        && (requested.cpu_quota_percent == 0
            || requested.cpu_quota_percent > required.cpu_quota_percent)
    {
        bail!("requested CPU quota is weaker than capability isolation floor");
    }
    if !required.cgroup_slice.is_empty() && requested.cgroup_slice != required.cgroup_slice {
        bail!("requested cgroup slice differs from capability isolation floor");
    }
    Ok(())
}

fn require_bool(actual: bool, required: bool, field: &str) -> Result<()> {
    if required && !actual {
        bail!("required isolation field {field} was weakened");
    }
    Ok(())
}

#[cfg(test)]
mod tests;
