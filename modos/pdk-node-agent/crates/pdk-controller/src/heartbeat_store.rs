use std::{fmt, path::Path};

use anyhow::{Context, anyhow};
use pdk_crypto::signed_heartbeat_digest_sha256;
use pdk_protocol::v1::{SignedHeartbeat, SignedHeartbeatAck};
use prost::Message;
use sqlx::{Row, SqlitePool, sqlite::SqlitePoolOptions};

#[derive(Clone)]
pub struct ControllerHeartbeatStore {
    pool: SqlitePool,
}

#[derive(Clone, Debug)]
pub enum HeartbeatAdmission {
    New(SignedHeartbeatAck),
    Idempotent(SignedHeartbeatAck),
}

impl HeartbeatAdmission {
    pub fn disposition(&self) -> &'static str {
        match self {
            Self::New(_) => "new",
            Self::Idempotent(_) => "idempotent",
        }
    }

    pub fn into_ack(self) -> SignedHeartbeatAck {
        match self {
            Self::New(ack) | Self::Idempotent(ack) => ack,
        }
    }
}

#[derive(Debug)]
pub enum HeartbeatAdmissionError {
    Collision,
    Replay { highest_sequence: u64 },
    Storage(anyhow::Error),
}

impl fmt::Display for HeartbeatAdmissionError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Collision => {
                formatter.write_str("heartbeat sequence collides with different signed content")
            }
            Self::Replay { highest_sequence } => write!(
                formatter,
                "heartbeat sequence is not newer than durable floor {highest_sequence}"
            ),
            Self::Storage(error) => {
                write!(formatter, "heartbeat admission storage failed: {error:#}")
            }
        }
    }
}

impl std::error::Error for HeartbeatAdmissionError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            Self::Storage(error) => Some(error.as_ref()),
            Self::Collision | Self::Replay { .. } => None,
        }
    }
}

impl ControllerHeartbeatStore {
    pub async fn open(path: &Path) -> anyhow::Result<Self> {
        if let Ok(metadata) = tokio::fs::symlink_metadata(path).await {
            anyhow::ensure!(
                !metadata.file_type().is_symlink(),
                "refusing symlink controller state database {}",
                path.display()
            );
            anyhow::ensure!(
                metadata.is_file(),
                "controller state database is not a regular file: {}",
                path.display()
            );
        }
        if let Some(parent) = path.parent() {
            tokio::fs::create_dir_all(parent).await.with_context(|| {
                format!(
                    "creating controller state database directory {}",
                    parent.display()
                )
            })?;
        }
        let url = format!("sqlite://{}?mode=rwc", path.display());
        let pool = SqlitePoolOptions::new()
            .max_connections(1)
            .connect(&url)
            .await
            .with_context(|| format!("opening controller state database {}", path.display()))?;
        sqlx::query("PRAGMA journal_mode = WAL")
            .execute(&pool)
            .await
            .context("enabling controller heartbeat SQLite WAL mode")?;
        sqlx::query("PRAGMA synchronous = FULL")
            .execute(&pool)
            .await
            .context("setting controller heartbeat SQLite synchronous=FULL")?;
        sqlx::query("PRAGMA busy_timeout = 5000")
            .execute(&pool)
            .await
            .context("setting controller heartbeat SQLite busy timeout")?;
        sqlx::query(
            r#"
            CREATE TABLE IF NOT EXISTS controller_heartbeat_write_fence (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                generation INTEGER NOT NULL
            )
            "#,
        )
        .execute(&pool)
        .await
        .context("creating controller heartbeat write fence")?;
        sqlx::query(
            "INSERT OR IGNORE INTO controller_heartbeat_write_fence (id, generation) VALUES (1, 0)",
        )
        .execute(&pool)
        .await
        .context("initializing controller heartbeat write fence")?;
        sqlx::query(
            r#"
            CREATE TABLE IF NOT EXISTS accepted_heartbeat (
                node_id TEXT NOT NULL,
                boot_id TEXT NOT NULL,
                sequence INTEGER NOT NULL,
                key_id TEXT NOT NULL,
                heartbeat_digest_sha256 TEXT NOT NULL,
                envelope BLOB NOT NULL,
                accepted_at_unix_ms INTEGER NOT NULL,
                acknowledgement BLOB NOT NULL,
                PRIMARY KEY (node_id, boot_id, sequence),
                CHECK (sequence > 0),
                CHECK (length(node_id) > 0),
                CHECK (length(boot_id) > 0),
                CHECK (heartbeat_digest_sha256 GLOB 'sha256:[0-9a-f]*'),
                CHECK (length(heartbeat_digest_sha256) = 71)
            )
            "#,
        )
        .execute(&pool)
        .await
        .context("creating durable accepted heartbeat table")?;
        sqlx::query(
            r#"
            CREATE TABLE IF NOT EXISTS heartbeat_stream_floor (
                node_id TEXT NOT NULL,
                boot_id TEXT NOT NULL,
                highest_sequence INTEGER NOT NULL,
                latest_heartbeat_digest_sha256 TEXT NOT NULL,
                latest_accepted_at_unix_ms INTEGER NOT NULL,
                PRIMARY KEY (node_id, boot_id),
                CHECK (highest_sequence > 0)
            )
            "#,
        )
        .execute(&pool)
        .await
        .context("creating durable heartbeat stream floor")?;
        Ok(Self { pool })
    }

