# bot-seller (One-command production install)

## Install with ONE command
```bash
curl -fsSL https://raw.githubusercontent.com/your-org/bot-seller/main/install.sh | sudo bash
```

Optional (recommended) with Telegram token inline:
```bash
curl -fsSL https://raw.githubusercontent.com/your-org/bot-seller/main/install.sh | sudo TELEGRAM_BOT_TOKEN="123:ABC" bash
```

That command automatically does everything:
- install OS dependencies
- clone/update project
- create `.env`
- install Python dependencies
- run migrations and collectstatic
- seed bank transfer text settings
- create and start background services with systemd

## Service names
- `bot-seller-api`
- `bot-seller-bot`

## Verify
```bash
curl http://127.0.0.1:8000/api/health/
systemctl status bot-seller-api
systemctl status bot-seller-bot
```

## Notes
- If no `TELEGRAM_BOT_TOKEN` is provided, API starts but bot service is installed and left stopped.
- Set token in `/opt/bot-seller/.env` then run:
```bash
sudo systemctl restart bot-seller-bot
```
