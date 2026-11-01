-- Dokumentumonként egy sor. Azt, hogy mi számít kiadásnak, egyedül ez a modell dönti el (ADR 0013).
with parses as (
  select distinct on (group_id)
    group_id,
    id as parse_id,
    status,
    payload
  from {{ source('bronze', 'receipt_parse') }}
  order by group_id, created_at desc
),

decisions as (
  select distinct on (group_id)
    group_id,
    decision,
    corrected
  from {{ source('bronze', 'review_decision') }}
  order by group_id, decided_at desc
),

-- Több fájlból álló dokumentumnál a feltöltés adatai minden oldalon azonosak.
uploads as (
  select distinct on (coalesce(group_id, id))
    coalesce(group_id, id) as group_id,
    uploaded_by,
    uploaded_at,
    purchased_by,
    purchase_date,
    payer,
    tags
  from {{ source('bronze', 'raw_document') }}
  order by coalesce(group_id, id), page_no
),

merged as (
  select
    parses.group_id,
    parses.parse_id,
    parses.status,
    decisions.decision,
    parses.payload ->> 'document_type' as document_type,
    parses.payload ->> 'tax_number' as tax_number,
    parses.payload ->> 'receipt_number' as receipt_number,
    parses.payload -> 'payments' as payments,
    case
      when decisions.decision = 'corrected' then decisions.corrected
      else parses.payload
    end as data,
    uploads.uploaded_by,
    uploads.uploaded_at,
    uploads.purchased_by,
    uploads.purchase_date,
    uploads.payer,
    uploads.tags
  from parses
  inner join uploads on parses.group_id = uploads.group_id
  left join decisions on parses.group_id = decisions.group_id
),

classified as (
  select
    *,
    case
      when decision = 'rejected' then 'rejected'
      when decision = 'corrected' then 'counted'
      when document_type = 'non_expense' then 'non_expense'
      when coalesce(data ->> 'currency', 'HUF') <> 'HUF' then 'foreign_currency'
      when decision = 'approved' or status = 'ok' then 'counted'
      else 'pending'
    end as raw_state
  from merged
),

-- Ugyanaz a dokumentum két külön fotóról: csak a legkorábbi számít.
ranked as (
  select
    *,
    case
      when raw_state = 'counted' and tax_number is not null and receipt_number is not null
        then row_number() over (
          partition by raw_state, tax_number, receipt_number
          order by uploaded_at, group_id
        )
      else 1
    end as copy_no
  from classified
)

select
  group_id,
  parse_id,
  document_type,
  case when copy_no > 1 then 'duplicate' else raw_state end as state,
  raw_state = 'counted' and copy_no = 1 as counted,
  data ->> 'store_name' as store_name,
  tax_number,
  receipt_number,
  coalesce((data ->> 'purchased_on')::date, purchase_date, uploaded_at::date) as occurred_on,
  (data ->> 'total')::numeric(14, 2) as total,
  uploaded_by,
  uploaded_at,
  purchased_by,
  payer,
  tags,
  data -> 'items' as items,
  payments
from ranked
