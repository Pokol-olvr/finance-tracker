-- A dokumentumok száma állapotonként, hogy a riport jelezze, mennyi vár még döntésre.
select
  state,
  count(*) as document_count
from {{ ref('documents') }}
group by state
