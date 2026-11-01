-- Minden kiadásnak van kategóriája: a seedből, vagy a besorolásra váró technikai érték.
select t.transaction_id, t.category
from {{ ref('transactions') }} as t
left join {{ ref('categories') }} as c on t.category = c.category
where t.kind = 'expense' and c.category is null and t.category <> '{{ var("uncategorized") }}'
