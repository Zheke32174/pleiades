use std::path::PathBuf;

use pdk_crypto::signed_heartbeat_digest_sha256;
use pdk_protocol::{
    PROTOCOL_VERSION,
    v1::{HeartbeatAckPayload, HeartbeatPayload, SignedHeartbeat, SignedHeartbeatAck},
};
use prost::Message;
use uuid::Uuid;

use crate::{
    heartbeat_read_store::{
        BootEpochActivation, BootEpochActivationError, BootEpochRecord,
        ControllerHeartbeatReadStore,
    },
    heartbeat_store::ControllerHeartbeatStore,
};

fn database_path(label: &str) -> PathBuf {
    std::env::temp_dir()
        .join(format!("pdk-heartbeat-read-{label}-{}", Uuid::new_v4()))
        .join("controller.db")
}

fn heartbeat(boot_id: &str, sequence: u64, version: &str) -> SignedHeartbeat {
    SignedHeartbeat {
        key_id: "node-key-v1".into(),
        payload: Some(HeartbeatPayload {
            protocol_version: PROTOCOL_VERSION,
            domain_id: "domain://test".into(),
            node_id: "node://test/source".into(),
            boot_id: boot_id.into(),
            sequence,
            sent_at_unix_ms: 10,
            agent_version: version.into(),
            node_state: 1,
            health: 1,
            inventory: None,
        }),
        signature_base64: "synthetic-signature".into(),
    }
}

fn acknowledgement(envelope: &SignedHeartbeat, ack_id: &str, accepted: u64) -> SignedHeartbeatAck {
    let payload = envelope.payload.as_ref().expect("heartbeat payload");
    SignedHeartbeatAck {
        key_id: "controller-key-v1".into(),
        payload: Some(HeartbeatAckPayload {
            ack_id: ack_id.into(),
            domain_id: payload.domain_id.clone(),
            controller_id: "controller://test".into(),
            node_id: payload.node_id.clone(),
            boot_id: payload.boot_id.clone(),
            accepted_sequence: payload.sequence,
            accepted_at_unix_ms: accepted,
            suggested_interval_seconds: 5,
            authority_mode: "single-authoritative-controller".into(),
            heartbeat_digest_sha256: signed_heartbeat_digest_sha256(envelope),
        }),
        signature_base64: "synthetic-controller-signature".into(),
    }
}

fn epoch(boot_id: &str, generation: u64, transition_id: &str) -> BootEpochRecord {
    BootEpochRecord {
        node_id: "node://test/source".into(),
        boot_id: boot_id.into(),
        generation,
        transition_id: transition_id.into(),
        activated_at_unix_ms: generation * 100,
    }
}

#[tokio::test]
async fn latest_for_boot_reconstructs_exact_durable_envelope() {
    let path = database_path("latest");
    let writer = ControllerHeartbeatStore::open(&path).await.expect("writer");
    let reader = ControllerHeartbeatReadStore::open(&path)
        .await
        .expect("reader");
    let first = heartbeat("boot/one", 1, "v1");
    let latest = heartbeat("boot/one", 2, "v2");
    writer
        .admit_new(&first, &acknowledgement(&first, "ack/one", 20))
        .await
        .expect("first");
    let latest_ack = acknowledgement(&latest, "ack/two", 30);
    writer
        .admit_new(&latest, &latest_ack)
        .await
        .expect("latest");
    let observed = reader
        .latest_for_boot("node://test/source", "boot/one")
        .await
        .expect("read")
        .expect("observation");
    assert_eq!(observed.sequence, 2);
    assert_eq!(observed.envelope.encode_to_vec(), latest.encode_to_vec());
    assert_eq!(
        observed.acknowledgement.encode_to_vec(),
        latest_ack.encode_to_vec()
    );
    let _ = tokio::fs::remove_dir_all(path.parent().expect("parent")).await;
}

