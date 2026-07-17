use std::path::Path;

use anyhow::{Context, Result};
use pdk_crypto::{sign_domain_event, LoadedSigningKey};
use pdk_protocol::{v1::{DomainEventPayload, SignedDomainEvent}, PROTOCOL_VERSION};
use prost::Message;
use serde::Serialize;
use sqlx::{sqlite::SqlitePoolOptions, Row, SqlitePool};
use uuid::Uuid;

use crate::autonomy::unix_ms;

#[derive(Clone)]
pub struct OfflineAuditBuffer {
    pool: SqlitePool,
    domain_id: String,
    node_id: String,
    signing_key: std::sync::Arc<LoadedSigningKey>,
}

impl OfflineAuditBuffer {
    pub async fn open(
        path: &Path,
        domain_id: impl Into<String>,
        node_id: impl Into<String>,
        signing_key: std::sync::Arc<LoadedSigningKey>,
    ) -> Result<Self> {
        if let Some(parent) = path.parent() {
            tokio::fs::create_dir_all(parent)
                .await
                .with_context(|| format!("creating audit database directory {}", parent.display()))?;
        }
        let url = format!("sqlite://{}?mode=rwc", path.display());
        let pool = SqlitePoolOptions::new()
            .max_connections(1)
            .connect(&url)
            .await
            .with_context(|| format!("opening SQLite audit buffer {}", path.display()))?;
        sqlx::query("PRAGMA journal_mode = WAL")
            .execute(&pool)
            .await
            .context("enabling SQLite WAL mode")?;
        sqlx::query("PRAGMA synchronous = FULL")
            .execute(&pool)
            .await
            .context("setting SQLite synchronous=FULL")?;
        sqlx::query("PRAGMA foreign_keys = ON")
            .execute(&pool)
            .await
            .context("enabling SQLite foreign keys")?;
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
        .context("creating domain event queue")?;
        Ok(Self {
            pool,
            domain_id: domain_id.into(),
            node_id: node_id.into(),
            signing_key,
        })
    }

    pub async fn queue_event<T: Serialize>(
        &self,
        event_type: &str,
        trace_id: &str,
        payload: &T,
    ) -> Result<String> {
        let event_id = Uuid::new_v4().to_string();
        let created_at_unix_ms = unix_ms();
        let payload_json = serde_json::to_vec(payload).context("serializing domain event payload")?;
        let signed = sign_domain_event(
            DomainEventPayload {
                protocol_version: PROTOCOL_VERSION,
                event_id: event_id.clone(),
                domain_id: self.domain_id.clone(),
                source_node_id: self.node_id.clone(),
                created_at_unix_ms,
                trace_id: trace_id.to_owned(),
                event_type: event_type.to_owned(),
                payload_json,
            },
            &self.signing_key,
        );
        let envelope = signed.encode_to_vec();
        sqlx::query(
            r#"
            INSERT INTO domain_event_queue
                (event_id, created_at_unix_ms, event_type, trace_id, envelope)
            VALUES (?, ?, ?, ?, ?)
            "#,
        )
        .bind(&event_id)
        .bind(as_i64(created_at_unix_ms))
        .bind(event_type)
        .bind(trace_id)
        .bind(envelope)
        .execute(&self.pool)
        .await
        .context("persisting signed domain event")?;
        Ok(event_id)
    }

    pub async fn next(&self) -> Result<Option<SignedDomainEvent>> {
        let row = sqlx::query(
            "SELECT envelope FROM domain_event_queue ORDER BY sequence ASC LIMIT 1",
        )
        .fetch_optional(&self.pool)
        .await
        .context("reading oldest audit event")?;
        row.map(|row| {
            let bytes: Vec<u8> = row.try_get("envelope")?;
            SignedDomainEvent::decode(bytes.as_slice()).context("decoding queued domain event")
        })
        .transpose()
    }

    pub async fn acknowledge(&self, event_id: &str) -> Result<bool> {
        let result = sqlx::query("DELETE FROM domain_event_queue WHERE event_id = ?")
            .bind(event_id)
            .execute(&self.pool)
            .await
            .context("deleting cryptographically acknowledged event")?;
        Ok(result.rows_affected() == 1)
    }

    pub async fn mark_attempt_failed(&self, event_id: &str, error: &str) -> Result<()> {
        sqlx::query(
            "UPDATE domain_event_queue SET attempts = attempts + 1, last_error = ? WHERE event_id = ?",
        )
        .bind(truncate(error, 2_048))
        .bind(event_id)
        .execute(&self.pool)
        .await
        .context("recording audit reconciliation failure")?;
        Ok(())
    }

    pub async fn pending_count(&self) -> Result<u64> {
        let row = sqlx::query("SELECT COUNT(*) AS count FROM domain_event_queue")
            .fetch_one(&self.pool)
            .await
            .context("counting pending audit events")?;
        let count: i64 = row.try_get("count")?;
        Ok(count.max(0) as u64)
    }
}

fn truncate(value: &str, max_chars: usize) -> String {
    value.chars().take(max_chars).collect()
}

fn as_i64(value: u64) -> i64 {
    value.min(i64::MAX as u64) as i64
}
