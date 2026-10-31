#!/usr/bin/env bash
# Letölti a képfelismerő modellt a data/ollama mappába, és kiírja az azonosítóját.
# A már letöltött rétegeket nem tölti le újra, ezért újrafuttatható.
set -euo pipefail
source "$(dirname "$0")/lib.sh"

model=${OLLAMA_MODEL:-glm-ocr}

compose up -d --wait ollama
compose exec -T ollama ollama pull "$model"
compose exec -T ollama ollama list
