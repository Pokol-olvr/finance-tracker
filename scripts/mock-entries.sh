#!/usr/bin/env bash
# Kitalált bejegyzések az elmúlt hónapokra a webapp API-ján át.
# A bronzból nem törölhetők, élesítés előtt a finance adatbázis újraépül.
set -euo pipefail
source "$(dirname "$0")/lib.sh"

exec python3 "$REPO_ROOT/scripts/mock_entries.py"
