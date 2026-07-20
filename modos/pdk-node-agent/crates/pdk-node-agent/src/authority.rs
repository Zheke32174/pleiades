use std::path::Path;

use anyhow::{Context, Result, bail};
use pdk_protocol::v1::CapabilityGrantPayload;
use sqlx::{Row, Sqlite, SqlitePool, Transaction, sqlite::SqlitePoolOptions};

use crate::audit::{PreparedAuditEvent, insert_prepared_event_tx};

#[derive(Clone)]
pub struct AuthorityStateStore {
    pool: SqlitePool,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub enum GrantAdmission {
    New { event_id: String },
    Recovered { event_id: String },
    Idempotent { event_id: String },
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub enum OperationIntentCommit {
    New { event_id: String, consumed_use: u32 },
    Idempotent { event_id: String, consumed_use: u32 },
}

impl OperationIntentCommit {
    pub fn event_id(&self) -> &str {
        match self {
            Self::New { event_id, .. } | Self::Idempotent { event_id, .. } => event_id,
        }
    }

    pub fn consumed_use(&self) -> u32 {
        match self {
            Self::New { consumed_use, .. } | Self::Idempotent { consumed_use, .. } => *consumed_use,
        }
    }

    pub fn replayed(&self) -> bool {
        matches!(self, Self::Idempotent { .. })
    }
}

impl AuthorityStateStore {
    pub async fn open(path: &Path) -> Result<Self> {
        if let Some(parent) = path.parent() {
            tokio::fs::create_dir_all(parent).await.with_context(|| {
                format!("creating authority database directory {}", parent.display())
            })?;
        }
        let url = format!("sqlite://{}?mode=rwc", path.display());
        let pool = SqlitePoolOptions::new()
            .max_connections(1)
            .connect(&url)
            .await
            .with_context(|| format!("opening SQLite authority state {}", path.display()))?;
        sqlx::query("PRAGMA journal_mode = WAL")
            .execute(&pool)
            .await
            .context("enabling SQLite WAL mode for authority state")?;
        sqlx::query("PRAGMA synchronous = FULL")
            .execute(&pool)
            .await
            .context("setting SQLite authority state synchronous=FULL")?;
        sqlx::query("PRAGMA busy_timeout = 5000")
            .execute(&pool)
            .await
            .context("setting SQLite authority busy timeout")?;
        sqlx::query("PRAGMA foreign_keys = ON")
            .execute(&pool)
            .await
            .context("enabling SQLite foreign keys for authority state")?;
        sqlx::query(
            r#"
            CREATE TABLE IF NOT EXISTS domain_event_queue (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL UNIQUE,
                created_at_unix_ms INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                trace_id TEXT NOT NULL,
                envelope BLOB NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0,
                last_error TEXT
            )
            "#,
        )
        .execute(&pool)
        .await
        .context("creating authority audit outbox")?;
        sqlx::query(
            r#"
            CREATE TABLE IF NOT EXISTS capability_sequence_floor (
                sequence_key TEXT PRIMARY KEY,
                highest_sequence INTEGER NOT NULL
            )
            "#,
        )
        .execute(&pool)
        .await
        .context("creating capability sequence floor")?;
        sqlx::query(
            r#"
            CREATE TABLE IF NOT EXISTS capability_authority_write_fence (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                generation INTEGER NOT NULL
            )
            "#,
        )
        .execute(&pool)
        .await
        .context("creating capability authority write fence")?;
        sqlx::query(
            "INSERT OR IGNORE INTO capability_authority_write_fence (id, generation) VALUES (1, 0)",
        )
        .execute(&pool)
        .await
        .context("initializing capability authority write fence")?;
        sqlx::query(
            r#"
            CREATE TABLE IF NOT EXISTS capability_grant_state (
                token_id TEXT PRIMARY KEY,
                signature_base64 TEXT NOT NULL,
                sequence_key TEXT NOT NULL,
                grant_sequence INTEGER NOT NULL,
                max_uses INTEGER NOT NULL,
                uses INTEGER NOT NULL DEFAULT 0,
                expires_at_unix_ms INTEGER NOT NULL,
                admission_event_id TEXT,
                FOREIGN KEY(sequence_key)
                    REFERENCES capability_sequence_floor(sequence_key)
            )
            "#,
        )
        .execute(&pool)
        .await
        .context("creating durable capability grant state")?;
        ensure_column(
            &pool,
            "capability_grant_state",
            "admission_event_id",
            "ALTER TABLE capability_grant_state ADD COLUMN admission_event_id TEXT",
        )
        .await?;
        sqlx::query(
            r#"
            CREATE TABLE IF NOT EXISTS capability_token_identity (
                token_id TEXT PRIMARY KEY,
                signature_base64 TEXT NOT NULL,
                sequence_key TEXT NOT NULL,
                grant_sequence INTEGER NOT NULL,
                first_seen_at_unix_ms INTEGER NOT NULL,
                admission_event_id TEXT
            )
            "#,
        )
        .execute(&pool)
        .await
        .context("creating durable capability token identity")?;
        sqlx::query(
            r#"
            INSERT OR IGNORE INTO capability_token_identity
                (token_id, signature_base64, sequence_key, grant_sequence, first_seen_at_unix_ms, admission_event_id)
            SELECT token_id, signature_base64, sequence_key, grant_sequence, 0, admission_event_id
            FROM capability_grant_state
            "#,
        )
        .execute(&pool)
        .await
        .context("migrating existing capability token identities")?;
        sqlx::query(
            r#"
            CREATE TABLE IF NOT EXISTS capability_revocation_tombstone (
                token_id TEXT PRIMARY KEY,
                signature_base64 TEXT NOT NULL,
                revoked_at_unix_ms INTEGER NOT NULL,
                reason TEXT NOT NULL,
                revocation_event_id TEXT NOT NULL,
                FOREIGN KEY(token_id)
                    REFERENCES capability_token_identity(token_id)
            )
            "#,
        )
        .execute(&pool)
        .await
        .context("creating capability revocation tombstones")?;
        sqlx::query(
            r#"
            CREATE TABLE IF NOT EXISTS capability_operation_intent (
                controller_id TEXT NOT NULL,
                trace_id TEXT NOT NULL,
                request_digest_sha256 TEXT NOT NULL,
                token_id TEXT NOT NULL,
                operation TEXT NOT NULL,
                workload_id TEXT NOT NULL,
                committed_use INTEGER NOT NULL,
                intent_event_id TEXT NOT NULL UNIQUE,
                committed_at_unix_ms INTEGER NOT NULL,
                PRIMARY KEY(controller_id, trace_id),
                FOREIGN KEY(token_id)
                    REFERENCES capability_token_identity(token_id)
            )
            "#,
        )
        .execute(&pool)
        .await
        .context("creating durable capability operation intents")?;
        sqlx::query(
            "CREATE INDEX IF NOT EXISTS capability_operation_intent_token_idx ON capability_operation_intent(token_id)",
        )
        .execute(&pool)
        .await
        .context("indexing capability operation intents by token")?;
        sqlx::query(
            "CREATE INDEX IF NOT EXISTS capability_grant_expiry_idx ON capability_grant_state(expires_at_unix_ms)",
        )
        .execute(&pool)
        .await
        .context("creating capability expiry index")?;
        Ok(Self { pool })
    }

    pub async fn admit_grant(
        &self,
        grant: &CapabilityGrantPayload,
        signature_base64: &str,
        event: &PreparedAuditEvent,
    ) -> Result<GrantAdmission> {
        let sequence_key = sequence_key(grant);
        let mut transaction = self
            .pool
            .begin()
            .await
            .context("starting capability admission transaction")?;
        acquire_authority_write_fence(&mut transaction).await?;

        if let Some(row) = sqlx::query(
            "SELECT signature_base64 FROM capability_revocation_tombstone WHERE token_id = ?",
        )
        .bind(&grant.token_id)
        .fetch_optional(&mut *transaction)
        .await
        .context("checking capability revocation tombstone")?
        {
            let revoked_signature: String = row.try_get("signature_base64")?;
            if revoked_signature == signature_base64 {
                bail!("capability token is durably revoked");
            }
            bail!("revoked token ID collides with different signed content");
        }

        if let Some(row) = sqlx::query(
            r#"
            SELECT signature_base64, admission_event_id
            FROM capability_token_identity
            WHERE token_id = ?
            "#,
        )
        .bind(&grant.token_id)
        .fetch_optional(&mut *transaction)
        .await
        .context("checking durable capability token identity")?
        {
            let existing_signature: String = row.try_get("signature_base64")?;
            if existing_signature != signature_base64 {
                bail!("token ID collision with different durable signed content");
            }
            let admission_event_id: Option<String> = row.try_get("admission_event_id")?;
            let active: i64 = sqlx::query_scalar(
                "SELECT COUNT(*) FROM capability_grant_state WHERE token_id = ?",
            )
            .bind(&grant.token_id)
            .fetch_one(&mut *transaction)
            .await
            .context("checking active durable capability state")?;
            if active == 0 {
                bail!("capability identity is retained but active state was compacted");
            }
            if let Some(event_id) = admission_event_id {
                transaction
                    .commit()
                    .await
                    .context("committing idempotent capability admission")?;
                return Ok(GrantAdmission::Idempotent { event_id });
            }

            insert_prepared_event_tx(&mut transaction, event).await?;
            sqlx::query(
                "UPDATE capability_token_identity SET admission_event_id = ? WHERE token_id = ?",
            )
            .bind(&event.event_id)
            .bind(&grant.token_id)
            .execute(&mut *transaction)
            .await
            .context("linking recovered capability admission receipt")?;
            sqlx::query(
                "UPDATE capability_grant_state SET admission_event_id = ? WHERE token_id = ?",
            )
            .bind(&event.event_id)
            .bind(&grant.token_id)
            .execute(&mut *transaction)
            .await
            .context("linking recovered active capability receipt")?;
            transaction
                .commit()
                .await
                .context("committing recovered capability admission")?;
            return Ok(GrantAdmission::Recovered {
                event_id: event.event_id.clone(),
            });
        }

        if let Some(row) = sqlx::query(
            "SELECT highest_sequence FROM capability_sequence_floor WHERE sequence_key = ?",
        )
        .bind(&sequence_key)
        .fetch_optional(&mut *transaction)
        .await
        .context("reading durable capability sequence floor")?
        {
            let highest_sequence: i64 = row.try_get("highest_sequence")?;
            if as_i64(grant.grant_sequence) <= highest_sequence {
                bail!(
                    "capability grant sequence {} is not newer than durable accepted sequence {}",
                    grant.grant_sequence,
                    highest_sequence
                );
            }
        }

        sqlx::query(
            r#"
            INSERT INTO capability_sequence_floor (sequence_key, highest_sequence)
            VALUES (?, ?)
            ON CONFLICT(sequence_key) DO UPDATE SET
                highest_sequence = excluded.highest_sequence
            WHERE excluded.highest_sequence > capability_sequence_floor.highest_sequence
            "#,
        )
        .bind(&sequence_key)
        .bind(as_i64(grant.grant_sequence))
        .execute(&mut *transaction)
        .await
        .context("advancing durable capability sequence floor")?;

        sqlx::query(
            r#"
            INSERT INTO capability_token_identity
                (token_id, signature_base64, sequence_key, grant_sequence, first_seen_at_unix_ms, admission_event_id)
            VALUES (?, ?, ?, ?, ?, ?)
            "#,
        )
        .bind(&grant.token_id)
        .bind(signature_base64)
        .bind(&sequence_key)
        .bind(as_i64(grant.grant_sequence))
        .bind(as_i64(event.created_at_unix_ms))
        .bind(&event.event_id)
        .execute(&mut *transaction)
        .await
        .context("persisting durable capability token identity")?;

        sqlx::query(
            r#"
            INSERT INTO capability_grant_state
                (token_id, signature_base64, sequence_key, grant_sequence, max_uses, uses, expires_at_unix_ms, admission_event_id)
            VALUES (?, ?, ?, ?, ?, 0, ?, ?)
            "#,
        )
        .bind(&grant.token_id)
        .bind(signature_base64)
        .bind(&sequence_key)
        .bind(as_i64(grant.grant_sequence))
        .bind(i64::from(grant.max_uses))
        .bind(as_i64(grant.expires_at_unix_ms))
        .bind(&event.event_id)
        .execute(&mut *transaction)
        .await
        .context("persisting durable capability grant state")?;

        insert_prepared_event_tx(&mut transaction, event).await?;
        transaction
            .commit()
            .await
            .context("committing capability admission and audit outbox")?;
        Ok(GrantAdmission::New {
            event_id: event.event_id.clone(),
        })
    }

    #[allow(clippy::too_many_arguments)]
    pub async fn consume_use_with_intent(
        &self,
        controller_id: &str,
        trace_id: &str,
        request_digest_sha256: &str,
        token_id: &str,
        operation: &str,
        workload_id: &str,
        now_unix_ms: u64,
        event: &PreparedAuditEvent,
    ) -> Result<OperationIntentCommit> {
        let mut transaction = self
            .pool
            .begin()
            .await
            .context("starting capability use and intent transaction")?;
        acquire_authority_write_fence(&mut transaction).await?;

        if let Some(row) = sqlx::query(
            r#"
            SELECT request_digest_sha256, token_id, operation, workload_id,
                   committed_use, intent_event_id
            FROM capability_operation_intent
            WHERE controller_id = ? AND trace_id = ?
            "#,
        )
        .bind(controller_id)
        .bind(trace_id)
        .fetch_optional(&mut *transaction)
        .await
        .context("checking durable operation intent idempotency key")?
        {
            let existing_digest: String = row.try_get("request_digest_sha256")?;
            let existing_token: String = row.try_get("token_id")?;
            let existing_operation: String = row.try_get("operation")?;
            let existing_workload: String = row.try_get("workload_id")?;
            if existing_digest != request_digest_sha256
                || existing_token != token_id
                || existing_operation != operation
                || existing_workload != workload_id
            {
                bail!("operation idempotency key collides with different request content");
            }
            let committed_use: i64 = row.try_get("committed_use")?;
            let event_id: String = row.try_get("intent_event_id")?;
            transaction
                .commit()
                .await
                .context("committing idempotent operation intent read")?;
            return Ok(OperationIntentCommit::Idempotent {
                event_id,
                consumed_use: committed_use.max(0).try_into().unwrap_or(u32::MAX),
            });
        }

        let row = sqlx::query(
            r#"
            SELECT g.uses, g.max_uses, g.expires_at_unix_ms,
                   CASE WHEN r.token_id IS NULL THEN 0 ELSE 1 END AS revoked
            FROM capability_grant_state AS g
            LEFT JOIN capability_revocation_tombstone AS r
              ON r.token_id = g.token_id
            WHERE g.token_id = ?
            "#,
        )
        .bind(token_id)
        .fetch_optional(&mut *transaction)
        .await
        .context("reading durable capability use state")?
        .context("capability token has no active durable grant state")?;

        let uses: i64 = row.try_get("uses")?;
        let max_uses: i64 = row.try_get("max_uses")?;
        let expires_at_unix_ms: i64 = row.try_get("expires_at_unix_ms")?;
        let revoked: i64 = row.try_get("revoked")?;
        if revoked != 0 {
            bail!("durable capability token is revoked");
        }
        if as_i64(now_unix_ms) >= expires_at_unix_ms {
            bail!("durable capability lease has expired");
        }
        if uses >= max_uses {
            bail!("durable capability lease use budget is exhausted");
        }

        let result = sqlx::query(
            r#"
            UPDATE capability_grant_state
            SET uses = uses + 1
            WHERE token_id = ?
              AND uses < max_uses
              AND expires_at_unix_ms > ?
              AND NOT EXISTS (
                  SELECT 1 FROM capability_revocation_tombstone
                  WHERE capability_revocation_tombstone.token_id = capability_grant_state.token_id
              )
            "#,
        )
        .bind(token_id)
        .bind(as_i64(now_unix_ms))
        .execute(&mut *transaction)
        .await
        .context("consuming durable capability use")?;
        if result.rows_affected() != 1 {
            bail!("durable capability use was not consumed");
        }

        let consumed = uses.saturating_add(1).max(0);
        insert_prepared_event_tx(&mut transaction, event).await?;
        sqlx::query(
            r#"
            INSERT INTO capability_operation_intent
                (controller_id, trace_id, request_digest_sha256, token_id,
                 operation, workload_id, committed_use, intent_event_id,
                 committed_at_unix_ms)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            "#,
        )
        .bind(controller_id)
        .bind(trace_id)
        .bind(request_digest_sha256)
        .bind(token_id)
        .bind(operation)
        .bind(workload_id)
        .bind(consumed)
        .bind(&event.event_id)
        .bind(as_i64(now_unix_ms))
        .execute(&mut *transaction)
        .await
        .context("persisting durable capability operation intent")?;
        transaction
            .commit()
            .await
            .context("committing capability use, intent, and signed receipt")?;
        Ok(OperationIntentCommit::New {
            event_id: event.event_id.clone(),
            consumed_use: consumed.try_into().unwrap_or(u32::MAX),
        })
    }

    #[cfg(test)]
    async fn consume_use(&self, token_id: &str, now_unix_ms: u64) -> Result<u32> {
        let identity = uuid::Uuid::new_v4().to_string();
        let trace_id = format!("test-use-trace-{identity}");
        let event = PreparedAuditEvent {
            event_id: format!("test-use-event-{identity}"),
            created_at_unix_ms: now_unix_ms,
            event_type: "capability.use.test".into(),
            trace_id: trace_id.clone(),
            envelope: vec![7, 8, 9],
        };
        self.consume_use_with_intent(
            "test-controller",
            &trace_id,
            &format!("sha256:{}", "a".repeat(64)),
            token_id,
            "test_use",
            "workload-1",
            now_unix_ms,
            &event,
        )
        .await
        .map(|commit| commit.consumed_use())
    }

    #[cfg_attr(
        not(test),
        expect(
            dead_code,
            reason = "durable storage primitive awaits the authenticated revocation RPC checkpoint"
        )
    )]
    pub async fn revoke_grant(
        &self,
        token_id: &str,
        signature_base64: &str,
        revoked_at_unix_ms: u64,
        reason: &str,
        event: &PreparedAuditEvent,
    ) -> Result<bool> {
        let mut transaction = self
            .pool
            .begin()
            .await
            .context("starting capability revocation transaction")?;
        acquire_authority_write_fence(&mut transaction).await?;
        let identity = sqlx::query(
            "SELECT signature_base64 FROM capability_token_identity WHERE token_id = ?",
        )
        .bind(token_id)
        .fetch_optional(&mut *transaction)
        .await
        .context("reading capability identity for revocation")?
        .context("cannot revoke an unknown capability token")?;
        let existing_signature: String = identity.try_get("signature_base64")?;
        if existing_signature != signature_base64 {
            bail!("revocation signature identity does not match admitted token");
        }

        if let Some(row) = sqlx::query(
            "SELECT signature_base64 FROM capability_revocation_tombstone WHERE token_id = ?",
        )
        .bind(token_id)
        .fetch_optional(&mut *transaction)
        .await
        .context("checking existing capability revocation")?
        {
            let revoked_signature: String = row.try_get("signature_base64")?;
            if revoked_signature != signature_base64 {
                bail!("revocation tombstone collides with different signed content");
            }
            transaction
                .commit()
                .await
                .context("committing idempotent capability revocation")?;
            return Ok(false);
        }

        sqlx::query(
            r#"
            INSERT INTO capability_revocation_tombstone
                (token_id, signature_base64, revoked_at_unix_ms, reason, revocation_event_id)
            VALUES (?, ?, ?, ?, ?)
            "#,
        )
        .bind(token_id)
        .bind(signature_base64)
        .bind(as_i64(revoked_at_unix_ms))
        .bind(reason)
        .bind(&event.event_id)
        .execute(&mut *transaction)
        .await
        .context("persisting capability revocation tombstone")?;
        insert_prepared_event_tx(&mut transaction, event).await?;
        transaction
            .commit()
            .await
            .context("committing capability revocation and audit outbox")?;
        Ok(true)
    }

