-- migrate:up
-- Termékszabály: a minta névrészlet vagy EAN, a cél `kategória/termékcsalád/termék`.
-- Kiszerelésszabály: a kiszerelés nélküli névhez ad kiszerelést, pl. `500G` (ADR 0015).
alter table bronze.rule_event drop constraint rule_event_rule_type_check;
alter table bronze.rule_event add constraint rule_event_rule_type_check check (
  rule_type in ('category', 'store', 'product', 'pack')
);

-- migrate:down
-- Szándékosan üres: a már felvett termékszabályok miatt a szűkebb feltétel nem állna vissza.
