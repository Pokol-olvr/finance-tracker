-- Minden kiadásnak van kategóriája, és az a seedben szerepel.
select t.transaction_id, t.category
from {{ ref('transactions') }} as t
left join {{ ref('categories') }} as c on t.category = c.category
where t.kind = 'expense' and c.category is null
