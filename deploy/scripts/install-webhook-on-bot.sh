#!/usr/bin/env bash
set -Eeuo pipefail

# ---------------------------------------------------------------------------
# install-webhook-on-bot.sh — run the Throne webhook receiver ON the bot host,
# reusing the bot's existing checkout and virtualenv.
#
# The standard combined deploy (docs/deployment-combined.md) installs the bot
# and the webhook as two separate app dirs, each with its own git clone and its
# own venv of the SAME code. On a single host that is wasteful: identical
# dependencies installed twice, two trees to keep in sync.
#
# This script instead co-locates the webhook as a lightweight second service:
#   - reuses /opt/rob-bot/app (code) and /opt/rob-bot/app/.venv (dependencies)
#   - keeps a separate webhook .env (DB user + signing settings differ)
#   - talks to the local bot ops bridge over loopback (127.0.0.1:8811)
#   - runs as its own systemd unit (rob-webhook.service)
#
# It "pulls details" for the webhook .env from the bot's existing .env (shared
# ROB_OPS_SECRET, log level, public base URL, DB host/name) so you don't
# re-enter them. The webhook DB *password* is the one secret it cannot derive;
# supply it with --webhook-db-url, --from-env, or by editing the .env after.
#
# The database stays remote. Safe to re-run; backs up the webhook .env it edits.
#
# Usage:
#   sudo bash deploy/scripts/install-webhook-on-bot.sh [options]
#
# Options:
#   --bot-dir DIR         Bot app dir (code + venv)   (default: /opt/rob-bot/app)
#   --webhook-env PATH    Webhook env file            (default: /opt/rob-webhook/.env)
#   --port N              Webhook listen port         (default: 8080)
#   --from-env FILE       Import an existing webhook .env (e.g. scp'd from the
#                         old webhook host), then force the loopback wiring.
#   --webhook-db-url URL  Set the webhook DATABASE_URL explicitly.
#   --rotate-secret       Generate a fresh shared ROB_OPS_SECRET (writes both).
#   --no-start            Install + enable only; do not start the service.
#   --dry-run             Show the plan; write nothing.
#   --yes, -y             Do not prompt for confirmation.
#   -h, --help            Show this help.
# ---------------------------------------------------------------------------

BOT_DIR="${BOT_DIR:-/opt/rob-bot/app}"
WEBHOOK_ENV="${WEBHOOK_ENV:-/opt/rob-webhook/.env}"
WEBHOOK_PORT="${WEBHOOK_PORT:-8080}"
WEBHOOK_HOST="127.0.0.1"
SERVICE_NAME="${SERVICE_NAME:-rob-webhook.service}"
BOT_SERVICE="${BOT_SERVICE:-rob-bot.service}"
RUNTIME_USER="${RUNTIME_USER:-rob}"
RUNTIME_GROUP="${RUNTIME_GROUP:-rob}"
DEPLOY_USER="${DEPLOY_USER:-${SUDO_USER:-}}"
SUDOERS_PATH="${SUDOERS_PATH:-/etc/sudoers.d/rob-webhook-deploy}"
DEFAULT_OPS_PORT="8811"

FROM_ENV=""
WEBHOOK_DB_URL=""
ROTATE_SECRET="false"
DO_START="true"
DRY_RUN="false"
ASSUME_YES="false"

log()  { printf '[install-webhook-on-bot] %s\n' "$*"; }
warn() { printf '[install-webhook-on-bot] WARNING: %s\n' "$*" >&2; }
die()  { printf '[install-webhook-on-bot] error: %s\n' "$*" >&2; exit 1; }

