use std::{fs, path::Path};

use anyhow::{anyhow, bail, Context, Result};
use base64::{engine::general_purpose::STANDARD, Engine as _};
use ed25519_dalek::{Signature, Signer, SigningKey, VerifyingKey};
use prost::Message;
use rand_core::OsRng;
use serde::{Deserialize, Serialize};

use pdk_protocol::{
    v1::{
        CapabilityGrantPayload, DomainEventPayload, EventAckPayload, HeartbeatAckPayload,
        HeartbeatPayload, SignedCapabilityGrant, SignedDomainEvent, SignedEventAck,
        SignedHeartbeat, SignedHeartbeatAck,
    },
    CAPABILITY_SIGNATURE_CONTEXT, DOMAIN_EVENT_SIGNATURE_CONTEXT,
    EVENT_ACK_SIGNATURE_CONTEXT, HEARTBEAT_ACK_SIGNATURE_CONTEXT,
    HEARTBEAT_SIGNATURE_CONTEXT,
};

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct KeyFile {
    pub key_id: String,
    pub secret_key_base64: String,
    pub public_key_base64: String,
}

#[derive(Clone)]
pub struct LoadedSigningKey {
    pub key_id: String,
    pub signing_key: SigningKey,
}

pub fn generate_key_file(key_id: impl Into<String>) -> KeyFile {
    let signing_key = SigningKey::generate(&mut OsRng);
    let verifying_key = signing_key.verifying_key();
    KeyFile {
        key_id: key_id.into(),
        secret_key_base64: STANDARD.encode(signing_key.to_bytes()),
        public_key_base64: STANDARD.encode(verifying_key.to_bytes()),
    }
}

pub fn write_key_file(path: &Path, key_file: &KeyFile) -> Result<()> {
    if path.exists() {
        bail!("refusing to overwrite existing key file: {}", path.display());
    }
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)
            .with_context(|| format!("creating key directory {}", parent.display()))?;
    }
    fs::write(path, serde_json::to_vec_pretty(key_file)?)
        .with_context(|| format!("writing {}", path.display()))?;
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        fs::set_permissions(path, fs::Permissions::from_mode(0o600))?;
    }
    Ok(())
}

pub fn load_signing_key(path: &Path) -> Result<LoadedSigningKey> {
    enforce_private_file_permissions(path)?;
    let raw = fs::read(path).with_context(|| format!("reading key file {}", path.display()))?;
    let file: KeyFile = serde_json::from_slice(&raw).context("parsing Ed25519 key file")?;
    let secret = decode_fixed::<32>(&file.secret_key_base64, "secret key")?;
    let signing_key = SigningKey::from_bytes(&secret);
    let derived = STANDARD.encode(signing_key.verifying_key().to_bytes());
    if derived != file.public_key_base64 {
        bail!("public key does not match secret key in {}", path.display());
    }
    Ok(LoadedSigningKey {
        key_id: file.key_id,
        signing_key,
    })
}

pub fn decode_verifying_key(encoded: &str) -> Result<VerifyingKey> {
    let bytes = decode_fixed::<32>(encoded, "public key")?;
    VerifyingKey::from_bytes(&bytes).map_err(|error| anyhow!("invalid Ed25519 public key: {error}"))
}

pub fn sign_heartbeat(payload: HeartbeatPayload, key: &LoadedSigningKey) -> SignedHeartbeat {
    SignedHeartbeat {
        key_id: key.key_id.clone(),
        signature_base64: sign_message(HEARTBEAT_SIGNATURE_CONTEXT, &payload, key),
        payload: Some(payload),
    }
}

pub fn verify_heartbeat(envelope: &SignedHeartbeat, key: &VerifyingKey) -> Result<()> {
    verify_message(
        HEARTBEAT_SIGNATURE_CONTEXT,
        envelope.payload.as_ref().context("heartbeat payload missing")?,
        &envelope.signature_base64,
        key,
    )
}

pub fn sign_heartbeat_ack(
    payload: HeartbeatAckPayload,
    key: &LoadedSigningKey,
) -> SignedHeartbeatAck {
    SignedHeartbeatAck {
        key_id: key.key_id.clone(),
        signature_base64: sign_message(HEARTBEAT_ACK_SIGNATURE_CONTEXT, &payload, key),
        payload: Some(payload),
    }
}

