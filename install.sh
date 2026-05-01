#!/usr/bin/env bash
set -euo pipefail

if [[ -f .env ]]; then
  echo ".env already exists. Keeping existing values."
else
  echo "=== bot-seller installer ==="
  read -rp "Django secret key (leave empty to auto-generate): " SECRET
  if [[ -z "${SECRET}" ]]; then
    SECRET=$(python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(50))
PY
)
  fi
  read -rp "Allowed hosts (comma separated, default: 127.0.0.1,localhost): " HOSTS
  HOSTS=${HOSTS:-127.0.0.1,localhost}
  read -rp "Telegram bot token: " TG_TOKEN
  read -rp "Default 3x-ui base URL (optional now): " XUI_URL
  read -rp "Default 3x-ui username (optional now): " XUI_USER
  read -rsp "Default 3x-ui password (optional now): " XUI_PASS; echo

  cat > .env <<ENV
DJANGO_SECRET_KEY=${SECRET}
DEBUG=0
ALLOWED_HOSTS=${HOSTS}
TELEGRAM_BOT_TOKEN=${TG_TOKEN}
DEFAULT_3XUI_URL=${XUI_URL}
DEFAULT_3XUI_USERNAME=${XUI_USER}
DEFAULT_3XUI_PASSWORD=${XUI_PASS}
ENV
  echo "Created .env"
fi

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate

echo "\nInstall complete."
echo "1) Create admin: source .venv/bin/activate && python manage.py createsuperuser"
echo "2) Run API: source .venv/bin/activate && python manage.py runserver 0.0.0.0:8000"
echo "3) Run bot: source .venv/bin/activate && python manage.py run_telegram_bot"
