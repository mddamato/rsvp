# RSVP App

Self-hosted event RSVP system. Guests scan a QR code or type a 3-word
passcode from their printed invitation. Flask + PostgreSQL + Nginx on a
single EC2 instance via Docker Compose. No frontend framework.

## Layout

```
config/          central config: .env (values), nginx template, htpasswd,
                 assets/ (non-secret files like an invitation image)
app/             Flask application, schema, EFF wordlist, Dockerfile
backup/          nightly pg_dump-to-S3 sidecar
scripts/         Let's Encrypt bootstrap, cron example, admin creation,
                 boot-time secrets fetch + app start (see Deploying),
                 migrations/ (one-off schema changes for existing DBs)
infra/           OpenTofu for EC2, security group, IAM, backup bucket
tests/           pytest suite (run: python3 -m pytest tests/)
```

## Event text

`EVENT_TITLE`, `EVENT_SUBHEADING`, `EVENT_DETAILS`, and `EVENT_CLOSING`
in `config/.env` control the guest-facing text: the main title, an
optional line underneath for date/time, an optional paragraph below
that for longer instructions (parking, directions, dress code, etc),
and an optional closing signature (e.g. "- The Smith Family") rendered
near the bottom of the page, below the form. Only `EVENT_TITLE` has a
default ("Our Celebration"); the rest are hidden if left unset. Admin
pages don't show any of this, and neither does the passcode entry
page itself (`phrase_entry.html`) — that page is reachable by anyone,
before they've proven they know a valid passcode or link, so
`EVENT_SUBHEADING`, `EVENT_DETAILS`, and `EVENT_DETAILS_IMAGE` only
render on pages reached *after* a match (the RSVP form,
self-registration). `EVENT_TITLE` and `EVENT_CLOSING` still show on
the passcode page — they're not treated as sensitive.

`EVENT_DETAILS_IMAGE` adds an invitation image right below
`EVENT_DETAILS`, same visibility rule. Set it to a filename (not a
path) and place the actual file in `config/assets/` — see "Non-secret
config assets" below for how that gets onto the server. Resized
server-side (capped at 1200px wide, aspect ratio kept) the first time
it's requested so mobile guests aren't stuck downloading a
multi-megabyte original, then cached in memory for the process
lifetime — replacing the file on disk needs a
`sudo systemctl restart rsvp-app.service` to pick up. The image URL
itself requires a token that's only ever embedded on a page reached
by knowing a valid passcode/link/self-register phrase (derived from
`SECRET_KEY`, not per-guest or time-limited — same bearer-token model
as the personal RSVP link) — a bot scanning the site cold can't fetch
it without that.

## Anonymous self-registration

`ANONYMOUS_PHRASE` in `config/.env` (unset/blank by default) enables a
second on-ramp for situations where the guest list isn't known ahead
of time — a generic flyer, poster, or cards handed out somewhere like
a school, all sharing one phrase instead of individual passcodes. Set
it to any human phrase, e.g. `ANONYMOUS_PHRASE=Tonys third birthday`.
Matching is case-insensitive, apostrophes are ignored, and extra
whitespace is collapsed, so "tony's THIRD birthday" and "Tonys  third
birthday" both match. Avoid picking exactly three common dictionary
words, since that's indistinguishable from a real generated passcode.

Anyone who types the configured phrase into the normal passcode box
gets a short form (name, email, attending/declining, and a notes
field) instead of "not found." Submitting it creates a real invitee
**immediately** with that RSVP already recorded — same as the admin's
"Add a single guest" followed by the guest's own RSVP in one step —
and shows them their phrase, link, and QR code on screen, plus emails
it to them if they gave an email. They can revisit their link later
to change their answer, same as any other guest. There's no separate
approval step before access is granted:
review is after the fact. Self-registered guests are flagged
`(self-registered, pending review)` on the admin dashboard, with
matching "Self-registered" and "Pending review" count tiles, and a
Confirm button that dismisses the flag (bookkeeping only — it doesn't
change their access, which they already have). Rejecting one entirely
is just the existing Delete button.

Self-registration is solo-only by default. Set
`SELF_REGISTER_MULTIPLE_GUESTS=1` to let self-registrants bring
additional guests too, using the same per-guest "Add guest" UI
described below.

Typing the phrase isn't the only way in: `/register` goes straight to
the self-registration form, no phrase needed — for a QR code you hand
out to people with no personal invite (a flyer, a poster, cards at a
school). The admin dashboard shows this QR (open by default, right
under the stat tiles, only when `ANONYMOUS_PHRASE` is set) alongside
the phrase itself for people who'd rather type it, and links to
`/admin/register-card` for a printable full-size version.

### Plus-one guests

Guests joining an invitee (whether entered by the invitee on their
RSVP form, or by a self-registrant when
`SELF_REGISTER_MULTIPLE_GUESTS=1`) are captured one at a time: a name
box plus a "child (6 or under)" checkbox per guest, with an "Add
guest" button revealing one more slot at a time, up to the number
allowed. This replaces the old single comma-separated text field. The
page works fully without JavaScript — every slot is rendered from the
start; "Add guest" just tidies the initial view by hiding slots
beyond however many are already filled, revealing more on click.

