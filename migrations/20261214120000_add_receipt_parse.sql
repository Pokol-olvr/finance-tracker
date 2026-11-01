-- migrate:up
alter table bronze.raw_document add column group_id uuid;
alter table bronze.raw_document add column page_no smallint not null default 1;
alter table bronze.raw_document add column page_count smallint not null default 1;

create table bronze.receipt_parse (
  id             uuid primary key default gen_random_uuid(),
  group_id       uuid not null,
  extraction_ids uuid[] not null,
  parser_version text not null,
  status         text not null check (status in ('ok', 'review', 'unparsed')),
  payload        jsonb not null,
  checks         jsonb not null,
  created_at     timestamptz not null default now(),
  unique (group_id, parser_version)
);

create trigger receipt_parse_append_only
before update or delete or truncate on bronze.receipt_parse
for each statement execute function bronze.forbid_change();

-- migrate:down
-- Szándékosan üres: a bronz adat nem görgethető vissza.
