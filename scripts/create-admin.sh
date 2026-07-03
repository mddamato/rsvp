#!/bin/bash
# Creates or updates the admin user in config/htpasswd using bcrypt.
# Usage: ./scripts/create-admin.sh <username>
set -euo pipefail
cd "$(dirname "$0")/.."
USERNAME="${1:?usage: create-admin.sh <username>}"
read -s -p "Password for ${USERNAME}: " PW; echo
docker run --rm httpd:alpine htpasswd -nbB "$USERNAME" "$PW" >> config/htpasswd
echo "Wrote entry to config/htpasswd"
