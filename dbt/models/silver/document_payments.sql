-- Fizetési soronként egy sor; a DRS-utalványok külön maradnak, a FIN-411 összeg szerint párosítja őket.
select
  documents.group_id,
  payment.ordinality::integer as line_no,
  payment.value ->> 'method' as method,
  (payment.value ->> 'amount')::numeric(14, 2) as amount
from {{ ref('documents') }} as documents
cross join lateral jsonb_array_elements(documents.payments) with ordinality as payment
where documents.counted
