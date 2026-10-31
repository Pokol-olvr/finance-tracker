-- Az összeg mindig pozitív, az irányt a kind adja.
select transaction_id, amount
from {{ ref('transactions') }}
where amount <= 0
