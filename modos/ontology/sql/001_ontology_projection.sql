-- Non-authoritative Pleiades ontology read projection.
-- Canonical compilation, review, signing, and promotion occur outside Postgres.

create schema if not exists ontology_projection;

revoke all on schema ontology_projection from public;
revoke all on schema ontology_projection from anon;
revoke all on schema ontology_projection from authenticated;
grant usage on schema ontology_projection to anon, authenticated;

create table if not exists ontology_projection.snapshots (
    snapshot_digest text primary key check (snapshot_digest ~ '^sha256:[0-9a-f]{64}$'),
    mind_id text not null,
    schema_version text not null,
    source_snapshot_digest text not null check (source_snapshot_digest ~ '^sha256:[0-9a-f]{64}$'),
    closure_receipt_digest text not null check (closure_receipt_digest ~ '^sha256:[0-9a-f]{64}$'),
    payload jsonb not null
);

create table if not exists ontology_projection.objects (
    snapshot_digest text not null references ontology_projection.snapshots(snapshot_digest) on delete cascade,
    object_id text not null,
    kind text not null,
    generation bigint not null check (generation >= 1),
    payload jsonb not null,
    primary key (snapshot_digest, object_id)
);

create table if not exists ontology_projection.relations (
    snapshot_digest text not null references ontology_projection.snapshots(snapshot_digest) on delete cascade,
    source_ref text not null,
    relation_type text not null,
    target_ref text not null,
    attributes jsonb not null default '{}'::jsonb,
    primary key (snapshot_digest, source_ref, relation_type, target_ref, attributes)
);

alter table ontology_projection.snapshots enable row level security;
alter table ontology_projection.objects enable row level security;
alter table ontology_projection.relations enable row level security;

revoke all on all tables in schema ontology_projection from public, anon, authenticated;
grant select on ontology_projection.snapshots to anon, authenticated;
grant select on ontology_projection.objects to anon, authenticated;
grant select on ontology_projection.relations to anon, authenticated;

create policy ontology_projection_snapshots_read
    on ontology_projection.snapshots for select
    to anon, authenticated using (true);
create policy ontology_projection_objects_read
    on ontology_projection.objects for select
    to anon, authenticated using (true);
create policy ontology_projection_relations_read
    on ontology_projection.relations for select
    to anon, authenticated using (true);

comment on schema ontology_projection is
    'Derived Pleiades read projection. Never a canonical ontology or write-back authority.';
