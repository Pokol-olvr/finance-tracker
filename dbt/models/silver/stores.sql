-- Adószámonként egy bolt: a boltszabály neve, különben a legkorábbi dokumentumé.
with seen as (
  select distinct on (tax_number)
    tax_number,
    store_name
  from {{ ref('documents') }}
  where counted and tax_number is not null and store_name is not null
  order by tax_number, uploaded_at
),

named as (
  select distinct on (pattern)
    pattern,
    target
  from {{ ref('rules') }}
  where rule_type = 'store'
  order by pattern, created_at, rule_id
)

select
  seen.tax_number,
  coalesce(named.target, seen.store_name) as store_name
from seen
left join named on seen.tax_number = named.pattern