    pub async fn retry_ack(
        &self,
        envelope: &SignedHeartbeat,
    ) -> Result<Option<SignedHeartbeatAck>, HeartbeatAdmissionError> {
        self.retry_ack_inner(envelope)
            .await
            .map_err(|error| match error.downcast_ref::<HeartbeatCollision>() {
                Some(_) => HeartbeatAdmissionError::Collision,
                None => HeartbeatAdmissionError::Storage(error),
            })
    }

    async fn retry_ack_inner(
        &self,
        envelope: &SignedHeartbeat,
    ) -> anyhow::Result<Option<SignedHeartbeatAck>> {
        let heartbeat = envelope
            .payload
            .as_ref()
            .context("signed heartbeat payload missing during retry lookup")?;
        let digest = signed_heartbeat_digest_sha256(envelope);
        let envelope_bytes = envelope.encode_to_vec();
        let row = sqlx::query(
            r#"
            SELECT heartbeat_digest_sha256, envelope, acknowledgement
            FROM accepted_heartbeat
            WHERE node_id = ? AND boot_id = ? AND sequence = ?
            "#,
        )
        .bind(&heartbeat.node_id)
        .bind(&heartbeat.boot_id)
        .bind(as_i64(heartbeat.sequence)?)
        .fetch_optional(&self.pool)
        .await
        .context("checking durable heartbeat retry identity")?;
        let Some(row) = row else {
            return Ok(None);
        };
        let existing_digest: String = row.try_get("heartbeat_digest_sha256")?;
        let existing_envelope: Vec<u8> = row.try_get("envelope")?;
        if existing_digest != digest || existing_envelope != envelope_bytes {
            return Err(anyhow::Error::new(HeartbeatCollision));
        }
        let acknowledgement: Vec<u8> = row.try_get("acknowledgement")?;
        Ok(Some(
            SignedHeartbeatAck::decode(acknowledgement.as_slice())
                .context("decoding durable heartbeat acknowledgement")?,
        ))
    }

    pub async fn admit_new(
        &self,
        envelope: &SignedHeartbeat,
        candidate_ack: &SignedHeartbeatAck,
    ) -> Result<HeartbeatAdmission, HeartbeatAdmissionError> {
        self.admit_new_inner(envelope, candidate_ack)
            .await
            .map_err(|error| {
                if error.downcast_ref::<HeartbeatCollision>().is_some() {
                    HeartbeatAdmissionError::Collision
                } else if let Some(replay) = error.downcast_ref::<HeartbeatReplay>() {
                    HeartbeatAdmissionError::Replay {
                        highest_sequence: replay.highest_sequence,
                    }
                } else {
                    HeartbeatAdmissionError::Storage(error)
                }
            })
    }