usage() { sed -n '4,40p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; }

parse_args() {
  while (($#)); do
    case "$1" in
      --bot-dir) shift; [[ $# -gt 0 ]] || die "--bot-dir needs a value"; BOT_DIR="$1" ;;
      --bot-dir=*) BOT_DIR="${1#*=}" ;;
      --webhook-env) shift; [[ $# -gt 0 ]] || die "--webhook-env needs a value"; WEBHOOK_ENV="$1" ;;
      --webhook-env=*) WEBHOOK_ENV="${1#*=}" ;;
      --port) shift; [[ $# -gt 0 ]] || die "--port needs a value"; WEBHOOK_PORT="$1" ;;
      --port=*) WEBHOOK_PORT="${1#*=}" ;;
      --from-env) shift; [[ $# -gt 0 ]] || die "--from-env needs a value"; FROM_ENV="$1" ;;
      --from-env=*) FROM_ENV="${1#*=}" ;;
      --webhook-db-url) shift; [[ $# -gt 0 ]] || die "--webhook-db-url needs a value"; WEBHOOK_DB_URL="$1" ;;
      --webhook-db-url=*) WEBHOOK_DB_URL="${1#*=}" ;;
      --rotate-secret) ROTATE_SECRET="true" ;;
      --no-start) DO_START="false" ;;
      --dry-run) DRY_RUN="true" ;;
      --yes|-y) ASSUME_YES="true" ;;
      -h|--help) usage; exit 0 ;;
      *) die "unknown option: $1 (try --help)" ;;
    esac
    shift || true
  done
  [[ "${WEBHOOK_PORT}" =~ ^[0-9]+$ ]] || die "--port must be numeric."
}

ensure_root() {
  [[ "${EUID}" -eq 0 ]] || die "Run this script with sudo or as root."
}

# -- env helpers (consistent with fix-me.sh) --------------------------------

read_env_var() {
  local file="$1" key="$2" line=""
  [[ -f "${file}" ]] || { printf ''; return; }
  line="$(grep -E "^${key}=" "${file}" | tail -n 1 || true)"
  line="${line#*=}"
  line="${line%$'\r'}"
  line="${line#\"}"; line="${line%\"}"
  line="${line#\'}"; line="${line%\'}"
  printf '%s' "${line}"
}

# upsert_env_var FILE KEY VALUE — replace the first KEY= line in place, or
# append KEY=VALUE if absent. Comment lines (#KEY=) are left untouched.
upsert_env_var() {
  local file="$1" key="$2" value="$3" tmp
  tmp="$(mktemp)"
  KEY="${key}" VALUE="${value}" awk '
    BEGIN { key = ENVIRON["KEY"]; value = ENVIRON["VALUE"]; done = 0 }
    {
      if (!done && $0 ~ "^" key "=") { print key "=" value; done = 1; next }
      print
    }
    END { if (!done) print key "=" value }
  ' "${file}" > "${tmp}"
  mv "${tmp}" "${file}"
}

generate_secret() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex 32
  elif command -v python3 >/dev/null 2>&1; then
    python3 -c 'import secrets; print(secrets.token_hex(32))'
  else
    die "Need openssl or python3 to generate ROB_OPS_SECRET."
  fi
}

is_placeholder() {
  local value="$1"
  [[ -z "${value}" || "${value}" == "replace" || "${value}" == *replace* ]]
}

# Derive a webhook DATABASE_URL from the bot's: keep host/db/params, swap the
# *_bot user to *_webhook (or default prod_rob_webhook), blank the password.
derive_webhook_db_url() {
  local bot_url="$1"
  [[ -n "${bot_url}" ]] || { printf ''; return; }
  BOT_URL="${bot_url}" python3 - <<'PY'
import os
from urllib.parse import urlsplit, urlunsplit

url = os.environ["BOT_URL"]
parts = urlsplit(url)
user = parts.username or "prod_rob_bot"
if user.endswith("_bot"):
    new_user = user[: -len("_bot")] + "_webhook"
else:
    new_user = "prod_rob_webhook"

host = parts.hostname or ""
netloc = f"{new_user}:replace@{host}"
if parts.port:
    netloc += f":{parts.port}"

print(urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment)))
PY
}

# -- validation -------------------------------------------------------------

