#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUTHORITY = ROOT / "modos/pdk-node-agent/crates/pdk-node-agent/src/authority.rs"
SYSTEMD = ROOT / "modos/pdk-node-agent/crates/pdk-node-agent/src/runtime/systemd.rs"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one source match, found {count}")
    return text.replace(old, new, 1)


authority = AUTHORITY.read_text(encoding="utf-8")
if "OperationIntentCommit" in authority or "capability_operation_intent" in authority:
    raise SystemExit("authority transformation already appears to be applied")

authority = replace_once(
    authority,
    '''#[derive(Clone, Debug, Eq, PartialEq)]
pub enum GrantAdmission {
    New { event_id: String },
    Recovered { event_id: String },
    Idempotent { event_id: String },
}
''',
    '''#[derive(Clone, Debug, Eq, PartialEq)]
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
            Self::New { consumed_use, .. } | Self::Idempotent { consumed_use, .. } => {
                *consumed_use
            }
        }
    }

    pub fn replayed(&self) -> bool {
        matches!(self, Self::Idempotent { .. })
    }
}
''',
    "operation intent enum",
)

authority = replace_once(
    authority,
    '''        .execute(&pool)
        .await
        .context("creating capability revocation tombstones")?;
        sqlx::query(
            "CREATE INDEX IF NOT EXISTS capability_grant_expiry_idx ON capability_grant_state(expires_at_unix_ms)",
        )
''',
    '''        .execute(&pool)
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
''',
    "operation intent table",
)

old_consume = '''    pub async fn consume_use(&self, token_id: &str, now_unix_ms: u64) -> Result<u32> {
        let mut transaction = self
            .pool
            .begin()
            .await
            .context("starting capability use transaction")?;
        acquire_authority_write_fence(&mut transaction).await?;
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

        let consumed = uses.saturating_add(1);
        transaction
            .commit()
            .await
            .context("committing durable capability use")?;
        Ok(consumed.try_into().unwrap_or(u32::MAX))
    }
'''

new_consume = '''    #[allow(clippy::too_many_arguments)]
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
'''

authority = replace_once(authority, old_consume, new_consume, "consume use method")

tests = r'''

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

        let uses: i64 = sqlx::query_scalar(
            "SELECT uses FROM capability_grant_state WHERE token_id = ?",
        )
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

        let uses: i64 = sqlx::query_scalar(
            "SELECT uses FROM capability_grant_state WHERE token_id = ?",
        )
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
        let first = AuthorityStateStore::open(&path).await.expect("open first store");
        let second = AuthorityStateStore::open(&path).await.expect("open second store");
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

        let reopened = AuthorityStateStore::open(&path).await.expect("reopen store");
        let uses: i64 = sqlx::query_scalar(
            "SELECT uses FROM capability_grant_state WHERE token_id = ?",
        )
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

        let uses: i64 = sqlx::query_scalar(
            "SELECT uses FROM capability_grant_state WHERE token_id = ?",
        )
        .bind(&accepted.token_id)
        .fetch_one(&store.pool)
        .await
        .expect("read uses");
        assert_eq!(uses, 1);

        store.pool.close().await;
        remove_database(&path).await;
    }
'''

if not authority.endswith("    }\n}\n"):
    raise SystemExit("authority test module ending changed unexpectedly")
authority = authority[:-3] + tests + "\n    }\n}\n"
AUTHORITY.write_text(authority, encoding="utf-8")

systemd = SYSTEMD.read_text(encoding="utf-8")
if "intent: None" in systemd:
    raise SystemExit("systemd receipt transformation already appears applied")
systemd = replace_once(
    systemd,
    '''            observed_at_unix_ms: crate::autonomy::unix_ms(),
            detail: format!("systemd ActiveState={active_state}, SubState={sub_state}"),
        })
''',
    '''            observed_at_unix_ms: crate::autonomy::unix_ms(),
            detail: format!("systemd ActiveState={active_state}, SubState={sub_state}"),
            intent: None,
        })
''',
    "systemd status receipt",
)
systemd = replace_once(
    systemd,
    '''            observed_at_unix_ms: crate::autonomy::unix_ms(),
            detail: format!("stop requested through systemd D-Bus: {reason}"),
        })
''',
    '''            observed_at_unix_ms: crate::autonomy::unix_ms(),
            detail: format!("stop requested through systemd D-Bus: {reason}"),
            intent: None,
        })
''',
    "systemd stop receipt",
)
SYSTEMD.write_text(systemd, encoding="utf-8")