    async fn admit_new_inner(
        &self,
        envelope: &SignedHeartbeat,
        candidate_ack: &SignedHeartbeatAck,
    ) -> anyhow::Result<HeartbeatAdmission> {
        let heartbeat = envelope
            .payload
            .as_ref()
            .context("signed heartbeat payload missing during durable admission")?;
        let ack = candidate_ack
            .payload
            .as_ref()
            .context("signed heartbeat acknowledgement payload missing")?;
        let digest = signed_heartbeat_digest_sha256(envelope);
        anyhow::ensure!(ack.node_id == heartbeat.node_id, "heartbeat ACK node mismatch");
        anyhow::ensure!(ack.boot_id == heartbeat.boot_id, "heartbeat ACK boot mismatch");
        anyhow::ensure!(
            ack.accepted_sequence == heartbeat.sequence,
            "heartbeat ACK sequence mismatch"
        );
        anyhow::ensure!(
            ack.heartbeat_digest_sha256 == digest,
            "heartbeat ACK digest mismatch"
        );

        let envelope_bytes = envelope.encode_to_vec();
        let acknowledgement_bytes = candidate_ack.encode_to_vec();
        let mut transaction = self
            .pool
            .begin()
            .await
            .context("starting durable heartbeat admission transaction")?;
        sqlx::query(
            "UPDATE controller_heartbeat_write_fence SET generation = generation + 1 WHERE id = 1",
        )
        .execute(&mut *transaction)
        .await
        .context("acquiring durable heartbeat write fence")?;

        if let Some(row) = sqlx::query(
            r#"
            SELECT heartbeat_digest_sha256, envelope, acknowledgement
            FROM accepted_heartbeat
            WHERE node_id = ? AND boot_id = ? AND sequence = ?
            "#,
        )
        .bind(&heartbeat.node_id)
        .bind(&heartbeat.boot_id)
        .bind(as_i64(heartbeat.sequence)?)
        .fetch_optional(&mut *transaction)
        .await
        .context("checking durable heartbeat identity")?
        {
            let existing_digest: String = row.try_get("heartbeat_digest_sha256")?;
            let existing_envelope: Vec<u8> = row.try_get("envelope")?;
            if existing_digest != digest || existing_envelope != envelope_bytes {
                return Err(anyhow::Error::new(HeartbeatCollision));
            }
            let acknowledgement: Vec<u8> = row.try_get("acknowledgement")?;
            let acknowledgement = SignedHeartbeatAck::decode(acknowledgement.as_slice())
                .context("decoding durable heartbeat acknowledgement")?;
            transaction
                .commit()
                .await
                .context("committing idempotent heartbeat admission")?;
            return Ok(HeartbeatAdmission::Idempotent(acknowledgement));
        }

        if let Some(row) = sqlx::query(
            "SELECT highest_sequence FROM heartbeat_stream_floor WHERE node_id = ? AND boot_id = ?",
        )
        .bind(&heartbeat.node_id)
        .bind(&heartbeat.boot_id)
        .fetch_optional(&mut *transaction)
        .await
        .context("reading durable heartbeat sequence floor")?
        {
            let highest: i64 = row.try_get("highest_sequence")?;
            if as_i64(heartbeat.sequence)? <= highest {
                return Err(anyhow::Error::new(HeartbeatReplay {
                    highest_sequence: u64::try_from(highest).unwrap_or(u64::MAX),
                }));
            }
        }

        sqlx::query(
            r#"
            INSERT INTO accepted_heartbeat
                (node_id, boot_id, sequence, key_id, heartbeat_digest_sha256,
                 envelope, accepted_at_unix_ms, acknowledgement)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            "#,
        )
        .bind(&heartbeat.node_id)
        .bind(&heartbeat.boot_id)
        .bind(as_i64(heartbeat.sequence)?)
        .bind(&envelope.key_id)
        .bind(&digest)
        .bind(&envelope_bytes)
        .bind(as_i64(ack.accepted_at_unix_ms)?)
        .bind(&acknowledgement_bytes)
        .execute(&mut *transaction)
        .await
        .context("persisting signed heartbeat and acknowledgement")?;
        sqlx::query(
            r#"
            INSERT INTO heartbeat_stream_floor
                (node_id, boot_id, highest_sequence, latest_heartbeat_digest_sha256,
                 latest_accepted_at_unix_ms)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(node_id, boot_id) DO UPDATE SET
                highest_sequence = excluded.highest_sequence,
                latest_heartbeat_digest_sha256 = excluded.latest_heartbeat_digest_sha256,
                latest_accepted_at_unix_ms = excluded.latest_accepted_at_unix_ms
            WHERE excluded.highest_sequence > heartbeat_stream_floor.highest_sequence
            "#,
        )
        .bind(&heartbeat.node_id)
        .bind(&heartbeat.boot_id)
        .bind(as_i64(heartbeat.sequence)?)
        .bind(&digest)
        .bind(as_i64(ack.accepted_at_unix_ms)?)
        .execute(&mut *transaction)
        .await
        .context("advancing durable heartbeat sequence floor")?;
        transaction
            .commit()
            .await
            .context("committing heartbeat and acknowledgement")?;
        Ok(HeartbeatAdmission::New(candidate_ack.clone()))
    }

