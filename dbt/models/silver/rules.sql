-- Szabályonként a legutóbbi esemény; a kikapcsolt szabály a bronzban megmarad.
with latest as (
  select distinct on (rule_id)
    rule_id,
    rule_type,
    pattern,
    target_value as target,
    active
  from {{ source('bronze', 'rule_event') }}
  order by rule_id, created_at desc, id
),

first_seen as (
  select
    rule_id,
    min(created_at) as created_at
  from {{ source('bronze', 'rule_event') }}
  group by rule_id
)

select
  latest.rule_id,
  latest.rule_type,
  translate(upper(latest.pattern), 'ÁÉÍÓÖŐÚÜŰ', 'AEIOOOUUU') as pattern,
  latest.target,
  first_seen.created_at
from latest
inner join first_seen on latest.rule_id = first_seen.rule_id
where latest.active
