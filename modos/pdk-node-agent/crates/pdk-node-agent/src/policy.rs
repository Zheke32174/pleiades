use std::{collections::HashMap, sync::Arc};

use anyhow::{Context, Result, anyhow, bail};
use ed25519_dalek::VerifyingKey;
use pdk_crypto::verify_capability;
use pdk_protocol::v1::{
    CapabilityAction, CapabilityGrantPayload, IsolationConstraints, NodeState, OfflinePolicy,
    SignedCapabilityGrant, WorkloadSpec,
};
use tokio::sync::RwLock;

use crate::{
    autonomy::{AutonomyStateMachine, unix_ms},
    config::TrustedControllerConfig,
};

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
    highest_sequences: Arc<RwLock<HashMap<String, HighestSequence>>>,
}

#[derive(Clone)]
struct CachedGrant {
    envelope: SignedCapabilityGrant,
    payload: CapabilityGrantPayload,
}

#[derive(Clone)]
struct HighestSequence {
    sequence: u64,
    token_id: String,
    signature_base64: String,
}

#[derive(Clone)]
pub struct ValidatedGrant {
    envelope: SignedCapabilityGrant,
    payload: CapabilityGrantPayload,
    sequence_key: String,
}

impl ValidatedGrant {
    pub fn payload(&self) -> &CapabilityGrantPayload {
        &self.payload
    }

    pub fn signature_base64(&self) -> &str {
        &self.envelope.signature_base64
    }
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
        validate_bounded_fields(&payload)?;
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

