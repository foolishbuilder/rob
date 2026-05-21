#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="/opt/rob-webhook/app"
SERVICE_NAME="rob-webhook-dev.service"
DEPLOY_BRANCH="${DEPLOY_BRANCH:-main}"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:8080/health}"

echo "[1/10] Entering ${APP_DIR}"
cd "$APP_DIR"

echo "[2/10] Checking repository state"
if [[ ! -d ".git" ]]; then
    echo "ERROR: ${APP_DIR} is not a git repository."
    exit 1
fi

echo "[3/10] Preserving local .env"
if [[ ! -f ".env" ]]; then
    echo "ERROR: ${APP_DIR}/.env does not exist."
    exit 1
fi

echo "[4/10] Fetching ${DEPLOY_BRANCH}"
git fetch origin "$DEPLOY_BRANCH"

echo "[5/10] Resetting tracked files to origin/${DEPLOY_BRANCH}"
# This intentionally discards local tracked-code changes on the server.
# Your .env is untracked/ignored and should not be touched.
git checkout "$DEPLOY_BRANCH" || git checkout -B "$DEPLOY_BRANCH" "origin/$DEPLOY_BRANCH"
git reset --hard "origin/$DEPLOY_BRANCH"
git clean -fd --exclude=.env --exclude=.venv

echo "[6/10] Preparing virtual environment"
if [[ ! -d ".venv" ]]; then
    python3 -m venv .venv
fi

echo "[7/10] Installing dependencies"
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt

echo "[8/10] Running compile and database checks"
PYTHONPATH=. .venv/bin/python -m compileall apps rob scripts
PYTHONPATH=. .venv/bin/python scripts/check_db.py

echo "[9/10] Restarting ${SERVICE_NAME}"
sudo systemctl restart "$SERVICE_NAME"

echo "[10/10] Running health check: ${HEALTH_URL}"
for attempt in {1..20}; do
    if curl -fsS "$HEALTH_URL"; then
        echo
        echo "Webhook deploy completed successfully."
        exit 0
    fi

    echo "Waiting for webhook service... attempt ${attempt}/20"
    sleep 2
done

echo "ERROR: Webhook health check failed."
echo
echo "Service status:"
sudo systemctl status "$SERVICE_NAME" --no-pager || true

echo
echo "Recent logs:"
sudo journalctl -u "$SERVICE_NAME" -n 120 --no-pager || true

exit 1
