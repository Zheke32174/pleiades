use std::{collections::HashMap, time::Duration};

use anyhow::Result;
use ed25519_dalek::SigningKey;
use pdk_crypto::{LoadedSigningKey, sign_capability};
use pdk_protocol::{
    PROTOCOL_VERSION,
    v1::{CapabilityAction, CapabilityGrantPayload, OfflinePolicy},
};

use super::*;
use crate::autonomy::unix_ms;

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

async fn validate_and_install(
    enforcer: &PolicyEnforcer,
    envelope: SignedCapabilityGrant,
) -> Result<GrantInstallOutcome> {
    let validated = enforcer.validate_signed_grant(envelope, "controller-1")?;
    enforcer.install_committed_grant(validated).await
}

#[test]
fn validation_produces_an_immutable_candidate_without_cache_access() {
    let (enforcer, key, _) = fixture();
    let validated = enforcer
        .validate_signed_grant(
            signed_grant(
                &key,
                "token-candidate",
                10,
                1,
                OfflinePolicy::BoundedCache,
                CapabilityAction::StatusWorkload,
            ),
            "controller-1",
        )
        .expect("candidate should validate");
    assert_eq!(validated.payload().token_id, "token-candidate");
    assert_eq!(validated.sequence_key(), "controller-1|node-1|workload-1");
    assert!(!validated.signature_base64().is_empty());
}

#[tokio::test]
async fn validated_candidate_is_inactive_until_committed_install() {
    let (enforcer, key, _) = fixture();
    let validated = enforcer
        .validate_signed_grant(
            signed_grant(
                &key,
                "token-candidate",
                10,
                1,
                OfflinePolicy::BoundedCache,
                CapabilityAction::StatusWorkload,
            ),
            "controller-1",
        )
        .expect("candidate should validate");

    assert_eq!(enforcer.cached_count().await, 0);
    enforcer
        .authorize_status("token-candidate", "workload-1")
        .await
        .expect_err("validated candidate must not be active");

    assert_eq!(
        enforcer
            .install_committed_grant(validated)
            .await
            .expect("committed candidate should install"),
        GrantInstallOutcome::Installed
    );
    enforcer
        .authorize_status("token-candidate", "workload-1")
        .await
        .expect("installed candidate should authorize");
}

#[tokio::test]
async fn rejected_validation_mutates_neither_cache_nor_sequence_floor() {
    let (enforcer, key, _) = fixture();
    enforcer
        .validate_signed_grant(
            signed_grant(
                &key,
                "token-invalid",
                10,
                1,
                OfflinePolicy::BoundedCache,
                CapabilityAction::StatusWorkload,
            ),
            "different-controller",
        )
        .expect_err("authenticated issuer mismatch must fail");

    assert_eq!(enforcer.cached_count().await, 0);
    assert_eq!(
        enforcer
            .highest_installed_sequence("controller-1|node-1|workload-1")
            .await,
        None
    );
}

#[tokio::test]
async fn exact_retry_is_idempotent_but_token_collision_is_rejected() {
    let (enforcer, key, _) = fixture();
    let first = signed_grant(
        &key,
        "token-exact",
        11,
        1,
        OfflinePolicy::BoundedCache,
        CapabilityAction::StatusWorkload,
    );
    assert_eq!(
        validate_and_install(&enforcer, first.clone())
            .await
            .expect("first install"),
        GrantInstallOutcome::Installed
    );
    assert_eq!(
        validate_and_install(&enforcer, first)
            .await
            .expect("exact retry"),
        GrantInstallOutcome::Idempotent
    );

    let collision = enforcer
        .validate_signed_grant(
            signed_grant(
                &key,
                "token-exact",
                12,
                1,
                OfflinePolicy::BoundedCache,
                CapabilityAction::StatusWorkload,
            ),
            "controller-1",
        )
        .expect("collision remains cryptographically valid");
    let error = enforcer
        .install_committed_grant(collision)
        .await
        .expect_err("same token with different signed content must fail");
    assert!(error.to_string().contains("token ID collision"));
}

#[tokio::test]
async fn late_lower_sequence_is_superseded_without_activation_rollback() {
    let (enforcer, key, _) = fixture();
    let old = enforcer
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
        .expect("old candidate validates before durable race");
    let new = enforcer
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
        .expect("new candidate validates");

    assert_eq!(
        enforcer
            .install_committed_grant(new)
            .await
            .expect("new candidate installs"),
        GrantInstallOutcome::Installed
    );
    assert_eq!(
        enforcer
            .install_committed_grant(old)
            .await
            .expect("late old candidate is classified"),
        GrantInstallOutcome::Superseded {
            highest_sequence: 20
        }
    );
    assert_eq!(enforcer.cached_count().await, 1);
    enforcer
        .authorize_status("token-old", "workload-1")
        .await
        .expect_err("superseded token must remain inactive");
    enforcer
        .authorize_status("token-new", "workload-1")
        .await
        .expect("newest token remains active");
}

#[tokio::test]
async fn equal_sequence_with_different_token_is_rejected() {
    let (enforcer, key, _) = fixture();
    validate_and_install(
        &enforcer,
        signed_grant(
            &key,
            "token-first",
            30,
            1,
            OfflinePolicy::BoundedCache,
            CapabilityAction::StatusWorkload,
        ),
    )
    .await
    .expect("first token installs");

    let second = enforcer
        .validate_signed_grant(
            signed_grant(
                &key,
                "token-second",
                30,
                1,
                OfflinePolicy::BoundedCache,
                CapabilityAction::StatusWorkload,
            ),
            "controller-1",
        )
        .expect("second token validates");
    let error = enforcer
        .install_committed_grant(second)
        .await
        .expect_err("equal sequence with different token must fail");
    assert!(error.to_string().contains("collides"));
}

#[tokio::test]
async fn removal_does_not_lower_the_installed_sequence_floor() {
    let (enforcer, key, _) = fixture();
    validate_and_install(
        &enforcer,
        signed_grant(
            &key,
            "token-current",
            40,
            1,
            OfflinePolicy::BoundedCache,
            CapabilityAction::StatusWorkload,
        ),
    )
    .await
    .expect("current token installs");
    assert!(enforcer.remove_active_grant("token-current").await);
    assert_eq!(enforcer.cached_count().await, 0);
    assert_eq!(
        enforcer
            .highest_installed_sequence("controller-1|node-1|workload-1")
            .await,
        Some(40)
    );

    let rollback = enforcer
        .validate_signed_grant(
            signed_grant(
                &key,
                "token-rollback",
                39,
                1,
                OfflinePolicy::BoundedCache,
                CapabilityAction::StatusWorkload,
            ),
            "controller-1",
        )
        .expect("rollback candidate remains cryptographically valid");
    assert_eq!(
        enforcer
            .install_committed_grant(rollback)
            .await
            .expect("rollback is classified"),
        GrantInstallOutcome::Superseded {
            highest_sequence: 40
        }
    );
}

#[tokio::test]
async fn subject_validation_does_not_consume_the_durable_budget() {
    let (enforcer, key, _) = fixture();
    validate_and_install(
        &enforcer,
        signed_grant(
            &key,
            "token-budget",
            50,
            1,
            OfflinePolicy::BoundedCache,
            CapabilityAction::StatusWorkload,
        ),
    )
    .await
    .expect("grant should install");

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
        .expect("durable authority state owns use consumption");
}

#[test]
fn offline_policy_matrix_remains_explicit() {
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