    pub async fn compact_expired(&self, now_unix_ms: u64) -> Result<u64> {
        let mut transaction = self
            .pool
            .begin()
            .await
            .context("starting capability compaction transaction")?;
        acquire_authority_write_fence(&mut transaction).await?;
        let result =
            sqlx::query("DELETE FROM capability_grant_state WHERE expires_at_unix_ms <= ?")
                .bind(as_i64(now_unix_ms))
                .execute(&mut *transaction)
                .await
                .context("compacting expired active capability state")?;
        let rows_affected = result.rows_affected();
        transaction
            .commit()
            .await
            .context("committing capability compaction")?;
        Ok(rows_affected)
    }
}

async fn acquire_authority_write_fence(transaction: &mut Transaction<'_, Sqlite>) -> Result<()> {
    sqlx::query(
        "UPDATE capability_authority_write_fence SET generation = generation + 1 WHERE id = 1",
    )
    .execute(&mut **transaction)
    .await
    .context("acquiring capability authority write fence")?;
    Ok(())
}

async fn ensure_column(
    pool: &SqlitePool,
    table: &str,
    column: &str,
    alter_statement: &str,
) -> Result<()> {
    let pragma = format!("PRAGMA table_info({table})");
    let rows = sqlx::query(&pragma)
        .fetch_all(pool)
        .await
        .with_context(|| format!("reading schema for {table}"))?;
    let exists = rows.iter().any(|row| {
        row.try_get::<String, _>("name")
            .map(|name| name == column)
            .unwrap_or(false)
    });
    if !exists {
        sqlx::query(alter_statement)
            .execute(pool)
            .await
            .with_context(|| format!("adding {table}.{column}"))?;
    }
    Ok(())
}

