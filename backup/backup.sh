#!/bin/sh
# Dumps the database every 24 hours and syncs to S3.
# Credentials come from the EC2 instance IAM role via the metadata
# service. Requires the instance's IMDS hop limit set to 2 so
# containers can reach it (handled in infra/main.tf).
set -eu

echo "backup sidecar started; first run in 60s"
sleep 60

while true; do
  STAMP=$(date -u +%Y-%m-%dT%H%M%SZ)
  FILE="/tmp/rsvp-${STAMP}.sql.gz"
  echo "dumping database to ${FILE}"
  PGPASSWORD="${POSTGRES_PASSWORD}" pg_dump \
    -h "${POSTGRES_HOST}" -U "${POSTGRES_USER}" "${POSTGRES_DB}" \
    | gzip > "${FILE}"
  echo "uploading to s3://${BACKUP_S3_BUCKET}/"
  aws s3 cp "${FILE}" "s3://${BACKUP_S3_BUCKET}/${STAMP}.sql.gz" \
    --region "${AWS_REGION}"
  rm -f "${FILE}"
  echo "backup complete, sleeping 24h"
  sleep 86400
done
