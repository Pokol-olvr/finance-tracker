-- migrate:up
create table bronze.review_decision (
  id          uuid primary key,
  group_id    uuid not null,
  parse_id    uuid not null references bronze.receipt_parse (id),
  decision    text not null check (decision in ('approved', 'corrected', 'rejected')),
  corrected   jsonb,
  decided_by  text not null,
  decided_at  timestamptz not null,
  ingested_at timestamptz not null default now()
);

create trigger review_decision_append_only
before update or delete or truncate on bronze.review_decision
for each statement execute function bronze.forbid_change();

-- migrate:down
-- Szándékosan üres: a bronz adat nem görgethető vissza.
