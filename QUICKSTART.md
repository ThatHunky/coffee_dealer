# Quick Start Guide

## 🚀 Get Started in 5 Minutes

### Step 1: Get Your Credentials

#### Telegram Bot Token
1. Open Telegram and search for **@BotFather**
2. Send `/newbot` command
3. Follow the prompts to create your bot
4. Copy the token (looks like `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

#### Google Gemini API Key
1. Go to [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Click "Create API Key"
3. Copy the key (starts with `AIza...`)

#### Your Telegram User ID
1. Open Telegram and search for **@userinfobot**
2. Send `/start`
3. Copy your user ID (a number like `123456789`)

### Step 2: Clone and Setup

```bash
# Clone the repository
git clone <your-repo-url>
cd coffee_dealer

# Run setup script (Linux/Mac)
chmod +x setup.sh
./setup.sh

# OR manually:
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Step 3: Configure

Create `.env` file (or copy from `.env.example`):

```env
BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
ADMIN_IDS=123456789
GOOGLE_API_KEY=AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
GEMINI_MODEL=gemini-2.0-flash-exp
TZ=Europe/Kyiv
DATABASE_URL=sqlite:///./schedule.db
```

### Step 4: Run!

```bash
python -m src.main
```

You should see:
```
2025-10-11 12:00:00 | INFO | Initializing database...
2025-10-11 12:00:00 | INFO | Starting Coffee Dealer bot...
```

### Step 5: Test Your Bot

1. Open Telegram and find your bot
2. Send `/start`
3. You should get a welcome message with keyboard buttons
4. Try: "покажи жовтень" (show October)
5. The bot should respond with a calendar image!

## 🐳 Docker Quick Start

If you prefer Docker:

```bash
# Create .env file first (see Step 3)
cp .env.example .env
# Edit .env with your credentials

# Run with Docker Compose
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

## 📝 First Commands to Try

Once your bot is running, try these commands:

### Basic Navigation
```
/start
/help
📅 Показати місяць
```

### Natural Language (Anyone)
```
покажи жовтень
розклад на листопад 2024
хто працює 15 числа?
хто на 10 жовтня?
```

### Admin Commands (You must be in ADMIN_IDS)
```
постав Діану на 5 жовтня
Діана і Женя на 15
Дана на 20 листопада
```

## 🔧 Troubleshooting

### "Configuration error: BOT_TOKEN is not set"
- Make sure you created `.env` file
- Check that `.env` is in the project root directory
- Verify BOT_TOKEN is correctly copied (no extra spaces)

### "Configuration error: GOOGLE_API_KEY is not set"
- Get your API key from [Google AI Studio](https://aistudio.google.com/app/apikey)
- Make sure it's in `.env` file

### Bot doesn't respond to commands
- Check that bot is running (look for "Starting Coffee Dealer bot..." in logs)
- Make sure you're messaging the correct bot
- Try `/start` first

### "Лише адміністратори можуть змінювати розклад"
- Add your Telegram user ID to `ADMIN_IDS` in `.env`
- Get your ID from @userinfobot
- Restart the bot after changing `.env`

### Calendar shows wrong month names
- This might happen if Babel locale data is missing
- Try: `pip install --upgrade Babel`

### Import errors (sqlmodel, aiogram, etc.)
- Make sure virtual environment is activated
- Run: `pip install -r requirements.txt`

## 📚 Next Steps

- **Customize**: Edit staff names and colors in `src/models.py`
- **Test**: Run `pytest` to verify everything works
- **Deploy**: Use systemd service or Docker for production
- **Monitor**: Check logs for any issues

## 🆘 Still Having Issues?

1. Check the full README.md for detailed documentation
2. Look at existing GitHub issues
3. Create a new issue with:
   - Your error message
   - Python version (`python --version`)
   - OS (Windows/Mac/Linux)
   - Steps you followed

Happy scheduling! ☕
