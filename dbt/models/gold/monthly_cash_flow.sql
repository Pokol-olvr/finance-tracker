with transactions as (
  select * from {{ ref('transactions') }}
),

bounds as (
  select
    date_trunc('month', min(occurred_on))::date as first_month,
    greatest(
      date_trunc('month', max(occurred_on))::date,
      date_trunc('month', {{ var('as_of_date') }})::date
    ) as last_month
  from transactions
),

-- Bejegyzés nélküli hónap is kell, különben torzulna az átlag.
months as (
  select generate_series(first_month, last_month, interval '1 month')::date as month
  from bounds
),

payers as (
  select distinct payer from transactions
),

totals as (
  select
    date_trunc('month', occurred_on)::date as month,
    payer,
    sum(amount) filter (where kind = 'income') as income,
    sum(amount) filter (where kind = 'expense') as expense
  from transactions
  group by 1, 2
),

filled as (
  select
    months.month,
    payers.payer,
    coalesce(totals.income, 0) as income,
    coalesce(totals.expense, 0) as expense
  from months
  cross join payers
  left join totals on months.month = totals.month and payers.payer = totals.payer
)

select
  month,
  payer,
  income::numeric(14, 2) as income,
  expense::numeric(14, 2) as expense,
  (income - expense)::numeric(14, 2) as net,
  ((income - expense) / nullif(income, 0))::numeric(12, 4) as savings_rate
from filled
