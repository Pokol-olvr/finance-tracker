#!/usr/bin/env bash
# Egyszeri gépbeállítás a Pi-n (Raspberry Pi OS 64 bit): Docker Engine és Tailscale a gyártók
# saját csomagtárolójából. Többször is futtatható.
set -euo pipefail

if [[ $(dpkg --print-architecture) != arm64 ]]; then
  echo "64 bites Raspberry Pi OS kell (arm64)." >&2
  exit 1
fi
codename=$(. /etc/os-release && echo "$VERSION_CODENAME")

sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg openssl
sudo install -m 0755 -d /etc/apt/keyrings

# Docker: a Raspberry Pi OS csomagjai régiek, a Compose v2 a Docker tárolójában van.
if [[ ! -f /etc/apt/keyrings/docker.asc ]]; then
  sudo curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
fi
echo "deb [arch=arm64 signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian $codename stable" |
  sudo tee /etc/apt/sources.list.d/docker.list >/dev/null

# Tailscale: a saját tárolójából, nem a telepítő scriptjével.
if [[ ! -f /usr/share/keyrings/tailscale-archive-keyring.gpg ]]; then
  curl -fsSL "https://pkgs.tailscale.com/stable/debian/$codename.noarmor.gpg" |
    sudo tee /usr/share/keyrings/tailscale-archive-keyring.gpg >/dev/null
fi
curl -fsSL "https://pkgs.tailscale.com/stable/debian/$codename.tailscale-keyring.list" |
  sudo tee /etc/apt/sources.list.d/tailscale.list >/dev/null

sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin tailscale
sudo systemctl enable --now docker tailscaled

if ! id -nG "$USER" | grep -qw docker; then
  sudo usermod -aG docker "$USER"
  echo "A docker csoporthoz adtalak: jelentkezz ki és be, vagy futtasd: newgrp docker"
fi

# A belépés böngészőben történik; a gép neve a tailnetben a Pi hostneve lesz.
if ! tailscale status >/dev/null 2>&1; then
  sudo tailscale up
fi
echo "A Pi Tailscale-címe (ez a BIND_ADDRESS): $(tailscale ip -4)"
docker compose version
