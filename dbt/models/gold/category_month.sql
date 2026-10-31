select
  date_trunc('month', occurred_on)::date as month,
  payer,
  category,
  sum(amount)::numeric(14, 2) as expense,
  count(*) as entry_count
from {{ ref('transactions') }}
where kind = 'expense'
group by 1, 2, 3
