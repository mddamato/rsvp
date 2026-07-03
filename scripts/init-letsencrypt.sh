#!/bin/bash
# One-time initial certificate issuance. Run from the repo root on the
# EC2 host after DNS for DOMAIN_NAME points at this server.
#
# Nginx must be able to start before a cert exists, so this script:
#  1. issues a temporary self-signed cert so nginx's 443 block loads
#  2. starts nginx
#  3. requests the real cert from Let's Encrypt via the webroot challenge
#  4. reloads nginx onto the real cert
set -euo pipefail

cd "$(dirname "$0")/.."
source config/.env

echo "==> Creating temporary self-signed cert for ${DOMAIN_NAME}"
docker compose run --rm --entrypoint /bin/sh certbot -c "
  mkdir -p /etc/letsencrypt/live/${DOMAIN_NAME} &&
  apk add --no-cache openssl >/dev/null 2>&1 || true;
  openssl req -x509 -nodes -newkey rsa:2048 -days 1 \
    -keyout /etc/letsencrypt/live/${DOMAIN_NAME}/privkey.pem \
    -out /etc/letsencrypt/live/${DOMAIN_NAME}/fullchain.pem \
    -subj '/CN=${DOMAIN_NAME}'"

echo "==> Starting nginx"
docker compose up -d nginx

echo "==> Removing temporary cert and requesting the real one"
docker compose run --rm --entrypoint /bin/sh certbot -c "
  rm -rf /etc/letsencrypt/live/${DOMAIN_NAME} \
         /etc/letsencrypt/archive/${DOMAIN_NAME} \
         /etc/letsencrypt/renewal/${DOMAIN_NAME}.conf"

docker compose run --rm --entrypoint certbot certbot certonly \
  --webroot -w /var/www/certbot \
  -d "${DOMAIN_NAME}" \
  --agree-tos --no-eff-email --register-unsafely-without-email

echo "==> Reloading nginx onto the real certificate"
docker exec rsvp_nginx nginx -s reload

echo "==> Done. Install the renewal cron job from scripts/crontab.example"
