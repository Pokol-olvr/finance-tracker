#!/usr/bin/env bash
# Kiírja a legutóbbi kiolvasásokat. A kimenet valódi blokk adatát is tartalmazhatja.
# Használat: scripts/last-extraction.sh [darab], alapból 1.
set -euo pipefail
source "$(dirname "$0")/lib.sh"

compose exec -T postgres psql -U postgres -d finance -v ON_ERROR_STOP=1 -v limit="${1:-1}" -x <<'SQL'
select d.purchase_date, d.uploaded_by, d.purchased_by, d.payer, d.tags, d.object_key,
       e.model_name, e.created_at,
       e.payload ->> 'seconds' as seconds,
       e.payload ->> 'done_reason' as done_reason,
       e.payload ->> 'error' as error,
       e.payload ->> 'ocr_text' as ocr_text,
       jsonb_pretty(e.payload -> 'parsed') as parsed
from bronze.extraction as e
join bronze.raw_document as d on d.id = e.document_id
order by e.created_at desc
limit :limit;
SQL