fn sequence_key(grant: &CapabilityGrantPayload) -> String {
    format!(
        "{}|{}|{}",
        grant.issuer_id, grant.target_node_id, grant.subject_workload_id
    )
}

fn as_i64(value: u64) -> i64 {
    value.min(i64::MAX as u64) as i64
}

#[cfg(test)]
mod tests {
    use std::time::Duration;

    use pdk_protocol::v1::CapabilityGrantPayload;
    use uuid::Uuid;

    use super::*;

    fn grant(token_id: &str, sequence: u64, max_uses: u32) -> CapabilityGrantPayload {
        CapabilityGrantPayload {
            token_id: token_id.into(),
            issuer_id: "controller-1".into(),
            target_node_id: "node-1".into(),
            subject_workload_id: "workload-1".into(),
            grant_sequence: sequence,
            max_uses,
            expires_at_unix_ms: crate::autonomy::unix_ms().saturating_add(60_000),
            ..Default::default()
        }
    }

    fn event(event_id: &str, event_type: &str) -> PreparedAuditEvent {
        PreparedAuditEvent {
            event_id: event_id.into(),
            created_at_unix_ms: crate::autonomy::unix_ms(),
            event_type: event_type.into(),
            trace_id: "test-trace".into(),
            envelope: vec![1, 2, 3],
        }
    }