**Upgrading an existing deployment**: this feature adds `origin` and
`reviewed` columns to the `invitees` table. Fresh installs get them
automatically from `app/schema.sql`, but `docker-entrypoint-initdb.d`
only runs against an empty Postgres volume — it won't touch an existing database
with real guest data. Run the one-time migrations in
`scripts/migrations/` (in order — `2026-08-23-add-invitee-origin.sql`
then `2026-08-24-add-invitee-reviewed.sql`) against the live database
**before** deploying this version of the app code (the new code's
INSERT statements reference these columns). See the comments in those
files, or:
```bash
docker compose exec -T postgres sh -c 'PGPASSWORD="$POSTGRES_PASSWORD" pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' | gzip > /root/pre-migration-backup.sql.gz  # optional extra backup
docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < scripts/migrations/2026-08-23-add-invitee-origin.sql
docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < scripts/migrations/2026-08-24-add-invitee-reviewed.sql
```
then proceed with the normal `git pull` + `sudo systemctl restart rsvp-app.service` redeploy.

## Theming

Edit the variable block at the top of `app/rsvp/static/style.css`.
Colors, fonts, corner radius, and spacing are all controlled there.
Nothing else needs to change for a basic reskin. Event title lives in
`app/rsvp/templates/base.html`.

Preset variable blocks for common party themes are in
`app/rsvp/static/themes/` — copy one over the `:root { ... }` block at
the top of `style.css` to apply it:

- `kids-party.css` — bright, playful, rounded corners
- `boy-toddler.css` — bold red & blue accents, blocky heading font
- `wedding.css` — black & white, script heading, serif body
- `holiday-party.css` — softer, muted festive red/green/gold on warm cream
- `christmas.css` — classic red/green/gold on snow white

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

Secrets (`config/.env`, `config/htpasswd`, and the Cloudflare cert/key
if used) never go through git or the AMI. They're pushed to AWS
Secrets Manager from a laptop and pulled onto the instance by a
systemd unit on every app start, so a pushed update takes effect on
the next restart or reboot with no manual file copying. Non-secret
config files that are too large for Secrets Manager (e.g. an
invitation image — Secrets Manager caps a value at 64KB) follow the
same pull-on-start pattern but through S3 instead — see "Non-secret
config assets" below.

1. `cd infra && tofu init && tofu apply -var backup_bucket_name=YOUR-BUCKET`
   (optionally add `-var vpc_id=YOUR-VPC -var subnet_id=YOUR-SUBNET` to
   deploy into an existing VPC/subnet instead of the account default).
   This also creates four empty Secrets Manager containers
   (`rsvp-app/env`, `rsvp-app/htpasswd`, `rsvp-app/cf-cert`,
   `rsvp-app/cf-key`) and grants the instance role read access to
   them.
2. Verify SES sender identity for `SES_SENDER_EMAIL` in the AWS console
3. Point your domain's A record at the output `public_ip`
4. Prepare the secrets locally, then push them:
   ```bash
   cp config/.env.example config/.env        # edit values; set TLS_MODE
   ./scripts/create-admin.sh yourname        # writes config/htpasswd

   aws secretsmanager put-secret-value --secret-id rsvp-app/env --secret-string file://config/.env
   aws secretsmanager put-secret-value --secret-id rsvp-app/htpasswd --secret-string file://config/htpasswd
   ```
   Using Cloudflare TLS mode (see below)? Push the cert/key too —
   otherwise these can be left as empty secrets for now:
   ```bash
   aws secretsmanager put-secret-value --secret-id rsvp-app/cf-cert --secret-string file://config/cloudflare_origin_server.crt
   aws secretsmanager put-secret-value --secret-id rsvp-app/cf-key --secret-string file://config/cloudflare_origin_server.key
   ```
5. Connect via SSM Session Manager, clone this repo to `/opt/rsvp-app`:
   ```bash
   sudo -s
   cd /opt && git clone https://github.com/mddamato/rsvp.git rsvp-app
   ```
6. `sudo systemctl enable --now rsvp-app.service` — pulls the secrets
   just pushed into `config/` (via the `rsvp-secrets` unit it depends
   on), then brings the app up with `docker compose`. Both steps
   repeat on every future boot.
7. Using the default Let's Encrypt TLS mode: run
   `./scripts/init-letsencrypt.sh` once (needs DNS live first), then
   install the renewal cron — see `scripts/crontab.example`. Using
   Cloudflare TLS mode instead, see below; no certbot step needed.

### Non-secret config assets

Files that don't belong in git but also aren't secrets — currently
just the optional `EVENT_DETAILS_IMAGE` invitation image — go in
`config/assets/` and are pushed to the same S3 bucket used for
backups, under an `assets/` prefix the instance role can only read
(not the timestamped backup dumps at the bucket root):

