-- A beszámítható dokumentumok tételei; a betétdíj és az utalvány itt marad, a kiadásba nem kerül.
-- A termék a termékszabályból jön, a kategória a termékből, ennek híján a kategóriaszabályból (ADR 0015).
with lines as (
  select
    documents.group_id,
    documents.tags,
    item.ordinality::integer as line_no,
    item.value ->> 'name' as name,
    coalesce(item.value ->> 'kind', 'item') as kind,
    (item.value ->> 'quantity')::numeric as quantity,
    upper(item.value ->> 'unit') as unit,
    (item.value ->> 'unit_price')::numeric as unit_price,
    (item.value ->> 'value')::numeric(14, 2) as value,
    nullif(item.value ->> 'ean', '') as ean
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

-- Több találatnál az EAN nyer, utána a hosszabb minta, egyezésnél a régebbi szabály.
ruled as (
  select
    keyed.*,
    category_rule.target as rule_category,
    product_rule.target as product_path,
    pack_rule.target as rule_pack
  from keyed
  left join lateral (
    select rules.target
    from {{ ref('rules') }} as rules
    where rules.rule_type = 'category' and strpos(keyed.match_name, rules.pattern) > 0
    order by length(rules.pattern) desc, rules.created_at, rules.rule_id
    limit 1
  ) as category_rule on true
  left join lateral (
    select rules.target
    from {{ ref('rules') }} as rules
    where
      rules.rule_type = 'product'
      and (rules.pattern = keyed.ean or strpos(keyed.match_name, rules.pattern) > 0)
    order by
      (rules.pattern = keyed.ean) is true desc,
      length(rules.pattern) desc,
      rules.created_at,
      rules.rule_id
    limit 1
  ) as product_rule on true
  left join lateral (
    select upper(rules.target) as target
    from {{ ref('rules') }} as rules
    where rules.rule_type = 'pack' and strpos(keyed.match_name, rules.pattern) > 0
    order by length(rules.pattern) desc, rules.created_at, rules.rule_id
    limit 1
  ) as pack_rule on true
),

-- A kiszerelés a névben van, pl. `3DB`, `175G`, `1,5L`, `4X120G`; a kiszerelésszabály felülírja.
-- A darabszám előtt nem állhat szám, így a `2.8X1L` nem nyolc literes csomag.
sized as (
  select
    *,
    regexp_match(
      coalesce(rule_pack, match_name),
      '(?:^|[^0-9.,])(\d+)\s*[X*]\s*(\d+(?:[,.]\d+)?)\s*(KG|G|ML|CL|DL|L)\y'
    ) as multipack,
    regexp_match(
      coalesce(rule_pack, match_name), '(\d+(?:[,.]\d+)?)\s*(DB|KG|G|ML|CL|DL|L)\y'
    ) as pack
  from ruled
),

packed as (
  select
    *,
    coalesce(multipack[1]::numeric, 1) as pack_count,
    replace(coalesce(multipack[2], pack[1]), ',', '.')::numeric as pack_quantity,
    coalesce(multipack[3], pack[2]) as pack_unit
  from sized
),

-- Egységár alapegységben: a mérlegelt tételnél a mért mennyiség, különben darab × kiszerelés.
measured as (
  select
    *,
    case
      when unit = 'KG' then 'kg'
      when pack_unit in ('G', 'KG') then 'kg'
      when pack_unit in ('ML', 'CL', 'DL', 'L') then 'l'
      else 'db'
    end as base_unit,
    case
      when unit = 'KG' then quantity
      when pack_unit is not null
        then
          coalesce(quantity, 1) * pack_count * pack_quantity
          * case pack_unit
            when 'G' then 0.001
            when 'ML' then 0.001
            when 'CL' then 0.01
            when 'DL' then 0.1
            else 1
          end
      else coalesce(quantity, 1)
    end as base_quantity
  from packed
),

categorized as (
  select
    *,
    split_part(product_path, '/', 2) as own_family,
    split_part(product_path, '/', 3) as own_product,
    case
      when kind not in ('item', 'discount') then null
      when product_path is not null then split_part(product_path, '/', 1)
      when rule_category is not null then rule_category
      when cardinality(tags) = 1 then tags[1]
      else '{{ var("uncategorized") }}'
    end as own_category,
    count(*) filter (where kind = 'item') over (
      partition by group_id order by line_no
    ) as item_block
  from measured
),

-- A kedvezménysor a fölötte álló tétel termékét és kategóriáját kapja.
inherited as (
  select
    *,
    case
      when kind = 'discount' then first_value(own_category) over item_lines
      else own_category
    end as category,
    case
      when kind = 'discount' then first_value(own_family) over item_lines
      when kind = 'item' then own_family
    end as product_family,
    case
      when kind = 'discount' then first_value(own_product) over item_lines
      when kind = 'item' then own_product
    end as product,
    sum(value) filter (where kind in ('item', 'discount')) over (
      partition by group_id, item_block
    ) as block_value
  from categorized
  window item_lines as (partition by group_id, item_block order by line_no)
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
  ean,
  case when pack_unit is not null then pack_count end as pack_count,
  pack_quantity,
  pack_unit,
  category,
  nullif(product_family, '') as product_family,
  nullif(product, '') as product,
  case when kind = 'item' then base_unit end as base_unit,
  case when kind = 'item' then base_quantity end as base_quantity,
  -- Az egységár a tétel és az alatta álló kedvezmények összegéből számít.
  case
    when kind = 'item' and base_quantity > 0 then round(block_value / base_quantity, 2)
  end as base_unit_price
from inherited