    fn database_path(name: &str) -> std::path::PathBuf {
        std::env::temp_dir().join(format!("pdk-{name}-{}.sqlite", Uuid::new_v4()))
    }

    async fn remove_database(path: &Path) {
        let _ = tokio::fs::remove_file(path).await;
        let _ = tokio::fs::remove_file(format!("{}-wal", path.display())).await;
        let _ = tokio::fs::remove_file(format!("{}-shm", path.display())).await;
    }

    #[tokio::test]
    async fn admission_and_audit_outbox_rollback_together() {
        let path = database_path("authority-atomic");
        let store = AuthorityStateStore::open(&path).await.expect("open store");
        let duplicate = event("duplicate-event", "existing.event");
        sqlx::query(
            r#"
            INSERT INTO domain_event_queue
                (event_id, created_at_unix_ms, event_type, trace_id, envelope)
            VALUES (?, ?, ?, ?, ?)
            "#,
        )
        .bind(&duplicate.event_id)
        .bind(as_i64(duplicate.created_at_unix_ms))
        .bind(&duplicate.event_type)
        .bind(&duplicate.trace_id)
        .bind(&duplicate.envelope)
        .execute(&store.pool)
        .await
        .expect("seed duplicate event");

        let candidate = grant("token-atomic", 10, 1);
        store
            .admit_grant(&candidate, "signature-atomic", &duplicate)
            .await
            .expect_err("duplicate audit event must abort admission");

        let identity_count: i64 =
            sqlx::query_scalar("SELECT COUNT(*) FROM capability_token_identity")
                .fetch_one(&store.pool)
                .await
                .expect("count identities");
        let state_count: i64 = sqlx::query_scalar("SELECT COUNT(*) FROM capability_grant_state")
            .fetch_one(&store.pool)
            .await
            .expect("count states");
        let floor_count: i64 = sqlx::query_scalar("SELECT COUNT(*) FROM capability_sequence_floor")
            .fetch_one(&store.pool)
            .await
            .expect("count floors");
        assert_eq!((identity_count, state_count, floor_count), (0, 0, 0));

        let retry = event("admission-event", "capability.grant.cached");
        assert!(matches!(
            store
                .admit_grant(&candidate, "signature-atomic", &retry)
                .await
                .expect("retry admission"),
            GrantAdmission::New { .. }
        ));
        store.pool.close().await;
        remove_database(&path).await;
    }

