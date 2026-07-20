use std::collections::HashMap;

use anyhow::{Context, Result, anyhow, bail};
use pdk_crypto::verify_capability;
use pdk_protocol::v1::{CapabilityGrantPayload, OfflinePolicy, SignedCapabilityGrant};

use super::TrustedControllerKey;
use crate::autonomy::{AutonomyStateMachine, unix_ms};

#[derive(Clone, Debug)]
pub struct ValidatedGrant {
    pub(super) envelope: SignedCapabilityGrant,
    pub(super) payload: CapabilityGrantPayload,
    pub(super) sequence_key: String,
}

impl ValidatedGrant {
    pub fn payload(&self) -> &CapabilityGrantPayload {
        &self.payload
    }

    pub fn signature_base64(&self) -> &str {
        &self.envelope.signature_base64
    }

    #[cfg(test)]
    pub(super) fn sequence_key(&self) -> &str {
        &self.sequence_key
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum GrantInstallOutcome {
    Installed,
    Idempotent,
    Superseded { highest_sequence: u64 },
}

pub(super) fn validate_signed_grant(
    domain_id: &str,
    node_id: &str,
    autonomy: &AutonomyStateMachine,
    max_clock_skew_ms: u64,
    trusted_controllers: &HashMap<String, TrustedControllerKey>,
    envelope: SignedCapabilityGrant,
    authenticated_controller_id: &str,
) -> Result<ValidatedGrant> {
    if !autonomy.allows_new_global_grant() {
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
    if payload.domain_id != domain_id {
        bail!("capability grant belongs to another domain");
    }
    if payload.target_node_id != node_id {
        bail!("capability grant targets another node");
    }
    if payload.issuer_id != authenticated_controller_id {
        bail!("mTLS controller identity does not match signed grant issuer");
    }

    let trusted = trusted_controllers
        .get(&payload.issuer_id)
        .context("grant issuer is not trusted")?;
    if envelope.key_id != trusted.key_id {
        bail!("capability grant key_id is not enrolled");
    }
    verify_capability(&envelope, &trusted.verifying_key)?;
    validate_grant_time(&payload, unix_ms(), max_clock_skew_ms)?;
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

pub(super) fn validate_grant_time(
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
