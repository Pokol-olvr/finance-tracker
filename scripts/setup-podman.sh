#!/usr/bin/env bash
# Egyszeri gépbeállítás rootless Podmanhez Fedorán. Többször is futtatható.
set -euo pipefail

# A docker-compose csomagnak Docker CLI kell; a podman-docker ezt Podmannel adja meg.
if ! podman compose version >/dev/null 2>&1; then
  sudo dnf install -y podman-docker docker-compose
fi

# A Compose ezen a socketen beszél a Podmannel.
systemctl --user enable --now podman.socket
# Újraindítás után ez indítja el a konténereket, Podmanben nincs daemon.
systemctl --user enable podman-restart.service
# Enélkül kijelentkezéskor leállnának a konténerek, és a timer sem futna.
loginctl enable-linger "$USER"

podman compose version