validate_bot_install() {
  [[ -d "${BOT_DIR}" ]]            || die "Bot app dir not found: ${BOT_DIR} (run install-bot.sh first, or pass --bot-dir)."
  [[ -d "${BOT_DIR}/.git" ]]       || die "${BOT_DIR} is not a git checkout."
  [[ -f "${BOT_DIR}/.env" ]]       || die "Missing ${BOT_DIR}/.env — set up the bot first."
  [[ -x "${BOT_DIR}/.venv/bin/python" ]] || die "Bot venv missing at ${BOT_DIR}/.venv — run install-bot.sh first."
  [[ -f "${BOT_DIR}/apps/webhook/main.py" ]] || die "Webhook entrypoint not found in ${BOT_DIR}; is this the Rob repo?"

  # Reusing the bot tree only works if the webhook env lives OUTSIDE it:
  # deploy-bot.sh runs `git clean -fd --exclude=.env --exclude=.venv`, which
  # would delete an untracked env file kept inside the bot app dir.
  case "$(readlink -f "${WEBHOOK_ENV}" 2>/dev/null || printf '%s' "${WEBHOOK_ENV}")" in
    "$(readlink -f "${BOT_DIR}" 2>/dev/null || printf '%s' "${BOT_DIR}")"/*)
      die "--webhook-env must live OUTSIDE ${BOT_DIR} (a bot redeploy would delete it). Try /opt/rob-webhook/.env." ;;
  esac
}

ensure_runtime_user() {
  if ! getent group "${RUNTIME_GROUP}" >/dev/null 2>&1; then
    log "Creating runtime group ${RUNTIME_GROUP}"
    [[ "${DRY_RUN}" == "true" ]] || groupadd --system "${RUNTIME_GROUP}"
  fi
  if ! id "${RUNTIME_USER}" >/dev/null 2>&1; then
    log "Creating runtime user ${RUNTIME_USER}"
    [[ "${DRY_RUN}" == "true" ]] || useradd --system --gid "${RUNTIME_GROUP}" \
      --home-dir "$(dirname "${WEBHOOK_ENV}")" --shell /usr/sbin/nologin "${RUNTIME_USER}"
  fi
}

# -- build the webhook env --------------------------------------------------

resolve_shared_secret() {
  # stdout is captured; log only to stderr.
  local bot_secret
  bot_secret="$(read_env_var "${BOT_DIR}/.env" ROB_OPS_SECRET)"
  if [[ "${ROTATE_SECRET}" == "true" ]]; then
    log "Rotating ROB_OPS_SECRET (fresh shared value for bot + webhook)." >&2
    generate_secret
    return
  fi
  if ! is_placeholder "${bot_secret}"; then
    printf '%s' "${bot_secret}"
    return
  fi
  log "Bot has no usable ROB_OPS_SECRET; generating a shared one." >&2
  generate_secret
}

write_webhook_env() {
  local secret="$1"
  local tmp staged
  staged="$(mktemp)"

  # 1. Seed the staged env from the chosen source.
  if [[ -n "${FROM_ENV}" ]]; then
    [[ -f "${FROM_ENV}" ]] || die "--from-env file not found: ${FROM_ENV}"
    log "Importing webhook env from ${FROM_ENV}"
    cp "${FROM_ENV}" "${staged}"
  elif [[ -f "${WEBHOOK_ENV}" ]]; then
    log "Updating existing webhook env at ${WEBHOOK_ENV}"
    cp "${WEBHOOK_ENV}" "${staged}"
  else
    log "Deriving a fresh webhook env from ${BOT_DIR}/.env"
    : > "${staged}"
  fi

  # 2. Decide DATABASE_URL (priority: flag > imported/existing real value > derived).
  local db_url existing_db
  existing_db="$(read_env_var "${staged}" DATABASE_URL)"
  if [[ -n "${WEBHOOK_DB_URL}" ]]; then
    db_url="${WEBHOOK_DB_URL}"
  elif ! is_placeholder "${existing_db}"; then
    db_url="${existing_db}"
  else
    db_url="$(derive_webhook_db_url "$(read_env_var "${BOT_DIR}/.env" DATABASE_URL)")"
    [[ -n "${db_url}" ]] || db_url="postgresql://prod_rob_webhook:replace@replace:25060/rob_prod?sslmode=require"
  fi

  # 3. Fill defaults for any keys still missing (pulled from the bot where sensible).
  local app_env log_level base_url
  app_env="$(read_env_var "${staged}" APP_ENV)";   [[ -n "${app_env}"  ]] || app_env="$(read_env_var "${BOT_DIR}/.env" APP_ENV)";   [[ -n "${app_env}"  ]] || app_env="prod"
  log_level="$(read_env_var "${staged}" LOG_LEVEL)"; [[ -n "${log_level}" ]] || log_level="$(read_env_var "${BOT_DIR}/.env" LOG_LEVEL)"; [[ -n "${log_level}" ]] || log_level="INFO"
  base_url="$(read_env_var "${staged}" THRONE_WEBHOOK_BASE_URL)"; [[ -n "${base_url}" ]] || base_url="$(read_env_var "${BOT_DIR}/.env" THRONE_WEBHOOK_BASE_URL)"; [[ -n "${base_url}" ]] || base_url="https://throne.robthebot.com"

  set_default() { local k="$1" v="$2"; [[ -n "$(read_env_var "${staged}" "${k}")" ]] || upsert_env_var "${staged}" "${k}" "${v}"; }
  set_default APP_ENV "${app_env}"
  set_default LOG_LEVEL "${log_level}"
  set_default THRONE_WEBHOOK_BASE_URL "${base_url}"
  set_default THRONE_WEBHOOK_REQUIRE_SIGNATURE "false"
  set_default THRONE_PUBLIC_KEY_PEM ""
  set_default THRONE_WEBHOOK_DEBUG_LOG_PAYLOAD "false"
  set_default THRONE_WEBHOOK_TIMESTAMP_HEADER "X-Signature-Timestamp"
  set_default THRONE_WEBHOOK_SIGNATURE_HEADER "X-Signature-Ed25519"
  set_default THRONE_WEBHOOK_SIGNED_MESSAGE_FORMAT "timestamp_dot_body"
  set_default THRONE_WEBHOOK_MAX_TIMESTAMP_SKEW_SECONDS "300"
  set_default THRONE_PARSE_TEST_SENDS_AS_REAL_SENDS "false"

  # 4. Force the managed keys that make co-location correct (always overwritten).
  local ops_port notify_url
  ops_port="$(read_env_var "${BOT_DIR}/.env" ROB_OPS_PORT)"; [[ -n "${ops_port}" ]] || ops_port="${DEFAULT_OPS_PORT}"
  notify_url="http://127.0.0.1:${ops_port}/ops/sends/process"
  upsert_env_var "${staged}" DATABASE_URL "${db_url}"
  upsert_env_var "${staged}" THRONE_WEBHOOK_HOST "${WEBHOOK_HOST}"
  upsert_env_var "${staged}" THRONE_WEBHOOK_PORT "${WEBHOOK_PORT}"
  upsert_env_var "${staged}" ROB_BOT_NOTIFY_URL "${notify_url}"
  upsert_env_var "${staged}" ROB_OPS_SECRET "${secret}"
  # This host must never hold a Discord token on the webhook side.
  if [[ -n "$(read_env_var "${staged}" DISCORD_TOKEN)" ]]; then
    warn "Removing DISCORD_TOKEN from the webhook env (webhook never connects to Discord)."
    grep -v -E '^DISCORD_TOKEN=' "${staged}" > "${staged}.clean" && mv "${staged}.clean" "${staged}"
  fi

  if [[ "${DRY_RUN}" == "true" ]]; then
    log "DRY-RUN webhook env (${WEBHOOK_ENV}) would be:"
    sed -E 's/^(DATABASE_URL=postgresql:\/\/[^:]+:)[^@]*@/\1*****@/; s/^(ROB_OPS_SECRET=).*/\1*****/' "${staged}" | sed 's/^/          /'
    rm -f "${staged}"
    return
  fi

  install -d -m 0750 -o "${DEPLOY_USER:-root}" -g "${RUNTIME_GROUP}" "$(dirname "${WEBHOOK_ENV}")"
  if [[ -f "${WEBHOOK_ENV}" ]]; then
    local backup="${WEBHOOK_ENV}.bak.$(date +%Y%m%d-%H%M%S)"
    cp "${WEBHOOK_ENV}" "${backup}"
    log "Backed up existing webhook env to ${backup}"
  fi
  install -m 0640 -o "${DEPLOY_USER:-root}" -g "${RUNTIME_GROUP}" "${staged}" "${WEBHOOK_ENV}"
  rm -f "${staged}"
  log "Wrote ${WEBHOOK_ENV}"
}

