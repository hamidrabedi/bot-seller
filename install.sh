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

green(){ echo -e "\033[32m$1\033[0m"; }
blue(){ echo -e "\033[36m$1\033[0m"; }
red(){ echo -e "\033[31m$1\033[0m"; }

random_cred(){ "$PYTHON_BIN" - <<'PY'
import secrets,string
u='admin_'+''.join(secrets.choice(string.ascii_lowercase+string.digits) for _ in range(6))
p=''.join(secrets.choice(string.ascii_letters+string.digits+'!@#%^&*') for _ in range(16))
print(u);print(p)
PY
}

prompt_install_inputs(){
  read -rp "Domain (e.g. seller.example.com): " DOMAIN
  read -rp "Telegram bot token: " TELEGRAM_BOT_TOKEN
  export DOMAIN TELEGRAM_BOT_TOKEN
}

install_os_packages(){
  local pkgs="git curl nginx certbot python3-certbot-nginx python3 python3-venv python3-dev build-essential libjpeg-dev zlib1g-dev"
  if command -v apt-get >/dev/null 2>&1; then
    if [[ $EUID -eq 0 ]]; then apt-get update && apt-get install -y $pkgs; else sudo apt-get update && sudo apt-get install -y $pkgs; fi
  fi
}

clone_or_update(){
  if [[ ! -d "$PROJECT_DIR/.git" ]]; then mkdir -p "$(dirname "$PROJECT_DIR")"; git clone "$REPO_URL" "$PROJECT_DIR"; else git -C "$PROJECT_DIR" pull --ff-only || true; fi
}

write_env(){
  [[ -f "$ENV_FILE" ]] && return
  secret=$($PYTHON_BIN - <<'PY'
import secrets; print(secrets.token_urlsafe(50))
PY
)
  cat > "$ENV_FILE" <<ENV
DJANGO_SECRET_KEY=$secret
DEBUG=0
ALLOWED_HOSTS=${DOMAIN},www.${DOMAIN},127.0.0.1,localhost
TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
BANK_TRANSFER_TEXT_FA=شماره کارت: 0000-0000-0000-0000 | به نام: YOUR NAME
BANK_TRANSFER_TEXT_EN=Card Number: 0000-0000-0000-0000 | Holder: YOUR NAME
ENV
}

setup_python(){
  cd "$PROJECT_DIR"; $PYTHON_BIN -m venv "$VENV_DIR"; source "$VENV_DIR/bin/activate"; pip install --upgrade pip wheel; pip install -r requirements.txt
}

setup_db_and_admin(){
  cd "$PROJECT_DIR"; source "$VENV_DIR/bin/activate"; mkdir -p "$LOG_DIR" media staticfiles
  python manage.py migrate
  python manage.py collectstatic --noinput
  creds=$(random_cred); ADMIN_USER=$(echo "$creds"|sed -n '1p'); ADMIN_PASS=$(echo "$creds"|sed -n '2p')
  ADMIN_EMAIL="${ADMIN_USER}@local"
  ADMIN_USER="$ADMIN_USER" ADMIN_PASS="$ADMIN_PASS" ADMIN_EMAIL="$ADMIN_EMAIL" python manage.py shell <<'PY'
import os
from django.contrib.auth import get_user_model
from core.models import PaymentSettings,SystemConfig
U=get_user_model()
if not U.objects.filter(username=os.environ['ADMIN_USER']).exists():
    U.objects.create_superuser(os.environ['ADMIN_USER'], os.environ['ADMIN_EMAIL'], os.environ['ADMIN_PASS'])
ps,_=PaymentSettings.objects.get_or_create(title='default')
ps.is_active=True; ps.save()
sc,_=SystemConfig.objects.get_or_create(title='default')
sc.telegram_bot_token=os.getenv('TELEGRAM_BOT_TOKEN','')
sc.service_api_name='bot-seller-api'; sc.service_bot_name='bot-seller-bot'; sc.allow_admin_restart=True; sc.save()
PY
}

