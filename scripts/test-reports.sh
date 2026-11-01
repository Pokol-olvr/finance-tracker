#!/usr/bin/env bash
# A riportfelület tesztjei kitalált adatokkal, adatbázis nélkül.
set -euo pipefail
source "$(dirname "$0")/lib.sh"

compose run --rm reports-test
