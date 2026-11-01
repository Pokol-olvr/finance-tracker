-- A beszámítható dokumentumok tételei; a betétdíj és az utalvány itt marad, a kiadásba nem kerül.
with lines as (
  select
    documents.group_id,
    documents.tags,
    item.ordinality::integer as line_no,
    item.value ->> 'name' as name,
    coalesce(item.value ->> 'kind', 'item') as kind,
    (item.value ->> 'quantity')::numeric as quantity,
    item.value ->> 'unit' as unit,
    (item.value ->> 'unit_price')::numeric as unit_price,
    (item.value ->> 'value')::numeric(14, 2) as value
  from {{ ref('documents') }} as documents
  cross join lateral jsonb_array_elements(documents.items) with ordinality as item
  where documents.counted
),

keyed as (
  select
    *,
    translate(upper(name), 'ÁÉÍÓÖŐÚÜŰ', 'AEIOOOUUU') as match_name
  from lines
),

-- A kiszerelés a névben van, pl. `3DB`, `175G`, `1,5L`; a név ettől nem változik.
sized as (
  select
    *,
    regexp_match(match_name, '(\d+(?:[,.]\d+)?)\s*(DB|KG|G|ML|CL|DL|L)\y') as pack
  from keyed
),

-- Több találatnál a hosszabb minta nyer, egyezésnél a régebbi szabály.
ruled as (
  select
    sized.*,
    rule.target as rule_category
  from sized
  left join lateral (
    select rules.target
    from {{ ref('rules') }} as rules
    where rules.rule_type = 'category' and strpos(sized.match_name, rules.pattern) > 0
    order by length(rules.pattern) desc, rules.created_at, rules.rule_id
    limit 1
  ) as rule on true
),

categorized as (
  select
    *,
    case
      when kind not in ('item', 'discount') then null
      when rule_category is not null then rule_category
      when cardinality(tags) = 1 then tags[1]
      else '{{ var("uncategorized") }}'
    end as own_category,
    count(*) filter (where kind = 'item') over (
      partition by group_id order by line_no
    ) as item_block
  from ruled
)

select
  group_id,
  line_no,
  name,
  match_name,
  kind,
  quantity,
  unit,
  unit_price,
  value,
  replace(pack[1], ',', '.')::numeric as pack_quantity,
  pack[2] as pack_unit,
  -- A kedvezménysor a fölötte álló tétel kategóriáját kapja.
  case
    when kind = 'discount' then first_value(own_category) over (
      partition by group_id, item_block order by line_no
    )
    else own_category
  end as category
from categorized
