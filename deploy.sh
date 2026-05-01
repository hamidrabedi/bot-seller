#!/usr/bin/env bash
set -euo pipefail

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput || true

echo "Done. Start API: source .venv/bin/activate && python manage.py runserver 0.0.0.0:8000"
echo "Start Bot: source .venv/bin/activate && TELEGRAM_BOT_TOKEN=... python manage.py run_telegram_bot"
