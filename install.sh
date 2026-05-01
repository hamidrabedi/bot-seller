#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-/opt/bot-seller}"
REPO_URL="${REPO_URL:-https://github.com/your-org/bot-seller.git}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
APP_USER="${APP_USER:-$(id -un)}"
ENV_FILE="$PROJECT_DIR/.env"
VENV_DIR="$PROJECT_DIR/.venv"
LOG_DIR="$PROJECT_DIR/logs"

# Optional env inputs for zero-touch installs:
# TELEGRAM_BOT_TOKEN, ALLOWED_HOSTS, BANK_TRANSFER_TEXT_FA, BANK_TRANSFER_TEXT_EN

if [[ ! -d "$PROJECT_DIR/.git" ]]; then
  echo "Cloning project into $PROJECT_DIR"
  mkdir -p "$(dirname "$PROJECT_DIR")"
  git clone "$REPO_URL" "$PROJECT_DIR"
fi
cd "$PROJECT_DIR"

install_os_packages() {
  if ! command -v apt-get >/dev/null 2>&1; then
    return
  fi
  if [[ $EUID -eq 0 ]]; then
    apt-get update
    apt-get install -y git curl python3 python3-venv python3-dev build-essential libjpeg-dev zlib1g-dev
  elif command -v sudo >/dev/null 2>&1; then
    sudo apt-get update
    sudo apt-get install -y git curl python3 python3-venv python3-dev build-essential libjpeg-dev zlib1g-dev
  fi
}

gen_secret() {
  "$PYTHON_BIN" - <<'PY'
import secrets
print(secrets.token_urlsafe(50))
PY
}

default_hosts() {
  ip=$(hostname -I 2>/dev/null | awk '{print $1}') || true
  if [[ -n "${ip:-}" ]]; then
    echo "127.0.0.1,localhost,${ip}"
  else
    echo "127.0.0.1,localhost"
  fi
}

write_env() {
  SECRET="${DJANGO_SECRET_KEY:-$(gen_secret)}"
  HOSTS="${ALLOWED_HOSTS:-$(default_hosts)}"
  TG_TOKEN="${TELEGRAM_BOT_TOKEN:-}"
  BANK_FA="${BANK_TRANSFER_TEXT_FA:-شماره کارت: 0000-0000-0000-0000 | به نام: YOUR NAME}"
  BANK_EN="${BANK_TRANSFER_TEXT_EN:-Card Number: 0000-0000-0000-0000 | Holder: YOUR NAME}"

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
  "$PYTHON_BIN" -m venv "$VENV_DIR"
  source "$VENV_DIR/bin/activate"
  pip install --upgrade pip wheel
  pip install -r requirements.txt
}

seed_defaults() {
  source "$VENV_DIR/bin/activate"
  mkdir -p "$LOG_DIR" media staticfiles
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
print('PaymentSettings ready')
PY
}

install_services() {
  API_SERVICE=/etc/systemd/system/bot-seller-api.service
  BOT_SERVICE=/etc/systemd/system/bot-seller-bot.service

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
    systemctl daemon-reload
    systemctl enable --now bot-seller-api.service
    if [[ -n "${TELEGRAM_BOT_TOKEN:-}" ]]; then
      systemctl enable --now bot-seller-bot.service
    else
      echo "TELEGRAM_BOT_TOKEN not set. Bot service installed but not started."
      systemctl disable --now bot-seller-bot.service || true
    fi
  else
    sudo mv /tmp/bot-seller-api.service "$API_SERVICE"
    sudo mv /tmp/bot-seller-bot.service "$BOT_SERVICE"
    sudo systemctl daemon-reload
    sudo systemctl enable --now bot-seller-api.service
    if [[ -n "${TELEGRAM_BOT_TOKEN:-}" ]]; then
      sudo systemctl enable --now bot-seller-bot.service
    else
      echo "TELEGRAM_BOT_TOKEN not set. Bot service installed but not started."
      sudo systemctl disable --now bot-seller-bot.service || true
    fi
  fi
}

main() {
  install_os_packages
  write_env
  setup_python
  seed_defaults
  install_services
  echo "Install complete."
  echo "API: http://$(hostname -I | awk '{print $1}'):8000/api/health/"
  echo "If bot token was omitted, set TELEGRAM_BOT_TOKEN in $ENV_FILE then run:"
  echo "sudo systemctl restart bot-seller-bot"
}

main "$@"