    #[tokio::test]
    async fn bounded_busy_timeout_allows_short_writer_contention() {
        let path = database_path("authority-contention");
        let first = AuthorityStateStore::open(&path)
            .await
            .expect("open first store");
        let second = AuthorityStateStore::open(&path)
            .await
            .expect("open second store");
        let mut lock = first.pool.begin().await.expect("begin writer lock");
        sqlx::query(
            "INSERT INTO capability_sequence_floor (sequence_key, highest_sequence) VALUES ('lock-holder', 1)",
        )
        .execute(&mut *lock)
        .await
        .expect("acquire SQLite writer lock");

        let task = tokio::spawn(async move {
            let candidate = grant("token-contention", 11, 1);
            second
                .admit_grant(
                    &candidate,
                    "signature-contention",
                    &event("contention-event", "capability.grant.cached"),
                )
                .await
        });
        tokio::time::sleep(Duration::from_millis(100)).await;
        lock.rollback().await.expect("release writer lock");
        let admitted = tokio::time::timeout(Duration::from_secs(2), task)
            .await
            .expect("contended admission should finish within timeout")
            .expect("contended admission task should join")
            .expect("contended admission should succeed");
        assert!(matches!(admitted, GrantAdmission::New { .. }));

        first.pool.close().await;
        remove_database(&path).await;
    }

