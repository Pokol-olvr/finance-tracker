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