#[tokio::test]
async fn explicit_boot_epoch_prevents_delayed_old_boot_from_becoming_current() {
    let path = database_path("epoch");
    let writer = ControllerHeartbeatStore::open(&path).await.expect("writer");
    let reader = ControllerHeartbeatReadStore::open(&path)
        .await
        .expect("reader");
    let old = heartbeat("boot/old", 1, "old");
    writer
        .admit_new(&old, &acknowledgement(&old, "ack/old", 20))
        .await
        .expect("old");
    assert_eq!(
        reader
            .activate_boot_epoch(&epoch("boot/old", 1, "transition/1"))
            .await
            .expect("activate old"),
        BootEpochActivation::New
    );

    let new = heartbeat("boot/new", 1, "new");
    writer
        .admit_new(&new, &acknowledgement(&new, "ack/new", 30))
        .await
        .expect("new");
    reader
        .activate_boot_epoch(&epoch("boot/new", 2, "transition/2"))
        .await
        .expect("activate new");

    let delayed = heartbeat("boot/old", 2, "delayed-old");
    writer
        .admit_new(&delayed, &acknowledgement(&delayed, "ack/delayed", 40))
        .await
        .expect("delayed old boot remains admissible history");
    let current = reader
        .current_for_node("node://test/source")
        .await
        .expect("current read")
        .expect("current observation");
    assert_eq!(current.epoch.boot_id, "boot/new");
    assert_eq!(current.epoch.generation, 2);
    assert_eq!(current.observation.boot_id, "boot/new");
    assert_eq!(current.observation.sequence, 1);
    let _ = tokio::fs::remove_dir_all(path.parent().expect("parent")).await;
}

#[tokio::test]
async fn boot_epoch_transition_is_idempotent_and_rejects_regression() {
    let path = database_path("retry");
    let writer = ControllerHeartbeatStore::open(&path).await.expect("writer");
    let reader = ControllerHeartbeatReadStore::open(&path)
        .await
        .expect("reader");
    let observed = heartbeat("boot/one", 1, "v1");
    writer
        .admit_new(&observed, &acknowledgement(&observed, "ack/one", 20))
        .await
        .expect("heartbeat");
    let record = epoch("boot/one", 1, "transition/1");
    assert_eq!(
        reader.activate_boot_epoch(&record).await.expect("new"),
        BootEpochActivation::New
    );
    assert_eq!(
        reader.activate_boot_epoch(&record).await.expect("retry"),
        BootEpochActivation::Idempotent
    );
    let regression = epoch("boot/one", 1, "transition/different");
    assert!(matches!(
        reader
            .activate_boot_epoch(&regression)
            .await
            .expect_err("regression"),
        BootEpochActivationError::Regression {
            current_generation: 1
        }
    ));
    let _ = tokio::fs::remove_dir_all(path.parent().expect("parent")).await;
}

#[tokio::test]
async fn boot_epoch_requires_an_accepted_heartbeat() {
    let path = database_path("missing");
    let _writer = ControllerHeartbeatStore::open(&path).await.expect("writer");
    let reader = ControllerHeartbeatReadStore::open(&path)
        .await
        .expect("reader");
    assert!(matches!(
        reader
            .activate_boot_epoch(&epoch("boot/missing", 1, "transition/missing"))
            .await
            .expect_err("missing"),
        BootEpochActivationError::BootNotObserved
    ));
    let _ = tokio::fs::remove_dir_all(path.parent().expect("parent")).await;
}

#[tokio::test]
async fn current_boot_epoch_survives_reader_restart() {
    let path = database_path("restart");
    let writer = ControllerHeartbeatStore::open(&path).await.expect("writer");
    let heartbeat = heartbeat("boot/one", 1, "v1");
    writer
        .admit_new(&heartbeat, &acknowledgement(&heartbeat, "ack/one", 20))
        .await
        .expect("heartbeat");
    {
        let reader = ControllerHeartbeatReadStore::open(&path)
            .await
            .expect("reader");
        reader
            .activate_boot_epoch(&epoch("boot/one", 1, "transition/1"))
            .await
            .expect("activate");
    }
    let reopened = ControllerHeartbeatReadStore::open(&path)
        .await
        .expect("reopen");
    let current = reopened
        .current_for_node("node://test/source")
        .await
        .expect("current")
        .expect("observation");
    assert_eq!(current.epoch.transition_id, "transition/1");
    assert_eq!(current.observation.sequence, 1);
    let _ = tokio::fs::remove_dir_all(path.parent().expect("parent")).await;
}
