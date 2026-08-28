#!/bin/bash
# Brings the app up with the TLS mode selected in config/.env. Run by
# the rsvp-app systemd unit after rsvp-secrets refreshes config/, and
# on every boot (WantedBy=multi-user.target). Set TLS_MODE=cloudflare
# in config/.env to use a Cloudflare Origin Certificate instead of
# Let's Encrypt (the default).
set -euo pipefail

cd "$(dirname "$0")/.."

# Sync the checkout to origin/main first, so a plain `systemctl
# restart rsvp-app.service` after a `git push` is enough to deploy --
# no separate manual "git fetch && git reset --hard" step needed.
# Hard reset (not pull/merge) to match exactly what's on GitHub every
# time, same as every manual deploy this repo has had so far -- the
# server is never expected to carry its own commits. A fetch failure
# (no network yet at boot, GitHub unreachable) is logged and skipped
# rather than aborting the whole start, so a transient network hiccup
# can't take the app down entirely.
#
# config/htpasswd is tracked in git but is actually owned by
# rsvp-secrets.service (fetch-secrets.sh), which just wrote it fresh
# from AWS Secrets Manager immediately before this script runs --
# rsvp-secrets.service is a plain oneshot with no RemainAfterExit, so
# Requires=rsvp-secrets.service reruns it on every start, not just at
# boot. A plain `reset --hard` would blow that away and silently
# revert to whatever stale htpasswd happens to be committed, locking
# out any admin account that only exists in Secrets Manager. Preserve
# whatever's already on disk across the reset instead.
if git fetch --quiet origin main; then
  cp config/htpasswd /tmp/rsvp-up-htpasswd.bak 2>/dev/null || true
  git reset --hard origin/main
  if [ -f /tmp/rsvp-up-htpasswd.bak ]; then
    mv /tmp/rsvp-up-htpasswd.bak config/htpasswd
  fi
else
  echo "rsvp-up: git fetch failed, continuing with the code already on disk" >&2
fi

TLS_MODE=$(grep -E '^TLS_MODE=' config/.env | tail -1 | cut -d= -f2-)

files=(-f docker-compose.yml)
if [ "${TLS_MODE:-letsencrypt}" = "cloudflare" ]; then
  files+=(-f docker-compose.cloudflare.yml)
fi

docker compose "${files[@]}" up -d --build
