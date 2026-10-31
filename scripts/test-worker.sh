#!/usr/bin/env bash
# A worker tesztjei valódi Garage-dzsal és Postgresszel. A bronz írás visszagörget,
# a Garage tesztobjektumai törlődnek, így a helyi stacken is futhat.
set -euo pipefail
source "$(dirname "$0")/lib.sh"

compose run --rm worker-test
