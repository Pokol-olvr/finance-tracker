-- migrate:up
create schema bronze;

create table bronze.raw_document (
  id            uuid primary key default gen_random_uuid(),
  sha256        text not null unique,
  object_key    text not null,
  source_type   text not null check (source_type in ('photo', 'pdf', 'email', 'payslip', 'statement')),
  uploaded_by   text not null,
  uploaded_at   timestamptz not null,
  purchase_date date,
  payer         text,
  tags          text[] not null default '{}',
  ingested_at   timestamptz not null default now()
);

create table bronze.extraction (
  id             uuid primary key default gen_random_uuid(),
  document_id    uuid not null references bronze.raw_document (id),
  model_name     text not null,
  model_version  text not null,
  prompt_version text not null,
  payload        jsonb not null,
  created_at     timestamptz not null default now()
);

create table bronze.manual_entry (
  id          uuid primary key default gen_random_uuid(),
  entered_by  text not null,
  entered_at  timestamptz not null default now(),
  kind        text not null check (kind in ('expense', 'income', 'transfer')),
  amount      numeric(12, 2) not null,
  currency    char(3) not null default 'HUF' check (currency ~ '^[A-Z]{3}$'),
  occurred_on date not null,
  payer       text,
  tags        text[] not null default '{}',
  note        text
);

create function bronze.forbid_change() returns trigger
language plpgsql as $$
begin
  raise exception 'A bronz réteg csak hozzáfűzhető (%)', tg_table_name;
end $$;

-- Utasításszintű trigger: a TRUNCATE-et is elkapja, és nulla soros módosításnál is hibát ad.
create trigger raw_document_append_only
before update or delete or truncate on bronze.raw_document
for each statement execute function bronze.forbid_change();

create trigger extraction_append_only
before update or delete or truncate on bronze.extraction
for each statement execute function bronze.forbid_change();

create trigger manual_entry_append_only
before update or delete or truncate on bronze.manual_entry
for each statement execute function bronze.forbid_change();

grant usage on schema bronze to app_writer, dbt_runner;
grant select, insert on all tables in schema bronze to app_writer;
grant select on all tables in schema bronze to dbt_runner;

alter default privileges in schema bronze grant select, insert on tables to app_writer;
alter default privileges in schema bronze grant select on tables to dbt_runner;

-- migrate:down
-- Szándékosan üres: a bronz adat nem görgethető vissza.
