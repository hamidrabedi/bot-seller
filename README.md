# bot-seller

## One command install
```bash
curl -fsSL https://raw.githubusercontent.com/your-org/bot-seller/main/install.sh | sudo bash
```

## Installed CLI command
Installer registers a global command: `seller`

Usage:
```bash
seller install
seller update
seller remove
```

## Notes
- `seller install`: install all dependencies, configure, migrate, and run in background.
- `seller update`: pull latest code and restart services.
- `seller remove`: stop services and remove project files.
