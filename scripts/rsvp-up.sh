#!/bin/bash
# Brings the app up with the TLS mode selected in config/.env. Run by
# the rsvp-app systemd unit after rsvp-secrets refreshes config/.
# Set TLS_MODE=cloudflare in config/.env to use a Cloudflare Origin
# Certificate instead of Let's Encrypt (the default).
set -euo pipefail

cd "$(dirname "$0")/.."
source config/.env

files=(-f docker-compose.yml)
if [ "${TLS_MODE:-letsencrypt}" = "cloudflare" ]; then
  files+=(-f docker-compose.cloudflare.yml)
fi

docker compose "${files[@]}" up -d
