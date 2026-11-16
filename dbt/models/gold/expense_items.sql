-- A Kiadások riport tételei; a riportfelület csak a goldot éri el.
select
  group_id,
  line_no,
  name,
  kind,
  category,
  product_family,
  product,
  quantity,
  unit,
  unit_price,
  value,
  pack_count,
  pack_quantity,
  pack_unit,
  base_unit,
  base_unit_price
from {{ ref('receipt_items') }}