# -- systemd ----------------------------------------------------------------

install_unit() {
  local unit="/etc/systemd/system/${SERVICE_NAME}"
  if [[ "${DRY_RUN}" == "true" ]]; then
    log "DRY-RUN would install ${unit} (ExecStart uses ${BOT_DIR}/.venv, EnvironmentFile=${WEBHOOK_ENV})."
    return
  fi
  log "Installing systemd unit ${unit}"
  cat > "${unit}" <<EOF
[Unit]
Description=Rob Webhook Service (co-located on the bot host)
After=network.target ${BOT_SERVICE}
Wants=${BOT_SERVICE}

[Service]
Type=simple
User=${RUNTIME_USER}
Group=${RUNTIME_GROUP}
WorkingDirectory=${BOT_DIR}
EnvironmentFile=${WEBHOOK_ENV}
Environment=PYTHONPATH=${BOT_DIR}
ExecStart=${BOT_DIR}/.venv/bin/python -m apps.webhook.main
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
  chmod 0644 "${unit}"
  systemctl daemon-reload
  systemctl enable "${SERVICE_NAME}" >/dev/null 2>&1 || true
}

install_sudoers() {
  [[ -n "${DEPLOY_USER}" ]] || return 0
  if [[ "${DRY_RUN}" == "true" ]]; then
    log "DRY-RUN would allow ${DEPLOY_USER} to restart/status ${SERVICE_NAME} via sudo."
    return
  fi
  log "Installing sudoers entry so '${DEPLOY_USER}' can manage ${SERVICE_NAME} (used by 'rob restart webhook')"
  cat > "${SUDOERS_PATH}" <<EOF
Cmnd_Alias ROB_WEBHOOK_DEPLOY = /bin/systemctl restart ${SERVICE_NAME}, /usr/bin/systemctl restart ${SERVICE_NAME}, /bin/systemctl --no-pager --full status ${SERVICE_NAME}, /usr/bin/systemctl --no-pager --full status ${SERVICE_NAME}
${DEPLOY_USER} ALL=(root) NOPASSWD: ROB_WEBHOOK_DEPLOY
EOF
  chmod 0440 "${SUDOERS_PATH}"
  command -v visudo >/dev/null 2>&1 && visudo -cf "${SUDOERS_PATH}" >/dev/null || true
}

