# Telegram Shift Calendar Bot

A Telegram bot for tracking and managing job shifts through a visual calendar interface.

## Features

- Visual calendar with colored day buttons
- Admin and user permission system
- Natural language processing via Gemini 2.5 Flash API
- Calendar history viewing
- User management (colors, names)
- Mass changes via natural language (admin only)

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Create `.env` file and fill in your credentials:
- `BOT_TOKEN`: Get from [@BotFather](https://t.me/BotFather)
- `GEMINI_API_KEY`: Get from [Google AI Studio](https://makersuite.google.com/app/apikey)
- `ADMIN_IDS`: Comma-separated list of Telegram user IDs
- `DATABASE_URL`: (Optional) SQLite database URL (defaults to `sqlite+aiosqlite:///shiftbot.db`)
- `THINKING_BUDGET`: (Optional) Gemini thinking budget. Use `-1` for dynamic thinking, or a number (1-8192) for fixed budget (default: 2048)

3. Initialize database:
```bash
# Create database tables (will be done automatically on first run)
python -m bot.main
```

4. Run the bot:
```bash
python -m bot.main
```

## Systemd Service (Autostart)

To run the bot as a systemd service for automatic startup:

1. Install the service:
```bash
sudo ./install-service.sh
```

2. Enable autostart on boot:
```bash
sudo systemctl enable coffee-dealer-bot
```

3. Start the service:
```bash
sudo systemctl start coffee-dealer-bot
```

4. Check status:
```bash
sudo systemctl status coffee-dealer-bot
```

5. View logs:
```bash
sudo journalctl -u coffee-dealer-bot -f
```

### Service Management Commands

- `sudo systemctl start coffee-dealer-bot` - Start the bot
- `sudo systemctl stop coffee-dealer-bot` - Stop the bot
- `sudo systemctl restart coffee-dealer-bot` - Restart the bot
- `sudo systemctl enable coffee-dealer-bot` - Enable autostart on boot
- `sudo systemctl disable coffee-dealer-bot` - Disable autostart
- `sudo systemctl status coffee-dealer-bot` - Check bot status
- `sudo journalctl -u coffee-dealer-bot -f` - View bot logs (follow mode)
- `sudo journalctl -u coffee-dealer-bot -n 100` - View last 100 log lines

## Commands

### User Commands
- `/start` - Start the bot
- `/calendar` - View current month calendar
- `/history [month] [year]` - View past months

### Admin Commands
- `/allow <user_id|@username>` - Allow user to interact with bot
- `/adduser <user_id> <name> [color]` - Add new user
- `/setcolor <user_id> <color>` - Change user color
- `/setname <user_id> <name>` - Change user display name
- `/listusers` - List all users

## Usage

Users can send natural language requests to ask for shift changes. Admins will be notified and can approve/reject requests.

Admins can also use natural language to make mass changes directly.

