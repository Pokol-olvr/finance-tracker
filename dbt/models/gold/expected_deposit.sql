-- A várható betétdíj jelenlegi összege: az utolsó nullázás óta történt mozgások összege.
select coalesce(sum(amount), 0) as balance
from {{ ref('deposit_history') }}
where period_no = (select max(period_no) from {{ ref('deposit_history') }})
