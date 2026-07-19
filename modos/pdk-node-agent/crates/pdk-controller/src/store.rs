use std::{fmt, path::Path};

use anyhow::{Context, anyhow};
use pdk_crypto::signed_domain_event_digest_sha256;
use pdk_protocol::v1::{SignedDomainEvent, SignedEventAck};
use prost::Message;
use sqlx::{Row, SqlitePool, sqlite::SqlitePoolOptions};

#[derive(Clone)]
pub struct ControllerStateStore {
    pool: SqlitePool,
}

#[derive(Clone, Debug)]
pub enum EventAdmission {
    New(SignedEventAck),
    Idempotent(SignedEventAck),
}

impl EventAdmission {
    pub fn disposition(&self) -> &'static str {
        match self {
            Self::New(_) => "new",
            Self::Idempotent(_) => "idempotent",
        }
    }

    pub fn into_ack(self) -> SignedEventAck {
        match self {
            Self::New(ack) | Self::Idempotent(ack) => ack,
        }
    }
}

#[derive(Debug)]
pub enum EventAdmissionError {
    Collision,
    Storage(anyhow::Error),
}

impl fmt::Display for EventAdmissionError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Collision => {
                formatter.write_str("event ID collides with different signed content")
            }
            Self::Storage(error) => write!(formatter, "event admission storage failed: {error:#}"),
        }
    }
}

impl std::error::Error for EventAdmissionError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            Self::Collision => None,
            Self::Storage(error) => Some(error.as_ref()),
        }
    }
}

impl ControllerStateStore {
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
            enforce_private_directory(parent).await?;
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
            .context("enabling controller SQLite WAL mode")?;
        sqlx::query("PRAGMA synchronous = FULL")
            .execute(&pool)
            .await
            .context("setting controller SQLite synchronous=FULL")?;
        sqlx::query("PRAGMA busy_timeout = 5000")
            .execute(&pool)
            .await
            .context("setting controller SQLite busy timeout")?;
        sqlx::query("PRAGMA foreign_keys = ON")
            .execute(&pool)
            .await
            .context("enabling controller SQLite foreign keys")?;

        sqlx::query(
            r#"
            CREATE TABLE IF NOT EXISTS controller_event_write_fence (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                generation INTEGER NOT NULL
            )
            "#,
        )
        .execute(&pool)
        .await
        .context("creating controller event write fence")?;
        sqlx::query(
            "INSERT OR IGNORE INTO controller_event_write_fence (id, generation) VALUES (1, 0)",
        )
        .execute(&pool)
        .await
        .context("initializing controller event write fence")?;
        sqlx::query(
            r#"
            CREATE TABLE IF NOT EXISTS accepted_domain_event (
                event_id TEXT PRIMARY KEY,
                source_node_id TEXT NOT NULL,
                key_id TEXT NOT NULL,
                event_digest_sha256 TEXT NOT NULL,
                envelope BLOB NOT NULL,
                accepted_at_unix_ms INTEGER NOT NULL,
                acknowledgement BLOB NOT NULL,
                CHECK (length(event_id) > 0),
                CHECK (length(source_node_id) > 0),
                CHECK (event_digest_sha256 GLOB 'sha256:[0-9a-f]*'),
                CHECK (length(event_digest_sha256) = 71)
            )
            "#,
        )
        .execute(&pool)
        .await
        .context("creating durable accepted domain event table")?;
        enforce_private_file(path).await?;

