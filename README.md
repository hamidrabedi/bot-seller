# bot-seller (One-command production install)

## Install with ONE command
```bash
curl -fsSL https://raw.githubusercontent.com/your-org/bot-seller/main/install.sh | sudo bash
```

Optional (recommended) with Telegram token inline:
```bash
curl -fsSL https://raw.githubusercontent.com/your-org/bot-seller/main/install.sh | sudo TELEGRAM_BOT_TOKEN="123:ABC" bash
```

## What gets configured in DB (not env)
After install, defaults are seeded in database:
- `PaymentSettings` (bank transfer text)
- `SystemConfig` (telegram token fallback, service names, restart toggle)

You can change these in Django admin without redeploy.

## Admin restart button
In Django admin -> `SystemConfig` changelist, there is a **Restart API + BOT** button.
- It calls systemctl restart for service names stored in `SystemConfig`.
- For safety it only works when `allow_admin_restart=True`.

## Verify
```bash
curl http://127.0.0.1:8000/api/health/
systemctl status bot-seller-api
systemctl status bot-seller-bot
```

## .env sample
Use `.env.sample` as reference.
