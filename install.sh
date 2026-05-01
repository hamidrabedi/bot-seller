#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-/opt/bot-seller}"
REPO_URL="${REPO_URL:-https://github.com/hamidrabedi/bot-seller.git}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
APP_USER="${APP_USER:-$(id -un)}"
ENV_FILE="$PROJECT_DIR/.env"
VENV_DIR="$PROJECT_DIR/.venv"
LOG_DIR="$PROJECT_DIR/logs"
BIN_LINK="/usr/local/bin/seller"
ACTION="${1:-install}"

usage() {
  cat <<USAGE
Usage: bash install.sh [install|update|remove]
Default action: install
USAGE
}

install_os_packages() {
  if ! command -v apt-get >/dev/null 2>&1; then return; fi
  if [[ $EUID -eq 0 ]]; then
    apt-get update
    apt-get install -y git curl python3 python3-venv python3-dev build-essential libjpeg-dev zlib1g-dev
  elif command -v sudo >/dev/null 2>&1; then
    sudo apt-get update
    sudo apt-get install -y git curl python3 python3-venv python3-dev build-essential libjpeg-dev zlib1g-dev
  fi
}

gen_secret() { "$PYTHON_BIN" - <<'PY'
import secrets; print(secrets.token_urlsafe(50))
PY
}

default_hosts() {
  ip=$(hostname -I 2>/dev/null | awk '{print $1}') || true
  [[ -n "${ip:-}" ]] && echo "127.0.0.1,localhost,${ip}" || echo "127.0.0.1,localhost"
}

clone_or_update_repo() {
  if [[ ! -d "$PROJECT_DIR/.git" ]]; then
    mkdir -p "$(dirname "$PROJECT_DIR")"
    git clone "$REPO_URL" "$PROJECT_DIR"
  else
    git -C "$PROJECT_DIR" pull --ff-only || true
  fi
}

write_env() {
  SECRET="${DJANGO_SECRET_KEY:-$(gen_secret)}"
  HOSTS="${ALLOWED_HOSTS:-$(default_hosts)}"
  TG_TOKEN="${TELEGRAM_BOT_TOKEN:-}"
  BANK_FA="${BANK_TRANSFER_TEXT_FA:-شماره کارت: 0000-0000-0000-0000 | به نام: YOUR NAME}"
  BANK_EN="${BANK_TRANSFER_TEXT_EN:-Card Number: 0000-0000-0000-0000 | Holder: YOUR NAME}"
  [[ -f "$ENV_FILE" ]] && return
  cat > "$ENV_FILE" <<ENV
DJANGO_SECRET_KEY=${SECRET}
DEBUG=0
ALLOWED_HOSTS=${HOSTS}
TELEGRAM_BOT_TOKEN=${TG_TOKEN}
BANK_TRANSFER_TEXT_FA=${BANK_FA}
BANK_TRANSFER_TEXT_EN=${BANK_EN}
ENV
}

setup_python() {
  cd "$PROJECT_DIR"
  "$PYTHON_BIN" -m venv "$VENV_DIR"
  source "$VENV_DIR/bin/activate"
  pip install --upgrade pip wheel
  pip install -r requirements.txt
}

seed_defaults() {
  cd "$PROJECT_DIR"
  source "$VENV_DIR/bin/activate"
  mkdir -p "$LOG_DIR" media staticfiles
  python manage.py migrate
  python manage.py collectstatic --noinput
  python manage.py shell <<'PY'
import os
from core.models import PaymentSettings, SystemConfig
fa=os.getenv('BANK_TRANSFER_TEXT_FA','شماره کارت: ...')
en=os.getenv('BANK_TRANSFER_TEXT_EN','Card Number: ...')
token=os.getenv('TELEGRAM_BOT_TOKEN','')
ps,_=PaymentSettings.objects.get_or_create(title='default')
ps.bank_transfer_text_fa=fa; ps.bank_transfer_text_en=en; ps.is_active=True; ps.save()
sc,_=SystemConfig.objects.get_or_create(title='default')
if token: sc.telegram_bot_token=token
sc.service_api_name='bot-seller-api'; sc.service_bot_name='bot-seller-bot'; sc.save()
PY
}

systemd_usable() { command -v systemctl >/dev/null 2>&1 && systemctl list-units >/dev/null 2>&1; }