pub fn verify_heartbeat_ack(envelope: &SignedHeartbeatAck, key: &VerifyingKey) -> Result<()> {
    verify_message(
        HEARTBEAT_ACK_SIGNATURE_CONTEXT,
        envelope.payload.as_ref().context("heartbeat ACK payload missing")?,
        &envelope.signature_base64,
        key,
    )
}

pub fn sign_capability(
    payload: CapabilityGrantPayload,
    key: &LoadedSigningKey,
) -> SignedCapabilityGrant {
    SignedCapabilityGrant {
        key_id: key.key_id.clone(),
        signature_base64: sign_message(CAPABILITY_SIGNATURE_CONTEXT, &payload, key),
        payload: Some(payload),
    }
}

pub fn verify_capability(envelope: &SignedCapabilityGrant, key: &VerifyingKey) -> Result<()> {
    verify_message(
        CAPABILITY_SIGNATURE_CONTEXT,
        envelope.payload.as_ref().context("capability payload missing")?,
        &envelope.signature_base64,
        key,
    )
}

pub fn sign_domain_event(payload: DomainEventPayload, key: &LoadedSigningKey) -> SignedDomainEvent {
    SignedDomainEvent {
        key_id: key.key_id.clone(),
        signature_base64: sign_message(DOMAIN_EVENT_SIGNATURE_CONTEXT, &payload, key),
        payload: Some(payload),
    }
}

pub fn verify_domain_event(envelope: &SignedDomainEvent, key: &VerifyingKey) -> Result<()> {
    verify_message(
        DOMAIN_EVENT_SIGNATURE_CONTEXT,
        envelope.payload.as_ref().context("domain event payload missing")?,
        &envelope.signature_base64,
        key,
    )
}

pub fn sign_event_ack(payload: EventAckPayload, key: &LoadedSigningKey) -> SignedEventAck {
    SignedEventAck {
        key_id: key.key_id.clone(),
        signature_base64: sign_message(EVENT_ACK_SIGNATURE_CONTEXT, &payload, key),
        payload: Some(payload),
    }
}

pub fn verify_event_ack(envelope: &SignedEventAck, key: &VerifyingKey) -> Result<()> {
    verify_message(
        EVENT_ACK_SIGNATURE_CONTEXT,
        envelope.payload.as_ref().context("event ACK payload missing")?,
        &envelope.signature_base64,
        key,
    )
}

fn sign_message<M: Message>(context: &[u8], payload: &M, key: &LoadedSigningKey) -> String {
    let bytes = signing_bytes(context, payload);
    STANDARD.encode(key.signing_key.sign(&bytes).to_bytes())
}

fn verify_message<M: Message>(
    context: &[u8],
    payload: &M,
    signature_base64: &str,
    key: &VerifyingKey,
) -> Result<()> {
    let signature = Signature::from_bytes(&decode_fixed::<64>(signature_base64, "signature")?);
    key.verify_strict(&signing_bytes(context, payload), &signature)
        .map_err(|error| anyhow!("signature verification failed: {error}"))
}

fn signing_bytes<M: Message>(context: &[u8], payload: &M) -> Vec<u8> {
    let encoded = payload.encode_to_vec();
    let mut bytes = Vec::with_capacity(context.len() + encoded.len());
    bytes.extend_from_slice(context);
    bytes.extend_from_slice(&encoded);
    bytes
}

fn decode_fixed<const N: usize>(encoded: &str, label: &str) -> Result<[u8; N]> {
    let bytes = STANDARD.decode(encoded).with_context(|| format!("decoding {label}"))?;
    bytes
        .try_into()
        .map_err(|value: Vec<u8>| anyhow!("{label} must be {N} bytes, got {}", value.len()))
}

fn enforce_private_file_permissions(path: &Path) -> Result<()> {
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        let mode = fs::metadata(path)
            .with_context(|| format!("stat {}", path.display()))?
            .permissions()
            .mode()
            & 0o777;
        if mode & 0o077 != 0 {
            bail!(
                "private key {} is too permissive ({mode:o}); require 0600 or stricter",
                path.display()
            );
        }
    }
    Ok(())
}
