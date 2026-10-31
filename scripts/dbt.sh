#!/usr/bin/env bash
# A dbt futtatása a Compose-ban; argumentum nélkül `dbt build`.
set -euo pipefail
source "$(dirname "$0")/lib.sh"

if [[ $# -eq 0 ]]; then
  set -- build
fi

compose build -q dbt
compose run --rm dbt "$@"
