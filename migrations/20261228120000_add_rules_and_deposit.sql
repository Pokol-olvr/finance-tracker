-- migrate:up
create table bronze.rule_event (
  id           uuid primary key,
  rule_id      uuid not null,
  rule_type    text not null check (rule_type in ('category', 'store')),
  pattern      text not null,
  target_value text not null,
  active       boolean not null,
  created_by   text not null,
  created_at   timestamptz not null,
  ingested_at  timestamptz not null default now()
);

create trigger rule_event_append_only
before update or delete or truncate on bronze.rule_event
for each statement execute function bronze.forbid_change();

create table bronze.deposit_correction (
  id          uuid primary key,
  kind        text not null check (kind in ('adjust', 'reset')),
  amount      numeric(12, 2),
  created_by  text not null,
  created_at  timestamptz not null,
  ingested_at timestamptz not null default now()
);

create trigger deposit_correction_append_only
before update or delete or truncate on bronze.deposit_correction
for each statement execute function bronze.forbid_change();

-- A worker a várható betétdíjat visszatölti a webappnak, ezért olvashatja a goldot.
grant usage on schema gold to app_writer;
alter default privileges for role dbt_runner in schema gold grant select on tables to app_writer;

-- migrate:down
-- Szándékosan üres: a bronz adat nem görgethető vissza.
