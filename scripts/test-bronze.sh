#!/usr/bin/env bash
# Ellenőrzi a bronz réteg hozzáfűzés-védelmét és a szerepkörök jogait.
# Egyetlen tranzakcióban fut, amely a végén visszagörgetődik, így nem hagy adatot.
set -euo pipefail
source "$(dirname "$0")/lib.sh"

compose exec -T postgres psql -v ON_ERROR_STOP=1 -q -o /dev/null -U postgres -d finance <<'SQL'
begin;

create function pg_temp.expect_error(who text, stmt text, expected_state text) returns void
language plpgsql as $$
declare
  actual_state text;
begin
  begin
    execute format('set local role %I', who);
    execute stmt;
  exception when others then
    get stacked diagnostics actual_state = returned_sqlstate;
    if actual_state <> expected_state then
      raise exception 'HIBA: % / %: % helyett % jött', who, stmt, expected_state, actual_state;
    end if;
    return;
  end;
  raise exception 'HIBA: % / % nem adott hibát', who, stmt;
end $$;

-- A beszúrás app_writerként működik.
set local role app_writer;
insert into bronze.raw_document (sha256, object_key, source_type, uploaded_by, uploaded_at)
values (repeat('a', 64), 'raw/teszt.jpg', 'photo', 'teszt', now());
insert into bronze.extraction (document_id, model_name, model_version, prompt_version, payload)
select id, 'teszt', '1', '1', '{}' from bronze.raw_document where sha256 = repeat('a', 64);
insert into bronze.manual_entry (entered_by, kind, amount, occurred_on)
values ('teszt', 'expense', 18450.00, current_date);
insert into bronze.receipt_parse (group_id, extraction_ids, parser_version, status, payload, checks)
values (gen_random_uuid(), '{}', 'teszt', 'ok', '{}', '{}');
reset role;

-- Ugyanaz a fájl-hash másodszorra nem szúrható be.
select pg_temp.expect_error('app_writer', $q$
  insert into bronze.raw_document (sha256, object_key, source_type, uploaded_by, uploaded_at)
  values (repeat('a', 64), 'raw/masolat.jpg', 'photo', 'teszt', now())
$q$, '23505');

-- UPDATE, DELETE és TRUNCATE senkinek: a trigger a tulajdonost és a superusert is megállítja,
-- a többi szerepkörnek jogosultsága sincs.
select pg_temp.expect_error(who, stmt, state)
from (values
  ('finance_owner', 'P0001'), ('postgres', 'P0001'),
  ('app_writer', '42501'), ('dbt_runner', '42501'), ('mb_reader', '42501')
) as roles (who, state)
cross join (values ('raw_document'), ('extraction'), ('manual_entry'), ('receipt_parse'), ('review_decision')) as tables (name)
cross join lateral (values
  (format('update bronze.%I set id = id', name)),
  (format('delete from bronze.%I', name)),
  (format('truncate bronze.%I cascade', name))
) as stmts (stmt);

-- A dbt olvassa a bronzt, és építi a silvert és a goldot.
set local role dbt_runner;
select count(*) from bronze.raw_document;
create table silver.jog_teszt (n int);
create table gold.jog_teszt (n int);
reset role;

-- A Metabase csak a goldot látja.
set local role mb_reader;
select count(*) from gold.jog_teszt;
reset role;
select pg_temp.expect_error('mb_reader', 'select 1 from silver.jog_teszt', '42501');
select pg_temp.expect_error('mb_reader', 'select 1 from bronze.raw_document', '42501');
select pg_temp.expect_error('mb_reader', 'select 1 from public.schema_migrations', '42501');

rollback;
SQL

echo "A bronz réteg ellenőrzése sikeres."
