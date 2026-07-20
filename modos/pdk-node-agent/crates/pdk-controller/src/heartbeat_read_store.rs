use std::{fmt, path::Path};

use anyhow::{Context, anyhow};
use pdk_crypto::signed_heartbeat_digest_sha256;
use pdk_protocol::v1::{SignedHeartbeat, SignedHeartbeatAck};
use prost::Message;
use sqlx::{Row, Sqlite, SqlitePool, Transaction, sqlite::SqlitePoolOptions};

#[derive(Clone)]
pub struct ControllerHeartbeatReadStore {
    pool: SqlitePool,
}

#[derive(Clone, Debug)]
pub struct DurableHeartbeatObservation {
    pub node_id: String,
    pub boot_id: String,
    pub sequence: u64,
    pub key_id: String,
    pub heartbeat_digest_sha256: String,
    pub accepted_at_unix_ms: u64,
    pub envelope: SignedHeartbeat,
    pub acknowledgement: SignedHeartbeatAck,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct BootEpochRecord {
    pub node_id: String,
    pub boot_id: String,
    pub generation: u64,
    pub transition_id: String,
    pub activated_at_unix_ms: u64,
}

#[derive(Clone, Debug)]
pub struct CurrentHeartbeatObservation {
    pub epoch: BootEpochRecord,
    pub observation: DurableHeartbeatObservation,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum BootEpochActivation {
    New,
    Idempotent,
}

#[derive(Debug)]
pub enum BootEpochActivationError {
    BootNotObserved,
    Regression { current_generation: u64 },
    Collision,
    Storage(anyhow::Error),
}

impl fmt::Display for BootEpochActivationError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::BootNotObserved => formatter.write_str("boot epoch has no accepted heartbeat"),
            Self::Regression { current_generation } => write!(
                formatter,
                "boot epoch generation does not advance durable generation {current_generation}"
            ),
            Self::Collision => formatter.write_str("boot epoch transition identity collision"),
            Self::Storage(error) => write!(formatter, "boot epoch storage failed: {error:#}"),
        }
    }
}

impl std::error::Error for BootEpochActivationError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            Self::Storage(error) => Some(error.as_ref()),
            Self::BootNotObserved | Self::Regression { .. } | Self::Collision => None,
        }
    }
}

