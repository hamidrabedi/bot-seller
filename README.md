# bot-seller

## One command install
```bash
curl -fsSL https://raw.githubusercontent.com/hamidrabedi/bot-seller/main/install.sh | sudo bash
```

Running `seller` (or `install.sh` with no args) opens interactive menu:
- Install
- Update
- Remove
- Exit

## Install flow now includes
- Prompt for **domain** and **telegram bot token**
- Automatic Nginx config
- Automatic HTTPS certificate with Certbot
- Gunicorn + Telegram bot systemd services
- Static/media serving via Nginx + WhiteNoise support in Django
- Auto create Django superuser with random username/password and print at end

## Seller CLI
```bash
seller install
seller update
seller remove
```
