#!/usr/bin/env bash
# A repó nyilvános: blokk, bérpapír, kivonat, dump, modell és .env nem kerülhet bele.
# A git indexét nézi, így a commit előtti hook és a CI ugyanazt ellenőrzi.
# Kivétel a dbt/seeds/ alatti CSV, amely nem tartalmazhat valódi adatot.
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

pattern='\.(jpe?g|png|heic|webp|pdf|eml|csv|xlsx?|ods|dump|gguf|safetensors)$|(^|/)\.env$'

if found=$(git -c core.quotePath=false ls-files | grep -iE "$pattern" | grep -vE '^dbt/seeds/[^/]+\.csv$'); then
  echo "Adatfájl a repóban, ezek nem commitolhatók:" >&2
  echo "$found" >&2
  exit 1
fi