    #[cfg(test)]
    async fn heartbeat_count(&self) -> anyhow::Result<i64> {
        sqlx::query_scalar("SELECT COUNT(*) FROM accepted_heartbeat")
            .fetch_one(&self.pool)
            .await
            .context("counting durable accepted heartbeats")
    }
}

#[derive(Debug)]
struct HeartbeatCollision;

impl fmt::Display for HeartbeatCollision {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter.write_str("heartbeat identity collision")
    }
}

impl std::error::Error for HeartbeatCollision {}

#[derive(Debug)]
struct HeartbeatReplay {
    highest_sequence: u64,
}

impl fmt::Display for HeartbeatReplay {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(
            formatter,
            "heartbeat is not newer than sequence {}",
            self.highest_sequence
        )
    }
}

impl std::error::Error for HeartbeatReplay {}

fn as_i64(value: u64) -> anyhow::Result<i64> {
    i64::try_from(value).map_err(|_| anyhow!("value exceeds SQLite INTEGER range: {value}"))
}

#[cfg(test)]
mod tests {
    use std::{path::PathBuf, sync::Arc};

    use pdk_crypto::signed_heartbeat_digest_sha256;
    use pdk_protocol::{
        PROTOCOL_VERSION,
        v1::{HeartbeatAckPayload, HeartbeatPayload, SignedHeartbeat, SignedHeartbeatAck},
    };
    use prost::Message;
    use uuid::Uuid;

    use super::{
        ControllerHeartbeatStore, HeartbeatAdmission, HeartbeatAdmissionError,
    };

    fn database_path(label: &str) -> PathBuf {
        std::env::temp_dir()
            .join(format!("pdk-heartbeat-{label}-{}", Uuid::new_v4()))
            .join("controller.db")
    }

    fn heartbeat(sequence: u64, agent_version: &str) -> SignedHeartbeat {
        SignedHeartbeat {
            key_id: "node-key-v1".into(),
            payload: Some(HeartbeatPayload {
                protocol_version: PROTOCOL_VERSION,
                domain_id: "domain://test".into(),
                node_id: "node://test/source".into(),
                boot_id: "boot/test".into(),
                sequence,
                sent_at_unix_ms: 10,
                agent_version: agent_version.into(),
                node_state: 1,
                health: 1,
                inventory: None,
            }),
            signature_base64: "synthetic-signature".into(),
        }
    }

