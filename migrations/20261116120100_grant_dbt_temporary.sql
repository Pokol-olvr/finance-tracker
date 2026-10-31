-- migrate:up
-- A dbt unit tesztjei ideiglenes táblákat használnak.
grant temporary on database finance to dbt_runner;

-- migrate:down
revoke temporary on database finance from dbt_runner;