        Ok(Self { pool })
    }

    pub async fn admit_event(
        &self,
        envelope: &SignedDomainEvent,
        candidate_ack: &SignedEventAck,
    ) -> Result<EventAdmission, EventAdmissionError> {
        self.admit_event_inner(envelope, candidate_ack)
            .await
            .map_err(|error| match error.downcast_ref::<EventCollision>() {
                Some(_) => EventAdmissionError::Collision,
                None => EventAdmissionError::Storage(error),
            })
    }

    async fn admit_event_inner(
        &self,
        envelope: &SignedDomainEvent,
        candidate_ack: &SignedEventAck,
    ) -> anyhow::Result<EventAdmission> {
        let event = envelope
            .payload
            .as_ref()
            .context("signed event payload missing during durable admission")?;
        let ack_payload = candidate_ack
            .payload
            .as_ref()
            .context("signed event acknowledgement payload missing")?;
        let event_digest = signed_domain_event_digest_sha256(envelope);
        anyhow::ensure!(
            ack_payload.event_id == event.event_id,
            "candidate acknowledgement event ID mismatch"
        );
        anyhow::ensure!(
            ack_payload.source_node_id == event.source_node_id,
            "candidate acknowledgement source mismatch"
        );
        anyhow::ensure!(
            ack_payload.event_digest_sha256 == event_digest,
            "candidate acknowledgement digest mismatch"
        );

        let envelope_bytes = envelope.encode_to_vec();
        let acknowledgement_bytes = candidate_ack.encode_to_vec();
        let mut transaction = self
            .pool
            .begin()
            .await
            .context("starting durable event admission transaction")?;
        sqlx::query(
            "UPDATE controller_event_write_fence SET generation = generation + 1 WHERE id = 1",
        )
        .execute(&mut *transaction)
        .await
        .context("acquiring durable event write fence")?;

        if let Some(row) = sqlx::query(
            r#"
            SELECT event_digest_sha256, envelope, acknowledgement
            FROM accepted_domain_event
            WHERE event_id = ?
            "#,
        )
        .bind(&event.event_id)
        .fetch_optional(&mut *transaction)
        .await
        .context("checking durable event identity")?
        {
            let existing_digest: String = row.try_get("event_digest_sha256")?;
            let existing_envelope: Vec<u8> = row.try_get("envelope")?;
            if existing_digest != event_digest || existing_envelope != envelope_bytes {
                return Err(anyhow::Error::new(EventCollision));
            }
            let acknowledgement_bytes: Vec<u8> = row.try_get("acknowledgement")?;
            let acknowledgement = SignedEventAck::decode(acknowledgement_bytes.as_slice())
                .context("decoding durable event acknowledgement")?;
            transaction
                .commit()
                .await
                .context("committing idempotent event admission")?;
            return Ok(EventAdmission::Idempotent(acknowledgement));
        }

        sqlx::query(
            r#"
            INSERT INTO accepted_domain_event
                (event_id, source_node_id, key_id, event_digest_sha256, envelope,
                 accepted_at_unix_ms, acknowledgement)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            "#,
        )
        .bind(&event.event_id)
        .bind(&event.source_node_id)
        .bind(&envelope.key_id)
        .bind(&event_digest)
        .bind(&envelope_bytes)
        .bind(as_i64(ack_payload.accepted_at_unix_ms)?)
        .bind(&acknowledgement_bytes)
        .execute(&mut *transaction)
        .await
        .context("persisting signed event and acknowledgement")?;
        transaction
            .commit()
            .await
            .context("committing signed event and acknowledgement")?;
        Ok(EventAdmission::New(candidate_ack.clone()))
    }

    #[cfg(test)]
    async fn event_count(&self) -> anyhow::Result<i64> {
        sqlx::query_scalar("SELECT COUNT(*) FROM accepted_domain_event")
            .fetch_one(&self.pool)
            .await
            .context("counting durable accepted events")
    }
}

#[derive(Debug)]
struct EventCollision;

impl fmt::Display for EventCollision {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter.write_str("event ID collision")
    }
}

impl std::error::Error for EventCollision {}

fn as_i64(value: u64) -> anyhow::Result<i64> {
    i64::try_from(value).map_err(|_| anyhow!("value exceeds SQLite INTEGER range: {value}"))
}

async fn enforce_private_directory(path: &Path) -> anyhow::Result<()> {
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        tokio::fs::set_permissions(path, std::fs::Permissions::from_mode(0o700))
            .await
            .with_context(|| format!("setting private mode on {}", path.display()))?;
    }
    Ok(())
}

