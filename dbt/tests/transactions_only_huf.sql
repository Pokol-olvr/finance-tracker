-- A gold összegei csak egy pénznemben értelmesek.
select transaction_id, currency
from {{ ref('transactions') }}
where currency <> 'HUF'
