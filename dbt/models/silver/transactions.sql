with manual as (
  select
    id as transaction_id,
    'manual' as source,
    kind,
    amount,
    currency,
    occurred_on,
    purchased_by,
    payer,
    tags[1] as category,
    entered_by,
    note
  from {{ source('bronze', 'manual_entry') }}
),

-- Dokumentumonként és kategóriánként egy kiadás; a kedvezmény csökkenti, a betétdíj nem része.
documents as (
  select
    md5(documents.group_id::text || items.category)::uuid as transaction_id,
    'document' as source,
    'expense' as kind,
    sum(items.value) as amount,
    'HUF' as currency,
    documents.occurred_on,
    documents.purchased_by,
    documents.payer,
    items.category,
    documents.uploaded_by as entered_by,
    documents.store_name as note
  from {{ ref('receipt_items') }} as items
  inner join {{ ref('documents') }} as documents on items.group_id = documents.group_id
  where items.kind in ('item', 'discount')
  group by
    documents.group_id,
    items.category,
    documents.occurred_on,
    documents.purchased_by,
    documents.payer,
    documents.uploaded_by,
    documents.store_name
  having sum(items.value) > 0
)

select * from manual
union all
select * from documents
