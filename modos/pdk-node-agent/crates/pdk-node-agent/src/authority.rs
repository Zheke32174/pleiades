use std::path::Path;

use anyhow::{Context, Result, bail};
use pdk_protocol::v1::CapabilityGrantPayload;
use sqlx::{Row, SqlitePool, sqlite::SqlitePoolOptions};

#[derive(Clone)]
pub struct AuthorityStateStore {
    pool: SqlitePool,
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
            CREATE TABLE IF NOT EXISTS capability_grant_state (
                token_id TEXT PRIMARY KEY,
                signature_base64 TEXT NOT NULL,
                sequence_key TEXT NOT NULL,
                grant_sequence INTEGER NOT NULL,
                max_uses INTEGER NOT NULL,
                uses INTEGER NOT NULL DEFAULT 0,
                expires_at_unix_ms INTEGER NOT NULL,
                FOREIGN KEY(sequence_key)
                    REFERENCES capability_sequence_floor(sequence_key)
            )
            "#,
        )
        .execute(&pool)
        .await
        .context("creating durable capability grant state")?;
        sqlx::query(
            "CREATE INDEX IF NOT EXISTS capability_grant_expiry_idx ON capability_grant_state(expires_at_unix_ms)",
        )
        .execute(&pool)
        .await
        .context("creating capability expiry index")?;
        Ok(Self { pool })
    }

    pub async fn persist_grant(
        &self,
        grant: &CapabilityGrantPayload,
        signature_base64: &str,
    ) -> Result<()> {
        let sequence_key = sequence_key(grant);
        let mut transaction = self
            .pool
            .begin()
            .await
            .context("starting capability grant transaction")?;

        if let Some(row) = sqlx::query(
            "SELECT signature_base64 FROM capability_grant_state WHERE token_id = ?",
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
            transaction
                .commit()
                .await
                .context("committing idempotent capability grant transaction")?;
            return Ok(());
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
            INSERT INTO capability_grant_state
                (token_id, signature_base64, sequence_key, grant_sequence, max_uses, uses, expires_at_unix_ms)
            VALUES (?, ?, ?, ?, ?, 0, ?)
            "#,
        )
        .bind(&grant.token_id)
        .bind(signature_base64)
        .bind(&sequence_key)
        .bind(as_i64(grant.grant_sequence))
        .bind(i64::from(grant.max_uses))
        .bind(as_i64(grant.expires_at_unix_ms))
        .execute(&mut *transaction)
        .await
        .context("persisting durable capability grant state")?;

        transaction
            .commit()
            .await
            .context("committing durable capability grant state")?;
        Ok(())
    }

    pub async fn consume_use(&self, token_id: &str, now_unix_ms: u64) -> Result<u32> {
        let mut transaction = self
            .pool
            .begin()
            .await
            .context("starting capability use transaction")?;
        let row = sqlx::query(
            r#"
            SELECT uses, max_uses, expires_at_unix_ms
            FROM capability_grant_state
            WHERE token_id = ?
            "#,
        )
        .bind(token_id)
        .fetch_optional(&mut *transaction)
        .await
        .context("reading durable capability use state")?
        .context("capability token has no durable grant state")?;

        let uses: i64 = row.try_get("uses")?;
        let max_uses: i64 = row.try_get("max_uses")?;
        let expires_at_unix_ms: i64 = row.try_get("expires_at_unix_ms")?;
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

        let consumed = uses.saturating_add(1);
        transaction
            .commit()
            .await
            .context("committing durable capability use")?;
        Ok(consumed.try_into().unwrap_or(u32::MAX))
    }
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

    #[tokio::test]
    async fn sequence_floor_and_use_budget_survive_reopen() {
        let path = std::env::temp_dir().join(format!(
            "pdk-authority-continuity-{}.sqlite",
            Uuid::new_v4()
        ));
        let first = AuthorityStateStore::open(&path).await.expect("open first store");
        let accepted = grant("token-current", 20, 1);
        first
            .persist_grant(&accepted, "signature-current")
            .await
            .expect("persist current grant");
        first
            .consume_use(&accepted.token_id, crate::autonomy::unix_ms())
            .await
            .expect("consume only use");
        first.pool.close().await;

        let reopened = AuthorityStateStore::open(&path).await.expect("reopen store");
        let exhausted = reopened
            .consume_use(&accepted.token_id, crate::autonomy::unix_ms())
            .await
            .expect_err("spent use budget must survive restart");
        assert!(exhausted.to_string().contains("exhausted"));

        let rollback = grant("token-rollback", 19, 1);
        let rejected = reopened
            .persist_grant(&rollback, "signature-rollback")
            .await
            .expect_err("sequence rollback must survive restart");
        assert!(rejected.to_string().contains("durable accepted sequence"));

        reopened.pool.close().await;
        let _ = tokio::fs::remove_file(&path).await;
        let _ = tokio::fs::remove_file(format!("{}-wal", path.display())).await;
        let _ = tokio::fs::remove_file(format!("{}-shm", path.display())).await;
    }
}
