# RSVP App

Self-hosted event RSVP system. Guests scan a QR code or type a 3-word
passcode from their printed invitation. Flask + PostgreSQL + Nginx on a
single EC2 instance via Docker Compose. No frontend framework.

## Layout

```
config/          central config: .env (values), nginx template, htpasswd
app/             Flask application, schema, EFF wordlist, Dockerfile
backup/          nightly pg_dump-to-S3 sidecar
scripts/         Let's Encrypt bootstrap, cron example, admin creation
infra/           OpenTofu for EC2, security group, IAM, backup bucket
tests/           pytest suite (run: python3 -m pytest tests/)
```

## Theming

Edit the variable block at the top of `app/rsvp/static/style.css`.
Colors, fonts, corner radius, and spacing are all controlled there.
Nothing else needs to change for a basic reskin. Event title lives in
`app/rsvp/templates/base.html`.

Preset variable blocks for common party themes are in
`app/rsvp/static/themes/` — copy one over the `:root { ... }` block at
the top of `style.css` to apply it:

- `kids-party.css` — bright, playful, rounded corners
- `wedding.css` — black & white, script heading, serif body
- `holiday-party.css` — festive red/green/gold on warm cream

## Local development

```bash
cp config/.env.example config/.env        # edit values
./scripts/create-admin.sh yourname        # writes config/htpasswd
docker compose up -d postgres python_app  # skip nginx/certbot locally
```

App listens on the internal network; for local browsing add a temporary
`ports: ["8000:8000"]` to python_app or run Flask directly:

```bash
cd app && pip install -r requirements.txt
FLASK_DEBUG=1 POSTGRES_HOST=localhost flask --app rsvp run
```

## Deploying

1. `cd infra && tofu init && tofu apply -var backup_bucket_name=YOUR-BUCKET`
   (optionally add `-var vpc_id=YOUR-VPC -var subnet_id=YOUR-SUBNET` to
   deploy into an existing VPC/subnet instead of the account default)
2. Verify SES sender identity for `SES_SENDER_EMAIL` in the AWS console
3. Point your domain's A record at the output `public_ip`
4. Connect via SSM Session Manager, clone this repo to `/opt/rsvp-app`
5. `cp config/.env.example config/.env` and fill in real values
6. `./scripts/create-admin.sh yourname`
7. `docker compose up -d`
8. `./scripts/init-letsencrypt.sh` (one time, needs DNS live first)
9. Install the renewal cron: see `scripts/crontab.example`

### Temporary HTTP-only mode

Before DNS/cert is ready (or to test without HTTPS briefly), swap nginx
to serve plain HTTP on port 80 instead of redirecting to HTTPS:

```bash
docker compose -f docker-compose.yml -f docker-compose.http-only.yml up -d nginx
```

Revert to the normal redirect+TLS config with the base file alone:

```bash
docker compose up -d nginx
```

## Bulk guest upload

CSV with a header row, columns `primary_name,email,max_guests`. Upload
from `/admin/dashboard`. UUIDs and passcodes generate automatically,
with collision retry. Print cards from the per-guest "View card" link.

## Notes

- The QR link is a bearer token by design: anyone with the link can
  RSVP for that household. Accepted tradeoff for this use case.
- Rate limiting (20 req/min, burst 10) applies to phrase lookup and
  email recovery at the Nginx layer, keyed per source IP.
- Backups expire from S3 after 30 days (lifecycle rule in infra).
- bcrypt is pinned to 4.0.1: passlib 1.7.4 is incompatible with
  bcrypt >= 4.1.
- Optional nginx Prometheus metrics: uncomment the exporter service in
  docker-compose.yml and the stub_status block in the nginx template.
