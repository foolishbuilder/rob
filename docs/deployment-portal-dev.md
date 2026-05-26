# Portal Dev Installation & Deployment Guide

This guide covers full setup for the Django portal in this repo, including first-time install, environment configuration, service wiring, and GitHub Actions deploy behavior.

## 1) Install the portal service on the server

Use the installer script:

```bash
# Run from a local checkout of this repo:
sudo bash deploy/scripts/install-portal-dev.sh

# Optional: override install root
# sudo APP_ROOT=/srv/rob-portal bash deploy/scripts/install-portal-dev.sh
```

The installer performs:

- package install (`python3`, `venv`, `pip`, `git`, `curl`)
- repo clone/update into `/opt/rob-portal/app`
- virtualenv creation and Python dependency install
- systemd unit install for `rob-portal-dev.service`
- compile checks
- optional migrations/startup when `.env` is fully configured

Primary script:

- `deploy/scripts/install-portal-dev.sh`

## 2) Configure portal environment (`/opt/rob-portal/app/.env`)

At minimum configure:

```dotenv
ROB_PORTAL_ENABLED=true
ROB_PORTAL_ENV=dev
ROB_PORTAL_BASE_URL=https://rob-dev.barecoding.com
ROB_PORTAL_ALLOWED_HOSTS=rob-dev.barecoding.com,127.0.0.1,localhost
ROB_PORTAL_CSRF_TRUSTED_ORIGINS=https://rob-dev.barecoding.com
ROB_PORTAL_SECRET_KEY=<long-random-secret>
ROB_PORTAL_SUPERADMIN_USER_IDS=<comma-separated-discord-ids>

DISCORD_CLIENT_ID=<oauth-client-id>
DISCORD_CLIENT_SECRET=<oauth-client-secret>
DISCORD_REDIRECT_URI=https://rob-dev.barecoding.com/portal/auth/discord/callback/

PORTAL_DATABASE_URL=postgresql://rob_dev_portal:<password>@<host>:<port>/rob_dev?sslmode=require
```

If `PORTAL_DATABASE_URL` is not used, `DATABASE_URL` may be used instead.

## 3) Nginx and Cloudflare

Add portal routes to Nginx:

```nginx
location /portal/static/ {
    alias /opt/rob-portal/app/portal/staticfiles/;
    access_log off;
    expires 1h;
}

location /portal/ {
    proxy_pass http://127.0.0.1:8090/portal/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_redirect off;
}
```

Then reload Nginx:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

For Cloudflare, use SSL mode `Full (strict)` and bypass cache for `/portal/*`.

## 4) Manual deploy command on server

Portal deploy script:

```bash
DEPLOY_BRANCH=main DEPLOY_REF=main /opt/rob-portal/deploy-portal-dev.sh
```

This script handles git update, dependency install, Rob migrations, portal migrations, static collection, checks, and service restart.

## 5) GitHub Actions deploy and SSH configuration

Portal deploy now uses the same SSH target and credentials as the webhook deploy workflow:

- `WEBHOOK_DEV_HOST`
- `WEBHOOK_DEV_USER`
- `WEBHOOK_DEV_SSH_KEY`
- `WEBHOOK_DEV_PORT`

This means portal and webhook are both deployed to the same server using one shared SSH secret set.

## 6) Verification commands

```bash
sudo systemctl status rob-portal-dev.service --no-pager
sudo journalctl -u rob-portal-dev.service -n 200 --no-pager
curl -I https://rob-dev.barecoding.com/portal/
```

## 7) Related files

- `deploy/scripts/install-portal-dev.sh`
- `deploy/scripts/deploy-portal-dev.sh`
- `deploy/systemd/rob-portal-dev.service`
- `.github/workflows/deploy-portal-dev.yml`
- `docs/web-portal.md`
