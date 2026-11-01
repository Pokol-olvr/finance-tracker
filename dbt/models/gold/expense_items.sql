-- A Kiadások riport tételei; a riportfelület csak a goldot éri el.
select
  group_id,
  line_no,
  name,
  kind,
  category,
  quantity,
  unit,
  unit_price,
  value,
  pack_quantity,
  pack_unit
from {{ ref('receipt_items') }}