impl ControllerHeartbeatReadStore {
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
            .context("enabling controller observation SQLite WAL mode")?;
        sqlx::query("PRAGMA synchronous = FULL")
            .execute(&pool)
            .await
            .context("setting controller observation SQLite synchronous=FULL")?;
        sqlx::query("PRAGMA busy_timeout = 5000")
            .execute(&pool)
            .await
            .context("setting controller observation SQLite busy timeout")?;
        sqlx::query(
            r#"
            CREATE TABLE IF NOT EXISTS node_boot_epoch_transition (
                node_id TEXT NOT NULL,
                generation INTEGER NOT NULL,
                boot_id TEXT NOT NULL,
                transition_id TEXT NOT NULL UNIQUE,
                activated_at_unix_ms INTEGER NOT NULL,
                PRIMARY KEY (node_id, generation),
                CHECK (generation > 0),
                CHECK (length(node_id) > 0),
                CHECK (length(boot_id) > 0),
                CHECK (length(transition_id) > 0)
            )
            "#,
        )
        .execute(&pool)
        .await
        .context("creating durable boot epoch transition table")?;
        sqlx::query(
            r#"
            CREATE TABLE IF NOT EXISTS node_current_boot_epoch (
                node_id TEXT PRIMARY KEY,
                generation INTEGER NOT NULL,
                boot_id TEXT NOT NULL,
                transition_id TEXT NOT NULL,
                activated_at_unix_ms INTEGER NOT NULL,
                CHECK (generation > 0),
                CHECK (length(node_id) > 0),
                CHECK (length(boot_id) > 0),
                CHECK (length(transition_id) > 0)
            )
            "#,
        )
        .execute(&pool)
        .await
        .context("creating durable current boot epoch table")?;
        Ok(Self { pool })
    }

    pub async fn latest_for_boot(
        &self,
        node_id: &str,
        boot_id: &str,
    ) -> anyhow::Result<Option<DurableHeartbeatObservation>> {
        let mut transaction = self
            .pool
            .begin()
            .await
            .context("starting durable heartbeat read transaction")?;
        let result = latest_in_transaction(&mut transaction, node_id, boot_id).await?;
        transaction
            .commit()
            .await
            .context("committing durable heartbeat read transaction")?;
        Ok(result)
    }

    pub async fn current_for_node(
        &self,
        node_id: &str,
    ) -> anyhow::Result<Option<CurrentHeartbeatObservation>> {
        let mut transaction = self
            .pool
            .begin()
            .await
            .context("starting current observation read transaction")?;
        let row = sqlx::query(
            r#"
            SELECT boot_id, generation, transition_id, activated_at_unix_ms
            FROM node_current_boot_epoch
            WHERE node_id = ?
            "#,
        )
        .bind(node_id)
        .fetch_optional(&mut *transaction)
        .await
        .context("reading durable current boot epoch")?;
        let Some(row) = row else {
            transaction
                .commit()
                .await
                .context("committing empty current observation read")?;
            return Ok(None);
        };
        let epoch = BootEpochRecord {
            node_id: node_id.to_owned(),
            boot_id: row.try_get("boot_id")?,
            generation: as_u64(row.try_get("generation")?)?,
            transition_id: row.try_get("transition_id")?,
            activated_at_unix_ms: as_u64(row.try_get("activated_at_unix_ms")?)?,
        };
        let observation = latest_in_transaction(&mut transaction, node_id, &epoch.boot_id)
            .await?
            .context("current boot epoch has no durable heartbeat floor")?;
        transaction
            .commit()
            .await
            .context("committing current observation read")?;
        Ok(Some(CurrentHeartbeatObservation { epoch, observation }))
    }

    pub async fn activate_boot_epoch(
        &self,
        record: &BootEpochRecord,
    ) -> Result<BootEpochActivation, BootEpochActivationError> {
        self.activate_boot_epoch_inner(record)
            .await
            .map_err(|error| {
                if error.downcast_ref::<BootNotObserved>().is_some() {
                    BootEpochActivationError::BootNotObserved
                } else if let Some(regression) = error.downcast_ref::<BootGenerationRegression>() {
                    BootEpochActivationError::Regression {
                        current_generation: regression.current_generation,
                    }
                } else if error.downcast_ref::<BootTransitionCollision>().is_some() {
                    BootEpochActivationError::Collision
                } else {
                    BootEpochActivationError::Storage(error)
                }
            })
    }

    async fn activate_boot_epoch_inner(
        &self,
        record: &BootEpochRecord,
    ) -> anyhow::Result<BootEpochActivation> {
        anyhow::ensure!(!record.node_id.is_empty(), "boot epoch node ID is empty");
        anyhow::ensure!(!record.boot_id.is_empty(), "boot epoch boot ID is empty");
        anyhow::ensure!(
            !record.transition_id.is_empty(),
            "boot epoch transition ID is empty"
        );
        anyhow::ensure!(record.generation > 0, "boot epoch generation is zero");

        let mut transaction = self
            .pool
            .begin()
            .await
            .context("starting boot epoch activation transaction")?;
        let observed: i64 = sqlx::query_scalar(
            "SELECT COUNT(*) FROM accepted_heartbeat WHERE node_id = ? AND boot_id = ?",
        )
        .bind(&record.node_id)
        .bind(&record.boot_id)
        .fetch_one(&mut *transaction)
        .await
        .context("checking accepted heartbeat for boot epoch")?;
        if observed == 0 {
            return Err(anyhow::Error::new(BootNotObserved));
        }

        if let Some(row) = sqlx::query(
            r#"
            SELECT node_id, boot_id, generation, activated_at_unix_ms
            FROM node_boot_epoch_transition
            WHERE transition_id = ?
            "#,
        )
        .bind(&record.transition_id)
        .fetch_optional(&mut *transaction)
        .await
        .context("checking boot transition identity")?
        {
            let exact = row.try_get::<String, _>("node_id")? == record.node_id
                && row.try_get::<String, _>("boot_id")? == record.boot_id
                && as_u64(row.try_get("generation")?)? == record.generation
                && as_u64(row.try_get("activated_at_unix_ms")?)? == record.activated_at_unix_ms;
            if !exact {
                return Err(anyhow::Error::new(BootTransitionCollision));
            }
            transaction
                .commit()
                .await
                .context("committing idempotent boot epoch activation")?;
            return Ok(BootEpochActivation::Idempotent);
        }

        if let Some(row) =
            sqlx::query("SELECT generation FROM node_current_boot_epoch WHERE node_id = ?")
                .bind(&record.node_id)
                .fetch_optional(&mut *transaction)
                .await
                .context("reading durable boot epoch generation")?
        {
            let current_generation = as_u64(row.try_get("generation")?)?;
            if record.generation <= current_generation {
                return Err(anyhow::Error::new(BootGenerationRegression {
                    current_generation,
                }));
            }
        }

        sqlx::query(
            r#"
            INSERT INTO node_boot_epoch_transition
                (node_id, generation, boot_id, transition_id, activated_at_unix_ms)
            VALUES (?, ?, ?, ?, ?)
            "#,
        )
        .bind(&record.node_id)
        .bind(as_i64(record.generation)?)
        .bind(&record.boot_id)
        .bind(&record.transition_id)
        .bind(as_i64(record.activated_at_unix_ms)?)
        .execute(&mut *transaction)
        .await
        .context("persisting boot epoch transition")?;
        sqlx::query(
            r#"
            INSERT INTO node_current_boot_epoch
                (node_id, generation, boot_id, transition_id, activated_at_unix_ms)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(node_id) DO UPDATE SET
                generation = excluded.generation,
                boot_id = excluded.boot_id,
                transition_id = excluded.transition_id,
                activated_at_unix_ms = excluded.activated_at_unix_ms
            WHERE excluded.generation > node_current_boot_epoch.generation
            "#,
        )
        .bind(&record.node_id)
        .bind(as_i64(record.generation)?)
        .bind(&record.boot_id)
        .bind(&record.transition_id)
        .bind(as_i64(record.activated_at_unix_ms)?)
        .execute(&mut *transaction)
        .await
        .context("advancing durable current boot epoch")?;
        transaction
            .commit()
            .await
            .context("committing boot epoch activation")?;
        Ok(BootEpochActivation::New)
    }
}