# -- verification -----------------------------------------------------------

run_db_check() {
  [[ "${DRY_RUN}" == "true" ]] && return
  log "Running webhook DB check (profile=webhook)"
  ( cd "${BOT_DIR}" \
    && set -a && . "${WEBHOOK_ENV}" && set +a \
    && PYTHON_DOTENV_DISABLED=1 ROB_CHECK_DB_PROFILE=webhook PYTHONPATH=. \
       .venv/bin/python scripts/check_db.py ) \
    || warn "Webhook DB check failed — confirm the prod_rob_webhook credentials/grants before relying on it."
}

start_and_health_check() {
  [[ "${DRY_RUN}" == "true" ]] && return
  if [[ "${DO_START}" != "true" ]]; then
    log "--no-start given; service enabled but not started."
    return
  fi
  local db_url
  db_url="$(read_env_var "${WEBHOOK_ENV}" DATABASE_URL)"
  if is_placeholder "${db_url}"; then
    log "Webhook DATABASE_URL still has a 'replace' placeholder; enabling without starting."
    log "Set the prod_rob_webhook password in ${WEBHOOK_ENV}, then: sudo systemctl restart ${SERVICE_NAME}"
    return
  fi
  log "Starting ${SERVICE_NAME}"
  systemctl restart "${SERVICE_NAME}"
  local url="http://${WEBHOOK_HOST}:${WEBHOOK_PORT}/health"
  local i
  for ((i=1; i<=15; i++)); do
    if curl -fsS --max-time 5 "${url}" >/dev/null 2>&1; then
      log "Webhook health OK: ${url}"
      return
    fi
    sleep 2
  done
  warn "Webhook health check did not pass at ${url}."
  systemctl --no-pager --full status "${SERVICE_NAME}" | sed -n '1,12p' || true
  journalctl -u "${SERVICE_NAME}" -n 40 --no-pager || true
}

