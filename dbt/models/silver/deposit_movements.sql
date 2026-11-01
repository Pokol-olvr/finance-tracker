-- A várható betétdíj mozgásai; a nullázás az akkori egyenleget törli, ezt a gold számolja.
with paid as (
  select
    items.group_id::text as source_id,
    'deposit' as movement,
    documents.occurred_on::timestamptz as moved_at,
    items.value as amount
  from {{ ref('receipt_items') }} as items
  inner join {{ ref('documents') }} as documents on items.group_id = documents.group_id
  where items.kind = 'deposit'
),

redeemed_lines as (
  select
    items.group_id::text as source_id,
    'voucher' as movement,
    documents.occurred_on::timestamptz as moved_at,
    items.value as amount
  from {{ ref('receipt_items') }} as items
  inner join {{ ref('documents') }} as documents on items.group_id = documents.group_id
  where items.kind = 'voucher'
),

redeemed as (
  select
    payments.group_id::text as source_id,
    'voucher' as movement,
    documents.occurred_on::timestamptz as moved_at,
    -payments.amount as amount
  from {{ ref('document_payments') }} as payments
  inner join {{ ref('documents') }} as documents on payments.group_id = documents.group_id
  where payments.method = 'deposit_voucher'
),

corrected as (
  select
    id::text as source_id,
    kind as movement,
    created_at as moved_at,
    coalesce(amount, 0) as amount
  from {{ source('bronze', 'deposit_correction') }}
)

select * from paid
union all
select * from redeemed_lines
union all
select * from redeemed
union all
select * from corrected
