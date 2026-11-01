-- Ugyanaz az adószám és sorszám csak egyszer számíthat.
select tax_number, receipt_number, count(*) as copies
from {{ ref('documents') }}
where counted and tax_number is not null and receipt_number is not null
group by 1, 2
having count(*) > 1