    #[tokio::test]
    async fn idempotent_retry_and_use_budget_survive_reopen() {
        let path = database_path("authority-reopen");
        let first = AuthorityStateStore::open(&path)
            .await
            .expect("open first store");
        let accepted = grant("token-current", 20, 1);
        let admission = event("admission-current", "capability.grant.cached");
        first
            .admit_grant(&accepted, "signature-current", &admission)
            .await
            .expect("admit current grant");
        first
            .consume_use(&accepted.token_id, crate::autonomy::unix_ms())
            .await
            .expect("consume only use");
        first.pool.close().await;

        let reopened = AuthorityStateStore::open(&path)
            .await
            .expect("reopen store");
        let retry_event = event("unused-retry-event", "capability.grant.cached");
        assert_eq!(
            reopened
                .admit_grant(&accepted, "signature-current", &retry_event)
                .await
                .expect("exact retry should be idempotent"),
            GrantAdmission::Idempotent {
                event_id: admission.event_id.clone()
            }
        );
        let event_count: i64 = sqlx::query_scalar(
            "SELECT COUNT(*) FROM domain_event_queue WHERE event_type = 'capability.grant.cached'",
        )
        .fetch_one(&reopened.pool)
        .await
        .expect("count admission events");
        assert_eq!(event_count, 1);
        let exhausted = reopened
            .consume_use(&accepted.token_id, crate::autonomy::unix_ms())
            .await
            .expect_err("spent use budget must survive restart");
        assert!(exhausted.to_string().contains("exhausted"));

        let rollback = grant("token-rollback", 19, 1);
        let rejected = reopened
            .admit_grant(
                &rollback,
                "signature-rollback",
                &event("rollback-event", "capability.grant.cached"),
            )
            .await
            .expect_err("sequence rollback must survive restart");
        assert!(rejected.to_string().contains("durable accepted sequence"));

        reopened.pool.close().await;
        remove_database(&path).await;
    }

    #[tokio::test]
    async fn revocation_and_compaction_preserve_restrictions() {
        let path = database_path("authority-revocation");
        let first = AuthorityStateStore::open(&path)
            .await
            .expect("open first store");
        let accepted = grant("token-revoked", 30, 3);
        first
            .admit_grant(
                &accepted,
                "signature-revoked",
                &event("admission-revoked", "capability.grant.cached"),
            )
            .await
            .expect("admit revocable grant");
        assert!(
            first
                .revoke_grant(
                    &accepted.token_id,
                    "signature-revoked",
                    crate::autonomy::unix_ms(),
                    "test revocation",
                    &event("revocation-event", "capability.grant.revoked"),
                )
                .await
                .expect("revoke grant")
        );
        first.pool.close().await;

        let reopened = AuthorityStateStore::open(&path)
            .await
            .expect("reopen store");
        let revoked = reopened
            .consume_use(&accepted.token_id, crate::autonomy::unix_ms())
            .await
            .expect_err("revocation must survive restart");
        assert!(revoked.to_string().contains("revoked"));
        let readmission = reopened
            .admit_grant(
                &accepted,
                "signature-revoked",
                &event("readmission-event", "capability.grant.cached"),
            )
            .await
            .expect_err("revoked grant must not reactivate");
        assert!(readmission.to_string().contains("durably revoked"));

        assert_eq!(
            reopened.compact_expired(u64::MAX).await.expect("compact"),
            1
        );
        let identity_count: i64 =
            sqlx::query_scalar("SELECT COUNT(*) FROM capability_token_identity")
                .fetch_one(&reopened.pool)
                .await
                .expect("count identities");
        let floor_count: i64 = sqlx::query_scalar("SELECT COUNT(*) FROM capability_sequence_floor")
            .fetch_one(&reopened.pool)
            .await
            .expect("count floors");
        let tombstone_count: i64 =
            sqlx::query_scalar("SELECT COUNT(*) FROM capability_revocation_tombstone")
                .fetch_one(&reopened.pool)
                .await
                .expect("count tombstones");
        assert_eq!((identity_count, floor_count, tombstone_count), (1, 1, 1));

        reopened.pool.close().await;
        remove_database(&path).await;
    }

