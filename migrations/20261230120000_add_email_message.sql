-- migrate:up
-- FIN-307: a postafiókból lehúzott levelek. A nyers levél a Garage-ban van, a belőle lett
-- dokumentumok (melléklet vagy a levél törzse) a raw_document-ben, `email` forrástípussal.
-- Ami a feladó-ellenőrzésen elbukik, ide nem kerül: a postafiók Karantén mappájában marad.
create table bronze.email_message (
  id            uuid primary key default gen_random_uuid(),
  sha256        text not null unique,
  object_key    text not null,
  message_id    text,
  from_address  text not null,
  to_addresses  text[] not null default '{}',
  subject       text,
  sent_at       timestamptz,
  received_at   timestamptz not null,
  auth          jsonb not null,
  document_ids  uuid[] not null default '{}',
  ingested_at   timestamptz not null default now()
);

create trigger email_message_append_only
before update or delete or truncate on bronze.email_message
for each statement execute function bronze.forbid_change();

-- migrate:down
-- Szándékosan üres: a bronz adat nem görgethető vissza.