nohup_fallback() {
  cd "$PROJECT_DIR"; source "$VENV_DIR/bin/activate"
  "$VENV_DIR/bin/gunicorn" config.wsgi:application --bind 0.0.0.0:8000 --workers 2 --daemon --access-logfile "$LOG_DIR/api.log" --error-logfile "$LOG_DIR/api.err.log"
  if [[ -n "${TELEGRAM_BOT_TOKEN:-}" ]]; then
    nohup "$VENV_DIR/bin/python" manage.py run_telegram_bot > "$LOG_DIR/bot.log" 2>&1 &
  fi
}

install_services() {
  if ! systemd_usable; then nohup_fallback; return; fi
  cat > /tmp/bot-seller-api.service <<UNIT
[Unit]
Description=bot-seller API
After=network.target
[Service]
Type=simple
User=${APP_USER}
WorkingDirectory=${PROJECT_DIR}
EnvironmentFile=${ENV_FILE}
ExecStart=${VENV_DIR}/bin/gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3 --timeout 120
Restart=always
[Install]
WantedBy=multi-user.target
UNIT
  cat > /tmp/bot-seller-bot.service <<UNIT
[Unit]
Description=bot-seller Telegram bot
After=network.target bot-seller-api.service
[Service]
Type=simple
User=${APP_USER}
WorkingDirectory=${PROJECT_DIR}
EnvironmentFile=${ENV_FILE}
ExecStart=${VENV_DIR}/bin/python manage.py run_telegram_bot
Restart=always
[Install]
WantedBy=multi-user.target
UNIT
  if [[ $EUID -eq 0 ]]; then
    mv /tmp/bot-seller-api.service /etc/systemd/system/bot-seller-api.service
    mv /tmp/bot-seller-bot.service /etc/systemd/system/bot-seller-bot.service
    systemctl daemon-reload
    systemctl enable --now bot-seller-api.service
    [[ -n "${TELEGRAM_BOT_TOKEN:-}" ]] && systemctl enable --now bot-seller-bot.service || true
  else
    sudo mv /tmp/bot-seller-api.service /etc/systemd/system/bot-seller-api.service
    sudo mv /tmp/bot-seller-bot.service /etc/systemd/system/bot-seller-bot.service
    sudo systemctl daemon-reload
    sudo systemctl enable --now bot-seller-api.service
    [[ -n "${TELEGRAM_BOT_TOKEN:-}" ]] && sudo systemctl enable --now bot-seller-bot.service || true
  fi
}

install_cli_link() {
  if [[ $EUID -eq 0 ]]; then
    cat > "$BIN_LINK" <<WRAP
#!/usr/bin/env bash
exec bash ${PROJECT_DIR}/install.sh "\$@"
WRAP
    chmod +x "$BIN_LINK"
  else
    sudo tee "$BIN_LINK" >/dev/null <<WRAP
#!/usr/bin/env bash
exec bash ${PROJECT_DIR}/install.sh "\$@"
WRAP
    sudo chmod +x "$BIN_LINK"
  fi
}

stop_services() {
  if systemd_usable; then
    ( [[ $EUID -eq 0 ]] && systemctl disable --now bot-seller-bot.service bot-seller-api.service ) || sudo systemctl disable --now bot-seller-bot.service bot-seller-api.service || true
    ( [[ $EUID -eq 0 ]] && rm -f /etc/systemd/system/bot-seller-api.service /etc/systemd/system/bot-seller-bot.service && systemctl daemon-reload ) || sudo rm -f /etc/systemd/system/bot-seller-api.service /etc/systemd/system/bot-seller-bot.service || true
  fi
  pkill -f 'gunicorn config.wsgi:application' || true
  pkill -f 'manage.py run_telegram_bot' || true
}

install_action() { install_os_packages; clone_or_update_repo; write_env; setup_python; seed_defaults; install_services; install_cli_link; echo 'Installed.'; }
update_action() { clone_or_update_repo; setup_python; seed_defaults; install_services; install_cli_link; echo 'Updated.'; }
remove_action() { stop_services; rm -rf "$PROJECT_DIR"; ( [[ $EUID -eq 0 ]] && rm -f "$BIN_LINK" ) || sudo rm -f "$BIN_LINK" || true; echo 'Removed.'; }

case "$ACTION" in
  install) install_action ;;
  update) update_action ;;
  remove) remove_action ;;
  -h|--help|help) usage ;;
  *) echo "Unknown action: $ACTION"; usage; exit 1 ;;
esac
