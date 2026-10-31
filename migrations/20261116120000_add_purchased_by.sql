-- migrate:up
alter table bronze.raw_document add column purchased_by text;
alter table bronze.manual_entry add column purchased_by text;

-- migrate:down
-- Szándékosan üres: a bronz adat nem görgethető vissza.
