#!/usr/bin/env bash
# Egyszeri gépbeállítás Windowson, WSL2-es Ubuntuban, Docker Engine-nel. Többször is futtatható.
# A Podman itt is használható, ehhez a setup-podman.sh csomagtelepítését kell apt-tal elvégezni.
set -euo pipefail

if ! grep -qi microsoft /proc/version; then
  echo "Ez a script WSL-hez készült, Fedorán a setup-podman.sh kell." >&2
  exit 1
fi

# A timerekhez és a Docker szolgáltatáshoz systemd kell, ezt a /etc/wsl.conf kapcsolja be.
if [[ $(ps -p 1 -o comm=) != systemd ]]; then
  echo "A systemd nem fut. Tedd a /etc/wsl.conf-ba:" >&2
  printf '[boot]\nsystemd=true\n' >&2
  echo "majd Windowsból: wsl --shutdown" >&2
  exit 1
fi

# Az Ubuntu saját csomagjai elegek, a Docker külön tárolója nem kell.
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-v2 jq
sudo systemctl enable --now docker

# A csoporttagság új bejelentkezéstől él, addig a docker parancs sudo-t kér.
if ! id -nG "$USER" | grep -qw docker; then
  sudo usermod -aG docker "$USER"
  echo "A docker csoporthoz adtalak: zárd be a WSL-terminált, vagy futtasd: newgrp docker"
fi

# Enélkül kijelentkezéskor leállna a felhasználói systemd, és a timerek sem futnának.
sudo loginctl enable-linger "$USER"

sudo docker compose version