    fn acknowledgement(
        envelope: &SignedHeartbeat,
        ack_id: &str,
        accepted_at_unix_ms: u64,
    ) -> SignedHeartbeatAck {
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
                accepted_at_unix_ms,
                suggested_interval_seconds: 5,
                authority_mode: "single-authoritative-controller".into(),
                heartbeat_digest_sha256: signed_heartbeat_digest_sha256(envelope),
            }),
            signature_base64: "synthetic-controller-signature".into(),
        }
    }

    #[tokio::test]
    async fn exact_retry_returns_original_acknowledgement() {
        let path = database_path("retry");
        let store = ControllerHeartbeatStore::open(&path).await.expect("open store");
        let heartbeat = heartbeat(1, "v1");
        let original = acknowledgement(&heartbeat, "ack/original", 20);
        store
            .admit_new(&heartbeat, &original)
            .await
            .expect("first admission");
        let retry = store
            .retry_ack(&heartbeat)
            .await
            .expect("retry lookup")
            .expect("durable retry ACK");
        assert_eq!(retry.encode_to_vec(), original.encode_to_vec());
        assert_eq!(store.heartbeat_count().await.expect("count"), 1);
        let _ = tokio::fs::remove_dir_all(path.parent().expect("parent")).await;
    }

    #[tokio::test]
    async fn same_sequence_with_different_content_is_collision() {
        let path = database_path("collision");
        let store = ControllerHeartbeatStore::open(&path).await.expect("open store");
        let first = heartbeat(1, "v1");
        let altered = heartbeat(1, "v2");
        store
            .admit_new(&first, &acknowledgement(&first, "ack/first", 20))
            .await
            .expect("first admission");
        let error = store
            .retry_ack(&altered)
            .await
            .expect_err("collision must fail");
        assert!(matches!(error, HeartbeatAdmissionError::Collision));
        let _ = tokio::fs::remove_dir_all(path.parent().expect("parent")).await;
    }

    #[tokio::test]
    async fn rollback_is_rejected_after_reopen() {
        let path = database_path("rollback");
        {
            let store = ControllerHeartbeatStore::open(&path).await.expect("open store");
            let latest = heartbeat(3, "v3");
            store
                .admit_new(&latest, &acknowledgement(&latest, "ack/latest", 30))
                .await
                .expect("latest admission");
        }
        let reopened = ControllerHeartbeatStore::open(&path)
            .await
            .expect("reopen store");
        let older = heartbeat(2, "v2");
        let error = reopened
            .admit_new(&older, &acknowledgement(&older, "ack/older", 40))
            .await
            .expect_err("rollback must fail");
        assert!(matches!(
            error,
            HeartbeatAdmissionError::Replay {
                highest_sequence: 3
            }
        ));
        let _ = tokio::fs::remove_dir_all(path.parent().expect("parent")).await;
    }

    #[tokio::test]
    async fn concurrent_exact_submissions_commit_one_identity() {
        let path = database_path("concurrent");
        let store = Arc::new(
            ControllerHeartbeatStore::open(&path)
                .await
                .expect("open store"),
        );
        let heartbeat = Arc::new(heartbeat(1, "v1"));
        let ack = Arc::new(acknowledgement(&heartbeat, "ack/concurrent", 20));
        let first_store = Arc::clone(&store);
        let first_heartbeat = Arc::clone(&heartbeat);
        let first_ack = Arc::clone(&ack);
        let second_store = Arc::clone(&store);
        let second_heartbeat = Arc::clone(&heartbeat);
        let second_ack = Arc::clone(&ack);
        let (first, second) = tokio::join!(
            async move { first_store.admit_new(&first_heartbeat, &first_ack).await },
            async move { second_store.admit_new(&second_heartbeat, &second_ack).await }
        );
        let first = first.expect("first admission");
        let second = second.expect("second admission");
        assert!(matches!(first, HeartbeatAdmission::New(_)));
        assert!(matches!(second, HeartbeatAdmission::Idempotent(_)));
        assert_eq!(store.heartbeat_count().await.expect("count"), 1);
        let _ = tokio::fs::remove_dir_all(path.parent().expect("parent")).await;
    }

    #[tokio::test]
    async fn failed_insert_commits_no_heartbeat() {
        let path = database_path("failure");
        let store = ControllerHeartbeatStore::open(&path).await.expect("open store");
        sqlx::query(
            r#"
            CREATE TRIGGER reject_heartbeat_insert
            BEFORE INSERT ON accepted_heartbeat
            BEGIN
                SELECT RAISE(ABORT, 'forced heartbeat insert failure');
            END
            "#,
        )
        .execute(&store.pool)
        .await
        .expect("create trigger");
        let heartbeat = heartbeat(1, "v1");
        let error = store
            .admit_new(&heartbeat, &acknowledgement(&heartbeat, "ack/failure", 20))
            .await
            .expect_err("forced failure");
        assert!(matches!(error, HeartbeatAdmissionError::Storage(_)));
        assert_eq!(store.heartbeat_count().await.expect("count"), 0);
        let _ = tokio::fs::remove_dir_all(path.parent().expect("parent")).await;
    }
}