async fn latest_in_transaction(
    transaction: &mut Transaction<'_, Sqlite>,
    node_id: &str,
    boot_id: &str,
) -> anyhow::Result<Option<DurableHeartbeatObservation>> {
    let floor = sqlx::query(
        r#"
        SELECT highest_sequence, latest_heartbeat_digest_sha256, latest_accepted_at_unix_ms
        FROM heartbeat_stream_floor
        WHERE node_id = ? AND boot_id = ?
        "#,
    )
    .bind(node_id)
    .bind(boot_id)
    .fetch_optional(&mut **transaction)
    .await
    .context("reading durable heartbeat stream floor")?;
    let Some(floor) = floor else {
        return Ok(None);
    };
    let highest_sequence = as_u64(floor.try_get("highest_sequence")?)?;
    let floor_digest: String = floor.try_get("latest_heartbeat_digest_sha256")?;
    let floor_accepted_at = as_u64(floor.try_get("latest_accepted_at_unix_ms")?)?;
    let row = sqlx::query(
        r#"
        SELECT sequence, key_id, heartbeat_digest_sha256, envelope,
               accepted_at_unix_ms, acknowledgement
        FROM accepted_heartbeat
        WHERE node_id = ? AND boot_id = ? AND sequence = ?
        "#,
    )
    .bind(node_id)
    .bind(boot_id)
    .bind(as_i64(highest_sequence)?)
    .fetch_optional(&mut **transaction)
    .await
    .context("reading latest durable heartbeat envelope")?
    .context("heartbeat stream floor points to a missing accepted envelope")?;

    let sequence = as_u64(row.try_get("sequence")?)?;
    let key_id: String = row.try_get("key_id")?;
    let digest: String = row.try_get("heartbeat_digest_sha256")?;
    let accepted_at_unix_ms = as_u64(row.try_get("accepted_at_unix_ms")?)?;
    anyhow::ensure!(
        sequence == highest_sequence,
        "heartbeat floor sequence mismatch"
    );
    anyhow::ensure!(digest == floor_digest, "heartbeat floor digest mismatch");
    anyhow::ensure!(
        accepted_at_unix_ms == floor_accepted_at,
        "heartbeat floor acceptance time mismatch"
    );

    let envelope_bytes: Vec<u8> = row.try_get("envelope")?;
    let acknowledgement_bytes: Vec<u8> = row.try_get("acknowledgement")?;
    let envelope = SignedHeartbeat::decode(envelope_bytes.as_slice())
        .context("decoding latest durable heartbeat")?;
    let acknowledgement = SignedHeartbeatAck::decode(acknowledgement_bytes.as_slice())
        .context("decoding latest durable heartbeat acknowledgement")?;
    let payload = envelope
        .payload
        .as_ref()
        .context("latest durable heartbeat payload missing")?;
    anyhow::ensure!(
        payload.node_id == node_id,
        "durable heartbeat node mismatch"
    );
    anyhow::ensure!(
        payload.boot_id == boot_id,
        "durable heartbeat boot mismatch"
    );
    anyhow::ensure!(
        payload.sequence == sequence,
        "durable heartbeat sequence mismatch"
    );
    anyhow::ensure!(envelope.key_id == key_id, "durable heartbeat key mismatch");
    anyhow::ensure!(
        signed_heartbeat_digest_sha256(&envelope) == digest,
        "durable heartbeat content digest mismatch"
    );
    let ack = acknowledgement
        .payload
        .as_ref()
        .context("latest durable heartbeat acknowledgement payload missing")?;
    anyhow::ensure!(
        ack.node_id == node_id,
        "durable heartbeat ACK node mismatch"
    );
    anyhow::ensure!(
        ack.boot_id == boot_id,
        "durable heartbeat ACK boot mismatch"
    );
    anyhow::ensure!(
        ack.accepted_sequence == sequence,
        "durable heartbeat ACK sequence mismatch"
    );
    anyhow::ensure!(
        ack.accepted_at_unix_ms == accepted_at_unix_ms,
        "durable heartbeat ACK acceptance time mismatch"
    );
    anyhow::ensure!(
        ack.heartbeat_digest_sha256 == digest,
        "durable heartbeat ACK digest mismatch"
    );

    Ok(Some(DurableHeartbeatObservation {
        node_id: node_id.to_owned(),
        boot_id: boot_id.to_owned(),
        sequence,
        key_id,
        heartbeat_digest_sha256: digest,
        accepted_at_unix_ms,
        envelope,
        acknowledgement,
    }))
}

fn as_i64(value: u64) -> anyhow::Result<i64> {
    i64::try_from(value).map_err(|_| anyhow!("value exceeds SQLite INTEGER range: {value}"))
}
fn as_u64(value: i64) -> anyhow::Result<u64> {
    u64::try_from(value).map_err(|_| anyhow!("negative SQLite INTEGER where u64 expected: {value}"))
}

#[derive(Debug)]
struct BootNotObserved;
impl fmt::Display for BootNotObserved {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter.write_str("boot not observed")
    }
}
impl std::error::Error for BootNotObserved {}

#[derive(Debug)]
struct BootGenerationRegression {
    current_generation: u64,
}
impl fmt::Display for BootGenerationRegression {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(
            formatter,
            "boot generation regression from {}",
            self.current_generation
        )
    }
}
impl std::error::Error for BootGenerationRegression {}

#[derive(Debug)]
struct BootTransitionCollision;
impl fmt::Display for BootTransitionCollision {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter.write_str("boot transition collision")
    }
}
impl std::error::Error for BootTransitionCollision {}
