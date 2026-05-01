# Project plan (production-ready target, minimal services)

## Fixed constraints
- Database: SQLite (as requested)
- Panels: 3x-ui only (no marzban/other panels)
- Interfaces: Django admin + REST API + Telegram bot
- Keep service count low: single Django service process for MVP

## Done
- Django project + admin + SQLite
- Telegram bot commands and inline purchase flow
- 3x-ui adapter and provisioning service
- APIs for plans/create-service/my-services
- One-script deploy

## Remaining tasks to reach production-ready

### 1) Security hardening
- Move all secrets to environment variables
- Enforce strong `DJANGO_SECRET_KEY`
- Restrict `ALLOWED_HOSTS`
- Add admin rate-limit / IP restrictions at reverse proxy

### 2) Reliability
- Add request timeouts/retries for 3x-ui calls
- Add structured logging around provisioning attempts
- Add idempotency key for create-service to avoid duplicate buys

### 3) Product completeness
- Add payment callback endpoint
- Add usage sync endpoint/cron command for 3x-ui usage data
- Add renewal endpoint and Telegram button

### 4) Deployment
- Add systemd service templates for API and bot
- Put Nginx in front of Django
- Enable HTTPS (Let's Encrypt)
- Run DB backups for SQLite file

## Execution order (clean and practical)
1. security envs
2. payment + renewal
3. usage sync
4. deployment hardening
5. monitoring/alerts
