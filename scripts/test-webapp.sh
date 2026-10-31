#!/usr/bin/env bash
# A webapp tesztjei a Compose-hálózaton. A bronz teszt visszagörget, így a helyi stacken is futhat.
set -euo pipefail
source "$(dirname "$0")/lib.sh"

compose run --rm webapp-test