async fn enforce_private_file(path: &Path) -> anyhow::Result<()> {
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        tokio::fs::set_permissions(path, std::fs::Permissions::from_mode(0o600))
            .await
            .with_context(|| format!("setting private mode on {}", path.display()))?;
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use std::{path::PathBuf, sync::Arc};

    use pdk_crypto::signed_domain_event_digest_sha256;
    use pdk_protocol::{
        PROTOCOL_VERSION,
        v1::{DomainEventPayload, EventAckPayload, SignedDomainEvent, SignedEventAck},
    };
    use prost::Message;
    use uuid::Uuid;

    use super::{ControllerStateStore, EventAdmission, EventAdmissionError};

    fn database_path(label: &str) -> PathBuf {
        std::env::temp_dir()
            .join(format!("pdk-controller-{label}-{}", Uuid::new_v4()))
            .join("controller.db")
    }

    fn event(event_id: &str, payload: &[u8]) -> SignedDomainEvent {
        SignedDomainEvent {
            key_id: "node-key-v1".into(),
            payload: Some(DomainEventPayload {
                protocol_version: PROTOCOL_VERSION,
                event_id: event_id.into(),
                domain_id: "domain://test".into(),
                source_node_id: "node://test/source".into(),
                created_at_unix_ms: 10,
                trace_id: "trace/test".into(),
                event_type: "test.event".into(),
                payload_json: payload.to_vec(),
            }),
            signature_base64: "synthetic-signature".into(),
        }
    }

    fn acknowledgement(
        event: &SignedDomainEvent,
        ack_id: &str,
        accepted_at_unix_ms: u64,
    ) -> SignedEventAck {
        let payload = event.payload.as_ref().expect("event payload");
        SignedEventAck {
            key_id: "controller-key-v1".into(),
            payload: Some(EventAckPayload {
                ack_id: ack_id.into(),
                domain_id: payload.domain_id.clone(),
                controller_id: "controller://test".into(),
                event_id: payload.event_id.clone(),
                accepted_at_unix_ms,
                source_node_id: payload.source_node_id.clone(),
                event_digest_sha256: signed_domain_event_digest_sha256(event),
            }),
            signature_base64: "synthetic-controller-signature".into(),
        }
    }

    #[tokio::test]
    async fn exact_retry_returns_the_original_acknowledgement() {
        let path = database_path("retry");
        let store = ControllerStateStore::open(&path).await.expect("open store");
        let event = event("event/retry", br#"{"value":1}"#);
        let first_ack = acknowledgement(&event, "ack/first", 20);
        let later_candidate = acknowledgement(&event, "ack/later", 30);

        let first = store
            .admit_event(&event, &first_ack)
            .await
            .expect("first admission");
        assert!(matches!(first, EventAdmission::New(_)));
        let retry = store
            .admit_event(&event, &later_candidate)
            .await
            .expect("idempotent retry");
        let retry_ack = match retry {
            EventAdmission::Idempotent(ack) => ack,
            EventAdmission::New(_) => panic!("retry was inserted twice"),
        };
        assert_eq!(retry_ack.encode_to_vec(), first_ack.encode_to_vec());
        assert_eq!(store.event_count().await.expect("event count"), 1);
        let _ = tokio::fs::remove_dir_all(path.parent().expect("database parent")).await;
    }

    #[tokio::test]
    async fn same_event_id_with_different_content_is_rejected() {
        let path = database_path("collision");
        let store = ControllerStateStore::open(&path).await.expect("open store");
        let first = event("event/collision", br#"{"value":1}"#);
        let altered = event("event/collision", br#"{"value":2}"#);
        store
            .admit_event(&first, &acknowledgement(&first, "ack/first", 20))
            .await
            .expect("first admission");
        let error = store
            .admit_event(&altered, &acknowledgement(&altered, "ack/altered", 30))
            .await
            .expect_err("collision must fail");
        assert!(matches!(error, EventAdmissionError::Collision));
        assert_eq!(store.event_count().await.expect("event count"), 1);
        let _ = tokio::fs::remove_dir_all(path.parent().expect("database parent")).await;
    }

    #[tokio::test]
    async fn acknowledgement_survives_store_reopen() {
        let path = database_path("reopen");
        let event = event("event/reopen", br#"{"value":1}"#);
        let original_ack = acknowledgement(&event, "ack/original", 20);
        {
            let store = ControllerStateStore::open(&path).await.expect("open store");
            store
                .admit_event(&event, &original_ack)
                .await
                .expect("first admission");
        }
        let reopened = ControllerStateStore::open(&path)
            .await
            .expect("reopen store");
        let retry = reopened
            .admit_event(&event, &acknowledgement(&event, "ack/new", 40))
            .await
            .expect("retry after reopen")
            .into_ack();
        assert_eq!(retry.encode_to_vec(), original_ack.encode_to_vec());
        let _ = tokio::fs::remove_dir_all(path.parent().expect("database parent")).await;
    }

    #[tokio::test]
    async fn concurrent_exact_retries_commit_one_identity() {
        let path = database_path("concurrent");
        let store = Arc::new(ControllerStateStore::open(&path).await.expect("open store"));
        let event = Arc::new(event("event/concurrent", br#"{"value":1}"#));
        let ack = Arc::new(acknowledgement(&event, "ack/concurrent", 20));
        let first_store = Arc::clone(&store);
        let first_event = Arc::clone(&event);
        let first_ack = Arc::clone(&ack);
        let second_store = Arc::clone(&store);
        let second_event = Arc::clone(&event);
        let second_ack = Arc::clone(&ack);
        let (first, second) = tokio::join!(
            async move { first_store.admit_event(&first_event, &first_ack).await },
            async move { second_store.admit_event(&second_event, &second_ack).await }
        );
        let first = first.expect("first concurrent admission");
        let second = second.expect("second concurrent admission");
        assert_ne!(first.disposition(), second.disposition());
        assert_eq!(
            first.into_ack().encode_to_vec(),
            second.into_ack().encode_to_vec()
        );
        assert_eq!(store.event_count().await.expect("event count"), 1);
        let _ = tokio::fs::remove_dir_all(path.parent().expect("database parent")).await;
    }

    #[tokio::test]
    async fn failed_insert_returns_no_acknowledgement_and_commits_nothing() {
        let path = database_path("failure");
        let store = ControllerStateStore::open(&path).await.expect("open store");
        sqlx::query(
            r#"
            CREATE TRIGGER reject_event_insert
            BEFORE INSERT ON accepted_domain_event
            BEGIN
                SELECT RAISE(ABORT, 'forced event insert failure');
            END
            "#,
        )
        .execute(&store.pool)
        .await
        .expect("create failure trigger");
        let event = event("event/failure", br#"{"value":1}"#);
        let error = store
            .admit_event(&event, &acknowledgement(&event, "ack/failure", 20))
            .await
            .expect_err("forced insert failure");
        assert!(matches!(error, EventAdmissionError::Storage(_)));
        assert_eq!(store.event_count().await.expect("event count"), 0);
        let _ = tokio::fs::remove_dir_all(path.parent().expect("database parent")).await;
    }
}
