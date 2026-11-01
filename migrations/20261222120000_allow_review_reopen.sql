-- migrate:up
alter table bronze.review_decision drop constraint review_decision_decision_check;
alter table bronze.review_decision add constraint review_decision_decision_check
check (decision in ('approved', 'corrected', 'rejected', 'reopened'));

-- migrate:down
-- Szándékosan üres: a bronz adat nem görgethető vissza.
