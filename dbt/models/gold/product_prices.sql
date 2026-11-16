-- Termékenként és hónaponként az egységár, a személyes inflációhoz (ADR 0015).
-- Az átlag súlyozott: a havi összeg osztva a havi mennyiséggel, így a nagy kiszerelés nem torzít.
select
  date_trunc('month', documents.occurred_on)::date as month,
  items.category,
  items.product_family,
  items.product,
  items.base_unit,
  coalesce(stores.store_name, documents.store_name) as store_name,
  round(sum(items.base_unit_price * items.base_quantity) / sum(items.base_quantity), 2)
    as unit_price,
  min(items.base_unit_price) as min_unit_price,
  max(items.base_unit_price) as max_unit_price,
  sum(items.base_quantity) as quantity,
  count(*) as purchase_count
from {{ ref('receipt_items') }} as items
inner join {{ ref('documents') }} as documents on items.group_id = documents.group_id
left join {{ ref('stores') }} as stores on documents.tax_number = stores.tax_number
where items.kind = 'item' and items.product is not null and items.base_unit_price is not null
group by 1, 2, 3, 4, 5, 6