    #[tokio::test]
    async fn operation_intent_and_use_rollback_together() {
        let path = database_path("operation-intent-atomic");
        let store = AuthorityStateStore::open(&path).await.expect("open store");
        let accepted = grant("token-intent-atomic", 40, 1);
        store
            .admit_grant(
                &accepted,
                "signature-intent-atomic",
                &event("intent-admission", "capability.grant.admitted"),
            )
            .await
            .expect("admit grant");
        let duplicate = event("duplicate-intent-event", "existing.event");
        sqlx::query(
            r#"
            INSERT INTO domain_event_queue
                (event_id, created_at_unix_ms, event_type, trace_id, envelope)
            VALUES (?, ?, ?, ?, ?)
            "#,
        )
        .bind(&duplicate.event_id)
        .bind(as_i64(duplicate.created_at_unix_ms))
        .bind(&duplicate.event_type)
        .bind(&duplicate.trace_id)
        .bind(&duplicate.envelope)
        .execute(&store.pool)
        .await
        .expect("seed duplicate event");

        store
            .consume_use_with_intent(
                "controller-1",
                "trace-atomic",
                &format!("sha256:{}", "1".repeat(64)),
                &accepted.token_id,
                "spawn_workload",
                "workload-1",
                crate::autonomy::unix_ms(),
                &duplicate,
            )
            .await
            .expect_err("duplicate receipt must roll back use and intent");

        let uses: i64 =
            sqlx::query_scalar("SELECT uses FROM capability_grant_state WHERE token_id = ?")
                .bind(&accepted.token_id)
                .fetch_one(&store.pool)
                .await
                .expect("read uses");
        let intents: i64 = sqlx::query_scalar("SELECT COUNT(*) FROM capability_operation_intent")
            .fetch_one(&store.pool)
            .await
            .expect("count intents");
        assert_eq!((uses, intents), (0, 0));

        store.pool.close().await;
        remove_database(&path).await;
    }

    #[tokio::test]
    async fn operation_intent_retry_is_idempotent_and_collision_safe() {
        let path = database_path("operation-intent-idempotent");
        let store = AuthorityStateStore::open(&path).await.expect("open store");
        let accepted = grant("token-intent-retry", 41, 2);
        store
            .admit_grant(
                &accepted,
                "signature-intent-retry",
                &event("intent-retry-admission", "capability.grant.admitted"),
            )
            .await
            .expect("admit grant");
        let digest = format!("sha256:{}", "2".repeat(64));
        let first_event = event("operation-intent-first", "workload.spawn.intent");
        assert_eq!(
            store
                .consume_use_with_intent(
                    "controller-1",
                    "trace-retry",
                    &digest,
                    &accepted.token_id,
                    "spawn_workload",
                    "workload-1",
                    crate::autonomy::unix_ms(),
                    &first_event,
                )
                .await
                .expect("commit first intent"),
            OperationIntentCommit::New {
                event_id: first_event.event_id.clone(),
                consumed_use: 1,
            }
        );
        assert_eq!(
            store
                .consume_use_with_intent(
                    "controller-1",
                    "trace-retry",
                    &digest,
                    &accepted.token_id,
                    "spawn_workload",
                    "workload-1",
                    crate::autonomy::unix_ms(),
                    &event("operation-intent-unused", "workload.spawn.intent"),
                )
                .await
                .expect("exact retry"),
            OperationIntentCommit::Idempotent {
                event_id: first_event.event_id.clone(),
                consumed_use: 1,
            }
        );
        let collision = store
            .consume_use_with_intent(
                "controller-1",
                "trace-retry",
                &format!("sha256:{}", "3".repeat(64)),
                &accepted.token_id,
                "spawn_workload",
                "workload-1",
                crate::autonomy::unix_ms(),
                &event("operation-intent-collision", "workload.spawn.intent"),
            )
            .await
            .expect_err("altered retry must be rejected");
        assert!(collision.to_string().contains("collides"));

        let uses: i64 =
            sqlx::query_scalar("SELECT uses FROM capability_grant_state WHERE token_id = ?")
                .bind(&accepted.token_id)
                .fetch_one(&store.pool)
                .await
                .expect("read uses");
        let intent_events: i64 = sqlx::query_scalar(
            "SELECT COUNT(*) FROM domain_event_queue WHERE event_type = 'workload.spawn.intent'",
        )
        .fetch_one(&store.pool)
        .await
        .expect("count intent events");
        assert_eq!((uses, intent_events), (1, 1));

        store.pool.close().await;
        remove_database(&path).await;
    }