        Ok(ValidatedGrant {
            sequence_key: grant_sequence_key(&payload),
            envelope,
            payload,
        })
    }

    pub async fn install_durably_admitted_grant(
        &self,
        candidate: ValidatedGrant,
    ) -> Result<CapabilityGrantPayload> {
        let token_id = candidate.payload.token_id.clone();
        let signature_base64 = candidate.envelope.signature_base64.clone();
        let mut grants = self.grants.write().await;
        if let Some(existing) = grants.get(&token_id) {
            if existing.envelope.signature_base64 != signature_base64 {
                bail!("token ID collision with different signed content");
            }
            return Ok(existing.payload.clone());
        }

        let mut highest_sequences = self.highest_sequences.write().await;
        if let Some(highest) = highest_sequences.get(&candidate.sequence_key) {
            if candidate.payload.grant_sequence < highest.sequence {
                bail!(
                    "capability grant sequence {} is older than active projection sequence {}",
                    candidate.payload.grant_sequence,
                    highest.sequence
                );
            }
            if candidate.payload.grant_sequence == highest.sequence
                && (highest.token_id != token_id || highest.signature_base64 != signature_base64)
            {
                bail!(
                    "capability grant sequence {} collides with another admitted identity",
                    candidate.payload.grant_sequence
                );
            }
        }

        highest_sequences.insert(
            candidate.sequence_key,
            HighestSequence {
                sequence: candidate.payload.grant_sequence,
                token_id: token_id.clone(),
                signature_base64,
            },
        );
        grants.insert(
            token_id,
            CachedGrant {
                envelope: candidate.envelope,
                payload: candidate.payload.clone(),
            },
        );
        Ok(candidate.payload)
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
        validate_grant_time(&cached.payload, unix_ms(), self.max_clock_skew_ms)?;
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

fn validate_bounded_fields(grant: &CapabilityGrantPayload) -> Result<()> {
    if grant.grant_sequence == 0 {
        bail!("capability grant sequence must be nonzero");
    }
    if grant.max_uses == 0 {
        bail!("capability grant max_uses must be nonzero");
    }
    let offline_policy = OfflinePolicy::try_from(grant.offline_policy)
        .map_err(|_| anyhow!("unsupported capability offline policy"))?;
    if offline_policy == OfflinePolicy::Unspecified {
        bail!("capability offline policy must be explicit");
    }
    validate_policy_digest(&grant.policy_digest_sha256)
}

fn validate_policy_digest(value: &str) -> Result<()> {
    let digest = value
        .strip_prefix("sha256:")
        .context("policy digest must use sha256:<lowercase-hex>")?;
    if digest.len() != 64 || !digest.chars().all(|ch| matches!(ch, '0'..='9' | 'a'..='f')) {
        bail!("policy digest must use sha256 followed by 64 lowercase hexadecimal characters");
    }
    Ok(())
}

fn grant_sequence_key(grant: &CapabilityGrantPayload) -> String {
    format!(
        "{}|{}|{}",
        grant.issuer_id, grant.target_node_id, grant.subject_workload_id
    )
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
mod tests {
    use std::{collections::HashMap, time::Duration};

    use ed25519_dalek::SigningKey;
    use pdk_crypto::{LoadedSigningKey, sign_capability};
    use pdk_protocol::{
        PROTOCOL_VERSION,
        v1::{CapabilityAction, CapabilityGrantPayload, OfflinePolicy},
    };

    use super::*;

    const POLICY_DIGEST: &str =
        "sha256:a6dda54861f8897bd1e0a2fb14d072d4733a54e1496bda220c70d24e188e131e";

    fn fixture() -> (PolicyEnforcer, LoadedSigningKey, AutonomyStateMachine) {
        let signing_key = SigningKey::from_bytes(&[7_u8; 32]);
        let loaded = LoadedSigningKey {
            key_id: "controller-key".into(),
            signing_key,
        };
        let autonomy = AutonomyStateMachine::new(Duration::from_secs(30), Duration::from_secs(60));
        autonomy.record_controller_ack(unix_ms());
        let trusted = HashMap::from([(
            "controller-1".into(),
            TrustedControllerKey {
                key_id: loaded.key_id.clone(),
                verifying_key: loaded.signing_key.verifying_key(),
            },
        )]);
        let enforcer = PolicyEnforcer::new("pleiades-lab", "node-1", autonomy.clone(), 5, trusted);
        (enforcer, loaded, autonomy)
    }

    fn signed_grant(
        key: &LoadedSigningKey,
        token_id: &str,
        sequence: u64,
        max_uses: u32,
        offline_policy: OfflinePolicy,
        action: CapabilityAction,
    ) -> SignedCapabilityGrant {
        let now = unix_ms();
        sign_capability(
            CapabilityGrantPayload {
                protocol_version: PROTOCOL_VERSION,
                token_id: token_id.into(),
                domain_id: "pleiades-lab".into(),
                issuer_id: "controller-1".into(),
                subject_workload_id: "workload-1".into(),
                target_node_id: "node-1".into(),
                lease_id: format!("lease-{token_id}"),
                actions: vec![action as i32],
                issued_at_unix_ms: now,
                not_before_unix_ms: now.saturating_sub(1_000),
                expires_at_unix_ms: now.saturating_add(60_000),
                policy_version: "epoch2-local-policy-v1".into(),
                nonce: format!("nonce-{token_id}"),
                maximum_isolation: None,
                singleton_destructive: false,
                grant_sequence: sequence,
                max_uses,
                offline_policy: offline_policy as i32,
                policy_digest_sha256: POLICY_DIGEST.into(),
            },
            key,
        )
    }

    #[tokio::test]
    async fn validation_is_side_effect_free_until_durable_installation() {
        let (enforcer, key, _) = fixture();
        let candidate = enforcer
            .validate_signed_grant(
                signed_grant(
                    &key,
                    "token-candidate",
                    20,
                    1,
                    OfflinePolicy::BoundedCache,
                    CapabilityAction::StatusWorkload,
                ),
                "controller-1",
            )
            .expect("candidate should pass deterministic validation");

        assert_eq!(enforcer.cached_count().await, 0);
        enforcer
            .authorize_status("token-candidate", "workload-1")
            .await
            .expect_err("validated but uncommitted candidate must not become active");

        enforcer
            .install_durably_admitted_grant(candidate)
            .await
            .expect("durably admitted candidate should become active");
        assert_eq!(enforcer.cached_count().await, 1);
        enforcer
            .authorize_status("token-candidate", "workload-1")
            .await
            .expect("installed grant should authorize policy checks");
    }

    #[tokio::test]
    async fn active_projection_rejects_rollback_and_same_sequence_collision() {
        let (enforcer, key, _) = fixture();
        let newest = enforcer
            .validate_signed_grant(
                signed_grant(
                    &key,
                    "token-new",
                    20,
                    1,
                    OfflinePolicy::BoundedCache,
                    CapabilityAction::StatusWorkload,
                ),
                "controller-1",
            )
            .expect("new grant should validate");
        enforcer
            .install_durably_admitted_grant(newest)
            .await
            .expect("new grant should install");

        let older = enforcer
            .validate_signed_grant(
                signed_grant(
                    &key,
                    "token-old",
                    19,
                    1,
                    OfflinePolicy::BoundedCache,
                    CapabilityAction::StatusWorkload,
                ),
                "controller-1",
            )
            .expect("sequence continuity belongs to durable admission, not validation");
        let error = enforcer
            .install_durably_admitted_grant(older)
            .await
            .expect_err("older durable projection must be rejected defensively");
        assert!(error.to_string().contains("older than active projection"));

        let collision = enforcer
            .validate_signed_grant(
                signed_grant(
                    &key,
                    "token-collision",
                    20,
                    1,
                    OfflinePolicy::BoundedCache,
                    CapabilityAction::StatusWorkload,
                ),
                "controller-1",
            )
            .expect("same-sequence candidate should validate cryptographically");
        let error = enforcer
            .install_durably_admitted_grant(collision)
            .await
            .expect_err("same sequence with another identity must be rejected");
        assert!(error.to_string().contains("collides"));
    }

    #[tokio::test]
    async fn exact_install_retry_is_idempotent() {
        let (enforcer, key, _) = fixture();
        let envelope = signed_grant(
            &key,
            "token-retry",
            21,
            1,
            OfflinePolicy::BoundedCache,
            CapabilityAction::StatusWorkload,
        );
        let first = enforcer
            .validate_signed_grant(envelope.clone(), "controller-1")
            .expect("first candidate should validate");
        let second = enforcer
            .validate_signed_grant(envelope, "controller-1")
            .expect("retry candidate should validate without cache mutation");
        enforcer
            .install_durably_admitted_grant(first)
            .await
            .expect("first install should succeed");
        enforcer
            .install_durably_admitted_grant(second)
            .await
            .expect("exact retry should be idempotent");
        assert_eq!(enforcer.cached_count().await, 1);
    }

    #[tokio::test]
    async fn subject_validation_does_not_consume_the_durable_budget() {
        let (enforcer, key, _) = fixture();
        let candidate = enforcer
            .validate_signed_grant(
                signed_grant(
                    &key,
                    "token-budget",
                    30,
                    1,
                    OfflinePolicy::BoundedCache,
                    CapabilityAction::StatusWorkload,
                ),
                "controller-1",
            )
            .expect("grant should validate");
        enforcer
            .install_durably_admitted_grant(candidate)
            .await
            .expect("durably admitted grant should install");

        enforcer
            .authorize_status("token-budget", "wrong-workload")
            .await
            .expect_err("wrong subject must fail");
        enforcer
            .authorize_status("token-budget", "workload-1")
            .await
            .expect("valid subject should pass policy validation");
        enforcer
            .authorize_status("token-budget", "workload-1")
            .await
            .expect("durable authority state, not the policy cache, owns use consumption");
    }

    #[test]
    fn offline_policy_matrix_is_explicit() {
        let key = LoadedSigningKey {
            key_id: "unused".into(),
            signing_key: SigningKey::from_bytes(&[9_u8; 32]),
        };
        let bounded = signed_grant(
            &key,
            "bounded",
            1,
            1,
            OfflinePolicy::BoundedCache,
            CapabilityAction::SpawnWorkload,
        )
        .payload
        .expect("payload");
        assert!(
            enforce_offline_policy(
                &bounded,
                NodeState::DegradedAutonomous,
                CapabilityAction::SpawnWorkload,
            )
            .is_ok()
        );

        let denied = signed_grant(
            &key,
            "denied",
            2,
            1,
            OfflinePolicy::Deny,
            CapabilityAction::StatusWorkload,
        )
        .payload
        .expect("payload");
        assert!(
            enforce_offline_policy(
                &denied,
                NodeState::DegradedAutonomous,
                CapabilityAction::StatusWorkload,
            )
            .is_err()
        );

        let finish = signed_grant(
            &key,
            "finish",
            3,
            1,
            OfflinePolicy::FinishCurrent,
            CapabilityAction::StopWorkload,
        )
        .payload
        .expect("payload");
        assert!(
            enforce_offline_policy(
                &finish,
                NodeState::ReadOnlySafe,
                CapabilityAction::StopWorkload,
            )
            .is_ok()
        );
        assert!(
            enforce_offline_policy(
                &finish,
                NodeState::ReadOnlySafe,
                CapabilityAction::SpawnWorkload,
            )
            .is_err()
        );
    }
}
