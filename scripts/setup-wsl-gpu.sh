#!/usr/bin/env bash
# Egyszeri beállítás: a WSL-es Docker eléri a Windows NVIDIA GPU-ját. Többször is futtatható.
# A driver a Windows oldalon van, a WSL-be nem kell drivert telepíteni.
set -euo pipefail

if ! nvidia-smi >/dev/null 2>&1; then
  echo "A WSL nem látja a GPU-t: frissítsd a Windows NVIDIA drivert, majd: wsl --shutdown" >&2
  exit 1
fi

# Az NVIDIA saját csomagtárolója, a toolkit az Ubuntu tárolóiban nincs benne.
keyring=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
if [[ ! -f $keyring ]]; then
  curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o "$keyring"
fi
curl -fsSL https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list |
  sed "s#deb https://#deb [signed-by=$keyring] https://#g" |
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list >/dev/null

sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

docker run --rm --gpus all docker.io/library/ubuntu:24.04 nvidia-smi -L
echo "Kész. A home/.env-be: COMPOSE_FILE=docker-compose.yml:docker-compose.gpu.yml"