```bash
aws s3 sync config/assets/ s3://YOUR-BUCKET/assets/
sudo systemctl restart rsvp-app.service   # picks it up, same as a pushed secret
```

`aws s3 sync ... --delete` on the push side removes a file from the
server the next time it starts if you also delete it locally first.
Pulled by the same `rsvp-secrets` systemd unit as the Secrets Manager
values (`scripts/fetch-assets.sh`, run right after
`scripts/fetch-secrets.sh` since it reads `BACKUP_S3_BUCKET` out of
the `config/.env` that step just wrote).

### Redeploying after a code change

```bash
git pull origin main
sudo systemctl restart rsvp-app.service
```

Re-fetches current secrets and rebuilds/restarts containers with the
new code, in one step.

### Applying a pushed secret without a reboot

```bash
sudo systemctl restart rsvp-app.service
```

Same command as above — it always re-fetches secrets before bringing
containers back up, so this is also how a `put-secret-value` pushed
from a laptop (updated `.env`, rotated `htpasswd`, a renewed
Cloudflare cert) takes effect immediately instead of waiting for the
next reboot.

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

### TLS: Let's Encrypt vs Cloudflare Origin Certificate

`TLS_MODE` in `config/.env` (pushed to the `rsvp-app/env` secret, per
step 4 above) picks the mode; `rsvp-app.service` selects the matching
`docker-compose` override automatically on every start — no manual
`docker compose -f ...` invocation needed on the server.

**Let's Encrypt** (`TLS_MODE=letsencrypt`, the default) — run
`./scripts/init-letsencrypt.sh` once DNS is live, and install the
renewal cron (`scripts/crontab.example`).

**Cloudflare Origin Certificate** (`TLS_MODE=cloudflare`) — valid for
the Cloudflare-to-origin hop, no certbot/renewal needed (15-year
expiry). Requires the domain proxied through Cloudflare with SSL/TLS
set to Full (strict):

1. In the Cloudflare dashboard: SSL/TLS > Origin Server > Create
   Certificate. Save the cert and key as
   `config/cloudflare_origin_server.crt` and
   `config/cloudflare_origin_server.key`, then push both to Secrets
   Manager (`rsvp-app/cf-cert`, `rsvp-app/cf-key` — step 4 above).
2. In the same Cloudflare dashboard page, enable **Authenticated
   Origin Pulls**. nginx is configured to require it
   (`ssl_verify_client on` against `config/cloudflare_origin_pull_ca.pem`,
   Cloudflare's published origin-pull CA — already in the repo, public,
   not a secret) so the origin can't be reached by going around
   Cloudflare directly. **Enable this before step 3** — until it's on,
   Cloudflare doesn't present a client certificate either, so nginx
   will reject Cloudflare's own requests too and the site goes down.
3. Set `TLS_MODE=cloudflare` in `config/.env`, push it
   (`aws secretsmanager put-secret-value --secret-id rsvp-app/env --secret-string file://config/.env`),
   then `sudo systemctl restart rsvp-app.service` on the instance to
   pick it up.

Switching back to Let's Encrypt is the same in reverse: set
`TLS_MODE=letsencrypt`, push, restart. To test either nginx config
directly without touching secrets or restarting the whole app, the
overrides still work standalone:
`docker compose -f docker-compose.yml -f docker-compose.cloudflare.yml up -d nginx`
(don't combine with `docker-compose.http-only.yml`).

## Emails

All outbound mail goes through SES (`SES_SENDER_EMAIL`/`AWS_REGION`
in `config/.env`) and needs the account out of the SES sandbox to
reach real recipient addresses — see the SES console. Three triggers,
and nothing else ever sends email:

- **RSVP submit/update** (`POST /rsvp`, i.e. every time anyone —
  admin-added or self-registered — submits or changes their answer
  via their personal link): a confirmation stating their current
  status (Attending/Declining), guests brought, and their note, if
  any. Sent every time, not just on change. Only if the invitee has
  an email on file — added by an admin, they won't unless the admin
  set one.
- **Self-registration** (`POST /self-register`): a welcome email with
  their new link/phrase and the status they just chose. Only if they
  filled in the optional email field.
- **`/recover`** ("lost your card?"): resends an existing invitee's
  link/phrase. Silent either way (same confirmation message whether
  the email matched or not, to prevent enumeration) — you can't tell
  from the UI whether one actually went out.

Adding a guest (single or CSV), editing one, or an admin confirming a
self-registered guest never sends anything.

Every email ends with a plain-text block of the current
`EVENT_TITLE`/`EVENT_SUBHEADING`/`EVENT_DETAILS`/`EVENT_CLOSING` (not
the image) so recipients have the event info to reference without
opening the site again. SES failures are always caught and logged
(`docker logs rsvp_app`, look for "SES send failed"), never surfaced
to the guest or allowed to break the RSVP/registration itself.

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