    #[tokio::test]
    async fn concurrent_last_use_commits_exactly_one_intent() {
        let path = database_path("operation-intent-concurrent");
        let first = AuthorityStateStore::open(&path)
            .await
            .expect("open first store");
        let second = AuthorityStateStore::open(&path)
            .await
            .expect("open second store");
        let accepted = grant("token-intent-last", 42, 1);
        first
            .admit_grant(
                &accepted,
                "signature-intent-last",
                &event("intent-last-admission", "capability.grant.admitted"),
            )
            .await
            .expect("admit grant");
        let token_a = accepted.token_id.clone();
        let token_b = accepted.token_id.clone();
        let task_a = tokio::spawn(async move {
            first
                .consume_use_with_intent(
                    "controller-1",
                    "trace-a",
                    &format!("sha256:{}", "4".repeat(64)),
                    &token_a,
                    "status_workload",
                    "workload-1",
                    crate::autonomy::unix_ms(),
                    &event("intent-a", "workload.status.intent"),
                )
                .await
        });
        let task_b = tokio::spawn(async move {
            second
                .consume_use_with_intent(
                    "controller-1",
                    "trace-b",
                    &format!("sha256:{}", "5".repeat(64)),
                    &token_b,
                    "status_workload",
                    "workload-1",
                    crate::autonomy::unix_ms(),
                    &event("intent-b", "workload.status.intent"),
                )
                .await
        });
        let outcomes = [task_a.await.expect("join a"), task_b.await.expect("join b")];
        assert_eq!(outcomes.iter().filter(|result| result.is_ok()).count(), 1);
        assert_eq!(outcomes.iter().filter(|result| result.is_err()).count(), 1);

        let reopened = AuthorityStateStore::open(&path)
            .await
            .expect("reopen store");
        let uses: i64 =
            sqlx::query_scalar("SELECT uses FROM capability_grant_state WHERE token_id = ?")
                .bind(&accepted.token_id)
                .fetch_one(&reopened.pool)
                .await
                .expect("read uses");
        let intents: i64 = sqlx::query_scalar("SELECT COUNT(*) FROM capability_operation_intent")
            .fetch_one(&reopened.pool)
            .await
            .expect("count intents");
        assert_eq!((uses, intents), (1, 1));

        reopened.pool.close().await;
        remove_database(&path).await;
    }

    #[tokio::test]
    async fn exact_retry_survives_later_revocation_without_new_use() {
        let path = database_path("operation-intent-revoked-retry");
        let store = AuthorityStateStore::open(&path).await.expect("open store");
        let accepted = grant("token-intent-revoked", 43, 2);
        store
            .admit_grant(
                &accepted,
                "signature-intent-revoked",
                &event("intent-revoked-admission", "capability.grant.admitted"),
            )
            .await
            .expect("admit grant");
        let digest = format!("sha256:{}", "6".repeat(64));
        let first_event = event("intent-before-revocation", "workload.status.intent");
        store
            .consume_use_with_intent(
                "controller-1",
                "trace-before-revocation",
                &digest,
                &accepted.token_id,
                "status_workload",
                "workload-1",
                crate::autonomy::unix_ms(),
                &first_event,
            )
            .await
            .expect("commit intent before revocation");
        assert!(
            store
                .revoke_grant(
                    &accepted.token_id,
                    "signature-intent-revoked",
                    crate::autonomy::unix_ms(),
                    "test revocation after intent",
                    &event("intent-revocation", "capability.grant.revoked"),
                )
                .await
                .expect("revoke grant")
        );
        assert_eq!(
            store
                .consume_use_with_intent(
                    "controller-1",
                    "trace-before-revocation",
                    &digest,
                    &accepted.token_id,
                    "status_workload",
                    "workload-1",
                    crate::autonomy::unix_ms(),
                    &event("unused-after-revocation", "workload.status.intent"),
                )
                .await
                .expect("exact retry should return original intent"),
            OperationIntentCommit::Idempotent {
                event_id: first_event.event_id.clone(),
                consumed_use: 1,
            }
        );
        let denied = store
            .consume_use_with_intent(
                "controller-1",
                "trace-new-after-revocation",
                &format!("sha256:{}", "7".repeat(64)),
                &accepted.token_id,
                "status_workload",
                "workload-1",
                crate::autonomy::unix_ms(),
                &event("new-after-revocation", "workload.status.intent"),
            )
            .await
            .expect_err("new intent after revocation must be denied");
        assert!(denied.to_string().contains("revoked"));

        let uses: i64 =
            sqlx::query_scalar("SELECT uses FROM capability_grant_state WHERE token_id = ?")
                .bind(&accepted.token_id)
                .fetch_one(&store.pool)
                .await
                .expect("read uses");
        assert_eq!(uses, 1);

        store.pool.close().await;
        remove_database(&path).await;
    }
}
