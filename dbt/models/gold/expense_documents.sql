-- A Kiadások riport dokumentumlistája: csak ami a kiadásba számít, egységes boltnévvel.
select
  documents.group_id,
  documents.occurred_on,
  coalesce(stores.store_name, documents.store_name) as store_name,
  documents.tax_number,
  documents.payer,
  documents.purchased_by,
  documents.document_type,
  documents.total,
  count(items.line_no) as item_count
from {{ ref('documents') }} as documents
left join {{ ref('stores') }} as stores on documents.tax_number = stores.tax_number
left join {{ ref('receipt_items') }} as items on documents.group_id = items.group_id
where documents.counted
group by
  documents.group_id,
  documents.occurred_on,
  stores.store_name,
  documents.store_name,
  documents.tax_number,
  documents.payer,
  documents.purchased_by,
  documents.document_type,
  documents.total