install_services(){
cat > /tmp/bot-seller-api.service <<UNIT
[Unit]
Description=bot-seller API
After=network.target
[Service]
Type=simple
User=${APP_USER}
WorkingDirectory=${PROJECT_DIR}
EnvironmentFile=${ENV_FILE}
ExecStart=${VENV_DIR}/bin/gunicorn config.wsgi:application --bind 127.0.0.1:8000 --workers 3 --timeout 120
Restart=always
[Install]
WantedBy=multi-user.target
UNIT
cat > /tmp/bot-seller-bot.service <<UNIT
[Unit]
Description=bot-seller Telegram bot
After=network.target
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
  systemctl daemon-reload; systemctl enable --now bot-seller-api.service bot-seller-bot.service
else
  sudo mv /tmp/bot-seller-api.service /etc/systemd/system/bot-seller-api.service
  sudo mv /tmp/bot-seller-bot.service /etc/systemd/system/bot-seller-bot.service
  sudo systemctl daemon-reload; sudo systemctl enable --now bot-seller-api.service bot-seller-bot.service
fi
}

setup_nginx_https(){
cat > /tmp/bot-seller-nginx <<NG
server {
  listen 80;
  server_name ${DOMAIN} www.${DOMAIN};
  location /static/ { alias ${PROJECT_DIR}/staticfiles/; }
  location /media/ { alias ${PROJECT_DIR}/media/; }
  location / { proxy_pass http://127.0.0.1:8000; proxy_set_header Host \$host; proxy_set_header X-Real-IP \$remote_addr; }
}
NG
if [[ $EUID -eq 0 ]]; then
  mv /tmp/bot-seller-nginx /etc/nginx/sites-available/bot-seller
  ln -sf /etc/nginx/sites-available/bot-seller /etc/nginx/sites-enabled/bot-seller
  nginx -t && systemctl reload nginx
  certbot --nginx -d "$DOMAIN" -d "www.$DOMAIN" --non-interactive --agree-tos -m "admin@$DOMAIN" --redirect || true
else
  sudo mv /tmp/bot-seller-nginx /etc/nginx/sites-available/bot-seller
  sudo ln -sf /etc/nginx/sites-available/bot-seller /etc/nginx/sites-enabled/bot-seller
  sudo nginx -t && sudo systemctl reload nginx
  sudo certbot --nginx -d "$DOMAIN" -d "www.$DOMAIN" --non-interactive --agree-tos -m "admin@$DOMAIN" --redirect || true
fi
}

install_cli_link(){
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

do_install(){ prompt_install_inputs; install_os_packages; clone_or_update; write_env; setup_python; setup_db_and_admin; install_services; setup_nginx_https; install_cli_link; green "Installed!"; blue "Admin URL: https://${DOMAIN}/admin"; blue "Admin Username: ${ADMIN_USER}"; red "Admin Password: ${ADMIN_PASS}"; }
do_update(){ clone_or_update; setup_python; setup_db_and_admin; install_services; [[ -n "${DOMAIN:-}" ]] && setup_nginx_https || true; green "Updated!"; }
do_remove(){ if [[ $EUID -eq 0 ]]; then systemctl disable --now bot-seller-api.service bot-seller-bot.service || true; rm -f /etc/systemd/system/bot-seller-api.service /etc/systemd/system/bot-seller-bot.service; systemctl daemon-reload || true; rm -f /etc/nginx/sites-enabled/bot-seller /etc/nginx/sites-available/bot-seller; systemctl reload nginx || true; rm -f "$BIN_LINK"; else sudo systemctl disable --now bot-seller-api.service bot-seller-bot.service || true; sudo rm -f /etc/systemd/system/bot-seller-api.service /etc/systemd/system/bot-seller-bot.service; sudo systemctl daemon-reload || true; sudo rm -f /etc/nginx/sites-enabled/bot-seller /etc/nginx/sites-available/bot-seller; sudo systemctl reload nginx || true; sudo rm -f "$BIN_LINK"; fi; rm -rf "$PROJECT_DIR"; green "Removed."; }

menu(){
  while true; do
    echo ""; blue "==== SELLER MANAGER ===="
    echo "1) Install"; echo "2) Update"; echo "3) Remove"; echo "4) Exit"
    read -rp "Choose: " c
    case "$c" in
      1) do_install ;;
      2) do_update ;;
      3) do_remove ;;
      4) exit 0 ;;
      *) echo "Invalid" ;;
    esac
  done
}

case "${1:-}" in
  install) do_install ;;
  update) do_update ;;
  remove) do_remove ;;
  "") menu ;;
  *) menu ;;
esac