confirm() {
  [[ "${ASSUME_YES}" == "true" || "${DRY_RUN}" == "true" ]] && return 0
  [[ -t 0 ]] || die "Refusing to run non-interactively without --yes (or use --dry-run)."
  local reply
  read -r -p "[install-webhook-on-bot] Co-locate the webhook on this host now? [y/N] " reply
  [[ "${reply}" =~ ^[Yy]$ ]] || die "Aborted by user."
}

print_summary() {
  local dry_suffix=""
  [[ "${DRY_RUN}" == "true" ]] && dry_suffix=" (dry-run — nothing written)"
  cat <<EOF

[install-webhook-on-bot] Done${dry_suffix}.

  Code + venv (reused):  ${BOT_DIR}  /  ${BOT_DIR}/.venv
  Webhook env:           ${WEBHOOK_ENV}
  Service:               ${SERVICE_NAME}  (listens ${WEBHOOK_HOST}:${WEBHOOK_PORT})
  Webhook -> bot:        http://127.0.0.1:${DEFAULT_OPS_PORT}/ops/sends/process (shared ROB_OPS_SECRET)
  Database:              remote, unchanged (webhook uses the prod_rob_webhook user)

No second clone, no second virtualenv — the webhook runs the same code the bot
already deployed, so a normal bot redeploy keeps both in version lock-step.

Next steps:
  1. Set the prod_rob_webhook password in ${WEBHOOK_ENV} if it still says 'replace'.
  2. Point the public Throne URL at this host's :${WEBHOOK_PORT}
     (cloudflared -> http://127.0.0.1:${WEBHOOK_PORT}; see docs/cloudflared-webhook.md).
     Do NOT expose ${WEBHOOK_PORT} or ${DEFAULT_OPS_PORT} publicly.
  3. Verify any time:  rob status   (and:  rob logs webhook)
  4. After a bot redeploy:  sudo systemctl restart ${SERVICE_NAME}  (or: rob restart all)
EOF
}

main() {
  parse_args "$@"
  ensure_root
  command -v systemctl >/dev/null 2>&1 || die "systemctl is required."
  command -v python3 >/dev/null 2>&1 || die "python3 is required."

  validate_bot_install
  ensure_runtime_user

  local secret
  secret="$(resolve_shared_secret)"

  log "Plan: co-locate ${SERVICE_NAME} on this host, reusing ${BOT_DIR} (code + venv); DB stays remote."
  confirm

  write_webhook_env "${secret}"

  # Keep the bot and webhook on the same shared secret.
  if [[ "${DRY_RUN}" != "true" ]]; then
    local bot_secret
    bot_secret="$(read_env_var "${BOT_DIR}/.env" ROB_OPS_SECRET)"
    if [[ "${bot_secret}" != "${secret}" ]]; then
      cp "${BOT_DIR}/.env" "${BOT_DIR}/.env.bak.$(date +%Y%m%d-%H%M%S)"
      upsert_env_var "${BOT_DIR}/.env" ROB_OPS_SECRET "${secret}"
      log "Synced shared ROB_OPS_SECRET into ${BOT_DIR}/.env (restart the bot to apply: rob restart bot)."
    fi
  fi

  install_unit
  install_sudoers
  run_db_check
  start_and_health_check
  print_summary
}

main "$@"
