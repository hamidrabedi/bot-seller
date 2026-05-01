#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

APP_USER="${SUDO_USER:-$USER}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${PROJECT_DIR}/.venv"
ENV_FILE="${PROJECT_DIR}/.env"
LOG_DIR="${PROJECT_DIR}/logs"
RUN_DIR="${PROJECT_DIR}/run"

ensure_cmd() {
  command -v "$1" >/dev/null 2>&1 || { echo "Missing command: $1"; exit 1; }
}

ensure_cmd "$PYTHON_BIN"
ensure_cmd systemctl || true

install_os_packages() {
  if command -v apt-get >/dev/null 2>&1; then
    echo "Installing OS packages..."
    if [[ $EUID -eq 0 ]]; then
      apt-get update
      apt-get install -y python3-venv python3-dev build-essential libjpeg-dev zlib1g-dev
    elif command -v sudo >/dev/null 2>&1; then
      sudo apt-get update
      sudo apt-get install -y python3-venv python3-dev build-essential libjpeg-dev zlib1g-dev
    else
      echo "Skipping OS packages (no root/sudo)."
    fi
  fi
}

gen_secret() {
  "$PYTHON_BIN" - <<'PY'
import secrets
print(secrets.token_urlsafe(50))
PY
}

write_env_if_missing() {
  if [[ -f "$ENV_FILE" ]]; then
    echo ".env exists, keeping current values."
    return
  fi

  echo "=== bot-seller production installer ==="
  read -rp "Domain or server IP for ALLOWED_HOSTS (comma separated): " HOSTS
  HOSTS=${HOSTS:-127.0.0.1,localhost}
  read -rp "Telegram bot token: " TG_TOKEN
  read -rp "Create default bank transfer FA text (single line): " BANK_FA
  read -rp "Create default bank transfer EN text (single line): " BANK_EN

  cat > "$ENV_FILE" <<ENV
DJANGO_SECRET_KEY=$(gen_secret)
DEBUG=0
ALLOWED_HOSTS=${HOSTS}
TELEGRAM_BOT_TOKEN=${TG_TOKEN}
BANK_TRANSFER_TEXT_FA=${BANK_FA}
BANK_TRANSFER_TEXT_EN=${BANK_EN}
ENV
  echo "Created $ENV_FILE"
}

setup_python() {
  "$PYTHON_BIN" -m venv "$VENV_DIR"
  source "$VENV_DIR/bin/activate"
  pip install --upgrade pip wheel
  pip install -r requirements.txt
}

prepare_runtime() {
  source "$VENV_DIR/bin/activate"
  mkdir -p "$LOG_DIR" "$RUN_DIR" media staticfiles
  python manage.py migrate
  python manage.py collectstatic --noinput
  python manage.py shell <<'PY'
import os
from core.models import PaymentSettings
fa = os.getenv('BANK_TRANSFER_TEXT_FA', 'شماره کارت: ...')
en = os.getenv('BANK_TRANSFER_TEXT_EN', 'Card Number: ...')
obj, _ = PaymentSettings.objects.get_or_create(title='default')
obj.bank_transfer_text_fa = fa
obj.bank_transfer_text_en = en
obj.is_active = True
obj.save()
print('PaymentSettings seeded/updated')
PY
}

write_systemd_units() {
  if ! command -v systemctl >/dev/null 2>&1; then
    echo "systemd not detected, using nohup fallback."
    return 1
  fi

  API_SERVICE="/etc/systemd/system/bot-seller-api.service"
  BOT_SERVICE="/etc/systemd/system/bot-seller-bot.service"

  cat > /tmp/bot-seller-api.service <<UNIT
[Unit]
Description=bot-seller Django API
After=network.target

[Service]
Type=simple
User=${APP_USER}
WorkingDirectory=${PROJECT_DIR}
EnvironmentFile=${ENV_FILE}
ExecStart=${VENV_DIR}/bin/gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3 --timeout 120
Restart=always
RestartSec=5
StandardOutput=append:${LOG_DIR}/api.log
StandardError=append:${LOG_DIR}/api.err.log

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
RestartSec=5
StandardOutput=append:${LOG_DIR}/bot.log
StandardError=append:${LOG_DIR}/bot.err.log

[Install]
WantedBy=multi-user.target
UNIT

  if [[ $EUID -eq 0 ]]; then
    mv /tmp/bot-seller-api.service "$API_SERVICE"
    mv /tmp/bot-seller-bot.service "$BOT_SERVICE"
  elif command -v sudo >/dev/null 2>&1; then
    sudo mv /tmp/bot-seller-api.service "$API_SERVICE"
    sudo mv /tmp/bot-seller-bot.service "$BOT_SERVICE"
  else
    echo "No permission to install systemd units, using nohup fallback."
    return 1
  fi

  if [[ $EUID -eq 0 ]]; then
    systemctl daemon-reload
    systemctl enable --now bot-seller-api.service
    systemctl enable --now bot-seller-bot.service
  else
    sudo systemctl daemon-reload
    sudo systemctl enable --now bot-seller-api.service
    sudo systemctl enable --now bot-seller-bot.service
  fi

  echo "Systemd services installed and started."
  return 0
}

nohup_fallback() {
  source "$VENV_DIR/bin/activate"
  pkill -f "gunicorn config.wsgi:application" || true
  pkill -f "manage.py run_telegram_bot" || true
  nohup "$VENV_DIR/bin/gunicorn" config.wsgi:application --bind 0.0.0.0:8000 --workers 2 > "$LOG_DIR/api.log" 2>&1 &
  nohup "$VENV_DIR/bin/python" manage.py run_telegram_bot > "$LOG_DIR/bot.log" 2>&1 &
  echo "Started with nohup fallback."
}

main() {
  install_os_packages
  write_env_if_missing
  setup_python
  prepare_runtime
  if ! write_systemd_units; then
    nohup_fallback
  fi

  echo "\nInstall complete."
  echo "Health: curl http://127.0.0.1:8000/api/health/"
  echo "API logs: tail -f ${LOG_DIR}/api.log"
  echo "BOT logs: tail -f ${LOG_DIR}/bot.log"
}

main "$@"
