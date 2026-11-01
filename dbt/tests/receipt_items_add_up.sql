-- Figyelmeztetés: a kézzel jóváhagyott dokumentum eltérhet, ez nem állíthatja meg a buildet.
{{ config(severity='warn') }}

select documents.group_id, documents.total, sum(items.value) as items_total
from {{ ref('documents') }} as documents
inner join {{ ref('receipt_items') }} as items on documents.group_id = items.group_id
where documents.counted
group by documents.group_id, documents.total
having abs(sum(items.value) - documents.total) > 2
