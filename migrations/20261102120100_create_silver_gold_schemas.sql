-- migrate:up
create schema silver;
create schema gold;

grant usage, create on schema silver to dbt_runner;
grant usage, create on schema gold to dbt_runner;
grant usage on schema gold to mb_reader;

-- A goldot a dbt_runner építi, ezért az ő új tábláira kell a Metabase olvasási joga.
alter default privileges for role dbt_runner in schema gold grant select on tables to mb_reader;

-- migrate:down
drop schema gold;
drop schema silver;
