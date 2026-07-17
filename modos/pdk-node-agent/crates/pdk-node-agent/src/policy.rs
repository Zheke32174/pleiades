use std::{collections::HashMap, sync::Arc};

use anyhow::{bail, Context, Result};
use ed25519_dalek::VerifyingKey;
use pdk_crypto::verify_capability;
use pdk_protocol::v1::{
    CapabilityAction, CapabilityGrantPayload, IsolationConstraints,
    SignedCapabilityGrant, WorkloadSpec,
};
use tokio::sync::RwLock;

use crate::{autonomy::{unix_ms, AutonomyStateMachine}, config::TrustedControllerConfig};

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
        }
    }

    pub async fn cache_signed_grant(
        &self,
        envelope: SignedCapabilityGrant,
        authenticated_controller_id: &str,
    ) -> Result<CapabilityGrantPayload> {
        if !self.autonomy.allows_new_global_grant() {
            bail!("new capability grants require Connected state");
        }
        let payload = envelope
            .payload
            .as_ref()
            .context("capability grant payload missing")?
            .clone();
        if payload.protocol_version != pdk_protocol::PROTOCOL_VERSION {
            bail!("unsupported capability protocol version");
        }
        if payload.domain_id != self.domain_id {
            bail!("capability grant belongs to another domain");
        }
        if payload.target_node_id != self.node_id {
            bail!("capability grant targets another node");
        }
        if payload.issuer_id != authenticated_controller_id {
            bail!("mTLS controller identity does not match signed grant issuer");
        }
        let trusted = self
            .trusted_controllers
            .get(&payload.issuer_id)
            .context("grant issuer is not trusted")?;
        if envelope.key_id != trusted.key_id {
            bail!("capability grant key_id is not enrolled");
        }
        verify_capability(&envelope, &trusted.verifying_key)?;
        validate_grant_time(&payload, unix_ms(), self.max_clock_skew_ms)?;
        if payload.actions.is_empty() {
            bail!("capability grant contains no actions");
        }
        if payload.token_id.is_empty()
            || payload.lease_id.is_empty()
            || payload.subject_workload_id.is_empty()
            || payload.nonce.is_empty()
        {
            bail!("capability grant is missing a required identity or nonce");
        }
        let token_id = payload.token_id.clone();
        let mut grants = self.grants.write().await;
        if let Some(existing) = grants.get(&token_id) {
            if existing.envelope.signature_base64 != envelope.signature_base64 {
                bail!("token ID collision with different signed content");
            }
            return Ok(existing.payload.clone());
        }
        grants.insert(
            token_id,
            CachedGrant {
                envelope,
                payload: payload.clone(),
            },
        );
        Ok(payload)
    }

    pub async fn authorize_spawn(
        &self,
        token_id: &str,
        lease_id: &str,
        workload: &WorkloadSpec,
    ) -> Result<Authorization> {
        let grant = self.lookup_valid(token_id, CapabilityAction::SpawnWorkload).await?;
        if grant.lease_id != lease_id {
            bail!("lease ID does not match capability token");
        }
        if grant.subject_workload_id != workload.workload_id {
            bail!("capability token subject does not match workload ID");
        }
        if workload.singleton_destructive && !grant.singleton_destructive {
            bail!("capability does not authorize singleton destructive execution");
        }
        if !self
            .autonomy
            .allows_cached_workload_operation(workload.singleton_destructive)
        {
            bail!("node state {:?} denies workload start", self.autonomy.current());
        }
        enforce_isolation_floor(
            workload.isolation.as_ref(),
            grant.maximum_isolation.as_ref(),
        )?;
        Ok(Authorization {
            token_id: grant.token_id,
            lease_id: grant.lease_id,
            workload_id: workload.workload_id.clone(),
        })
    }

    pub async fn authorize_stop(
        &self,
        token_id: &str,
        workload_id: &str,
    ) -> Result<Authorization> {
        let grant = self.lookup_valid(token_id, CapabilityAction::StopWorkload).await?;
        if grant.subject_workload_id != workload_id {
            bail!("capability token subject does not match workload ID");
        }
        if !self.autonomy.allows_workload_stop() {
            bail!("node state {:?} denies controller-requested workload stop", self.autonomy.current());
        }
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
        if !self.autonomy.allows_status_read() {
            bail!("node is quarantined");
        }
        let grant = self.lookup_valid(token_id, CapabilityAction::StatusWorkload).await?;
        if grant.subject_workload_id != workload_id {
            bail!("capability token subject does not match workload ID");
        }
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

    pub async fn remove_cached_grant(&self, token_id: &str) -> bool {
        self.grants.write().await.remove(token_id).is_some()
    }

    pub async fn cached_count(&self) -> u64 {
        self.grants.read().await.len().try_into().unwrap_or(u64::MAX)
    }

    async fn lookup_valid(
        &self,
        token_id: &str,
        action: CapabilityAction,
    ) -> Result<CapabilityGrantPayload> {
        let cached = self
            .grants
            .read()
            .await
            .get(token_id)
            .cloned()
            .context("capability token is not cached")?;
        validate_grant_time(&cached.payload, unix_ms(), self.max_clock_skew_ms)?;
        if !cached.payload.actions.contains(&(action as i32)) {
            bail!("capability token does not authorize requested action");
        }
        Ok(cached.payload)
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

fn validate_grant_time(
    grant: &CapabilityGrantPayload,
    now_unix_ms: u64,
    max_clock_skew_ms: u64,
) -> Result<()> {
    if grant.not_before_unix_ms > grant.expires_at_unix_ms {
        bail!("capability validity interval is inverted");
    }
    if grant.issued_at_unix_ms > now_unix_ms.saturating_add(max_clock_skew_ms) {
        bail!("capability was issued too far in the future");
    }
    if now_unix_ms.saturating_add(max_clock_skew_ms) < grant.not_before_unix_ms {
        bail!("capability is not yet valid");
    }
    if now_unix_ms >= grant.expires_at_unix_ms {
        bail!("capability has expired");
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
    require_bool(requested.network_denied, required.network_denied, "network_denied")?;
    require_bool(requested.read_only_root, required.read_only_root, "read_only_root")?;
    require_bool(requested.private_tmp, required.private_tmp, "private_tmp")?;
    require_bool(requested.protect_home, required.protect_home, "protect_home")?;
    require_bool(
        requested.no_new_privileges,
        required.no_new_privileges,
        "no_new_privileges",
    )?;
    require_bool(requested.dynamic_user, required.dynamic_user, "dynamic_user")?;
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
