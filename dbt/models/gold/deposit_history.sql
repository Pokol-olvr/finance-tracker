-- Mozgásonként a várható betétdíj; a nullázás új szakaszt nyit, ami előtte volt, az nem számít.
with positioned as (
  select
    *,
    row_number() over (order by moved_at, source_id, movement, amount) as position
  from {{ ref('deposit_movements') }}
),

periods as (
  select
    *,
    count(*) filter (where movement = 'reset') over (
      order by position rows unbounded preceding
    ) as period_no
  from positioned
)

select
  source_id,
  position,
  period_no,
  movement,
  moved_at,
  amount,
  sum(amount) over (partition by period_no order by position rows unbounded preceding) as balance
from periods
