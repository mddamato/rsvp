#!/bin/bash
# Pulls non-secret config assets (e.g. an invitation image referenced
# by EVENT_DETAILS_IMAGE) from S3 into config/assets/. Run by the
# rsvp-secrets systemd unit alongside fetch-secrets.sh, before every
# app start, so a file pushed from a laptop with
# `aws s3 sync config/assets/ s3://$BACKUP_S3_BUCKET/assets/`
# takes effect on the next start without touching git or Secrets
# Manager (which caps secret values at 64KB -- too small for most
# real images).
set -euo pipefail

cd "$(dirname "$0")/.."

BACKUP_S3_BUCKET=$(grep -E '^BACKUP_S3_BUCKET=' config/.env | tail -1 | cut -d= -f2-)

mkdir -p config/assets
aws s3 sync "s3://${BACKUP_S3_BUCKET}/assets/" config/assets/ --delete
