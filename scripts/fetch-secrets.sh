#!/bin/bash
# Pulls the app's secrets from AWS Secrets Manager into config/. Run by
# the rsvp-secrets systemd unit before every app start (boot or manual
# `systemctl restart rsvp-app`), so a `put-secret-value` pushed from a
# laptop takes effect on the next start without touching git.
set -euo pipefail

cd "$(dirname "$0")/.."

fetch() {
  aws secretsmanager get-secret-value --secret-id "$1" --query SecretString --output text > "$2"
}

fetch rsvp-app/env config/.env
fetch rsvp-app/htpasswd config/htpasswd
fetch rsvp-app/cf-cert config/cloudflare_origin_server.crt
fetch rsvp-app/cf-key config/cloudflare_origin_server.key

chmod 600 config/.env config/cloudflare_origin_server.key
chmod 644 config/htpasswd config/cloudflare_origin_server.crt
