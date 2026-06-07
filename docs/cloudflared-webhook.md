# Cloudflared: Webhook Routing

This guide configures Cloudflared for the production webhook host only.

Target routing:

- `https://throne.robthebot.com` -> `http://127.0.0.1:8080`
- Route the hostname to the local webhook origin so `/health`, `/webhook/*`, and `/throne/webhook/*` stay reachable through the same tunnel host.
- Optional second hostname: `https://age.robthebot.com` -> `http://127.0.0.1:8080`
- The age-verification backend lives on the same webhook app/origin; it is not a
  separate service.

Safety rules:

- Do not open port `8080` publicly.
- Do not commit tunnel tokens or credential JSON files.
- Do not copy random credential JSON files; the installer now performs a named-tunnel login flow and installs the exact tunnel credentials at `/etc/cloudflared/rob-webhook.json`.
- On Ubuntu/Debian, use the official Cloudflare apt repository (the installer handles this).

## Install sequence

```bash
sudo bash deploy/scripts/install-webhook.sh
sudo nano /opt/rob-webhook/app/.env
sudo chown "${USER}:rob" /opt/rob-webhook/app/.env
sudo chmod 0640 /opt/rob-webhook/app/.env
cd /opt/rob-webhook/app
set -a
source .env
set +a
PYTHONPATH=. .venv/bin/python -m scripts.check_db
sudo systemctl restart rob-webhook.service
curl -fsS http://127.0.0.1:8080/health
sudo bash deploy/scripts/install-cloudflared-webhook.sh
curl -I https://throne.robthebot.com/health
```

The Cloudflared installer now uses the browser-based `cloudflared tunnel login` flow and named tunnel routing. It does not prompt for a token-managed tunnel key.

## Verify services

```bash
sudo systemctl status cloudflared --no-pager
sudo journalctl -u cloudflared -n 100 --no-pager
sudo systemctl status rob-webhook.service --no-pager
sudo journalctl -u rob-webhook.service -n 100 --no-pager
```

## Optional: add `age.robthebot.com`

If you want a dedicated public hostname for age verification, point it to the
same tunnel and same origin:

```bash
cloudflared tunnel route dns rob-webhook age.robthebot.com
sudo nano /etc/cloudflared/config.yml
sudo systemctl restart cloudflared
curl -I https://age.robthebot.com/health
```

Add a second ingress block in `/etc/cloudflared/config.yml` so both hostnames
route to the same local webhook app:

```yaml
ingress:
  - hostname: throne.robthebot.com
    service: http://127.0.0.1:8080
  - hostname: age.robthebot.com
    service: http://127.0.0.1:8080
  - service: http_status:404
```

Then keep the runtime settings aligned:

- Bot host: `ROB_BACKEND_URL=https://age.robthebot.com`
- Webhook host: `YOTI_PUBLIC_BASE_URL=https://age.robthebot.com`

If you have not completed those DNS/tunnel steps yet, use
`https://throne.robthebot.com` for both the bot backend URL and Yoti public
base URL as the fast path.
