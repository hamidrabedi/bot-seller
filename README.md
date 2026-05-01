# bot-seller (Django + Telegram + 3x-ui)

This project is focused on:
- 3x-ui only (no other panel integrations)
- Telegram bot sales flow
- Manual bank-transfer receipts (temporary)
- Django admin operations

## Production install (single script)
```bash
chmod +x install.sh
./install.sh
```

### What the script does
1. Installs required OS packages (on Debian/Ubuntu when possible).
2. Creates `.env` interactively (secret key, hosts, telegram token, bank-transfer text).
3. Creates virtualenv and installs all Python requirements.
4. Runs migrations and collectstatic.
5. Seeds/updates default `PaymentSettings` from `.env`.
6. Runs app + bot in background:
   - Preferred: systemd services (`bot-seller-api`, `bot-seller-bot`)
   - Fallback: `nohup` processes if systemd permissions are unavailable.

## After install
- Health check:
```bash
curl http://127.0.0.1:8000/api/health/
```
- Logs:
```bash
tail -f logs/api.log
tail -f logs/bot.log
```

## First admin user
```bash
source .venv/bin/activate
python manage.py createsuperuser
```

## Payment flow (temporary)
1. User asks for bank transfer info in bot.
2. User transfers manually.
3. User sends receipt image with caption `receipt:PLAN_ID`.
4. Admin approves receipt in Django admin.
5. User service is issued after approved receipt.

## Important
- For public deployment, put Nginx in front of port `8000` and enable HTTPS.
- Keep `DEBUG=0` in production.
