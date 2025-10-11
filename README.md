# ☕ Coffee Dealer Schedule Bot

Ukrainian Telegram bot for managing Coffee Dealer's work schedule with AI-powered natural language commands.

## Features

✨ **Natural Language Processing** - Powered by Google Gemini 2.0 Flash
- "покажи жовтень" → Display October calendar
- "постав Діану на 5 жовтня" → Assign Diana to October 5th
- "хто працює 15 числа?" → Who works on the 15th?

� **AI Image Recognition** - Extract schedules from calendar photos
- Upload calendar image → Automatic schedule extraction
- Color recognition for staff assignments
- Bulk import with confirmation (Admin only)

�📅 **Visual Calendar** - PNG calendar with color-coded assignments
- Monday-first week layout
- Ukrainian month names (Babel)
- Color legend for staff assignments

👥 **Staff Management**
- Diana (Blue) 🔵
- Dana (Purple) 🟣
- Zhenya (Green) 🟢
- Combinations: Pink (Diana+Zhenya), Yellow (Dana+Zhenya), Red (Dana+Diana)

🔒 **Admin Controls** - Secure role-based access for schedule modifications

## Tech Stack

- **Python 3.12+**
- **aiogram 3** - Modern async Telegram bot framework
- **Google Gen AI SDK** (`google-genai`) - Gemini 2.0 Flash for NLP
- **Pillow** - Calendar image rendering
- **SQLModel + SQLite** - Database with type safety
- **Pydantic** - JSON schema validation
- **Babel** - Ukrainian locale support

## Setup

### 1. Clone and Install

```bash
# Clone repository
git clone <your-repo-url>
cd coffee_dealer

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

Copy `.env.example` to `.env` and fill in your credentials:

```env
# Telegram Bot Configuration
BOT_TOKEN=your-telegram-bot-token-here
ADMIN_IDS=123456789,987654321

# Google Gemini Configuration
GOOGLE_API_KEY=your-gemini-api-key-here
GEMINI_MODEL=gemini-2.0-flash-exp

# Application Settings
TZ=Europe/Kyiv
DATABASE_URL=sqlite:///./schedule.db
```

**How to get credentials:**
- **Telegram Bot Token**: Talk to [@BotFather](https://t.me/botfather)
- **Gemini API Key**: Get from [Google AI Studio](https://aistudio.google.com/app/apikey)
- **Admin IDs**: Get your Telegram user ID from [@userinfobot](https://t.me/userinfobot)

### 3. Run the Bot

```bash
python -m src.main
```

## Usage

### Basic Commands

- `/start` - Welcome message and keyboard
- `/help` - Show available commands
- `📅 Показати місяць` - Display current month calendar

### Natural Language Examples

**Show Calendar:**
```
покажи жовтень
розклад на листопад
```

**Query Schedule:**
```
хто працює 15 числа?
хто на 10 жовтня?
```

**Assign Staff (Admin Only):**
```
постав Діану на 5 жовтня
Діана і Женя на 15
Дана на 20 листопада
```

## Architecture

```
src/
├── config.py          # Environment configuration
├── models.py          # SQLModel data models (bitmask-based)
├── repo.py            # Database repository
├── image_render.py    # Pillow calendar renderer
├── intents.py         # Pydantic intent models
├── nlp.py             # Gemini NLP integration
├── bot.py             # aiogram handlers and routers
└── main.py            # Entry point

tests/
├── test_image.py      # Renderer tests
└── test_nlp.py        # NLP intent tests
```

### Key Design Decisions

**Bitmask Assignments** - Efficient storage using bitwise operations:
- 1 (0b001) = Diana
- 2 (0b010) = Dana  
- 4 (0b100) = Zhenya
- 3 (0b011) = Diana + Dana
- etc.

**JSON Response Schema** - Gemini enforces strict JSON output via `response_schema=NLCommand`:
```python
class NLCommand(BaseModel):
    action: Literal["show_month", "assign_day", "who_works", "help"]
    year: Optional[int] = None
    month: Optional[int] = None
    day: Optional[int] = None
    people: list[Person] = []
    note: str = ""
```

**Admin Guards** - Server-side permission checks for mutations:
```python
if cmd.action == "assign_day" and not is_admin(user_id):
    return "Лише для адміністратора"
```

## Documentation

📚 **Complete documentation is available in the [`docs/`](docs/) directory:**

- **[Quick Start Guide](docs/QUICKSTART.md)** - For end users
- **[Admin Quick Start](docs/ADMIN_QUICKSTART.md)** - For administrators
- **[Admin Guide](docs/ADMIN_GUIDE.md)** - Complete admin reference
- **[Image Import Feature](docs/IMAGE_IMPORT_FEATURE.md)** - AI-powered schedule extraction from photos
- **[Development Guide](docs/DEVELOPMENT.md)** - For contributors
- **[Logging Guide](docs/LOGGING_GUIDE.md)** - Debugging and monitoring
- **[Project Summary](docs/PROJECT_SUMMARY.md)** - Architecture overview
- **[Feature Updates](docs/)** - All feature documentation

See [docs/README.md](docs/README.md) for the complete documentation index.

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src

# Run specific test file
pytest tests/test_nlp.py
```

**Test Coverage:**
- ✅ Image renderer creates valid PNG
- ✅ Bitmask mapping correctness
- ✅ Color assignments
- ✅ NLP intent parsing (with fallback tolerance)
- ✅ Pydantic validation

## Development

### Adding New Staff Members

1. Update bitmask in `models.py` (next power of 2: 8, 16, etc.)
2. Add color mapping in `Assignment.get_color()`
3. Update `Assignment.from_people()` name matching
4. Add to legend in `image_render.py`
5. Update Gemini system instruction in `nlp.py`

### Improving NLP Accuracy

Add few-shot examples to `SYSTEM_INSTRUCTION` in `nlp.py`:

```python
SYSTEM_INSTRUCTION = """
...existing instructions...

Приклади:
- "покажи жовтень 2024" → {"action": "show_month", "month": 10, "year": 2024}
- "постав Діану на 5" → {"action": "assign_day", "day": 5, "people": ["diana"]}
...
"""
```

## Deployment

### Using systemd (Linux)

Create `/etc/systemd/system/coffee-dealer-bot.service`:

```ini
[Unit]
Description=Coffee Dealer Telegram Bot
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/coffee_dealer
Environment="PATH=/path/to/coffee_dealer/.venv/bin"
ExecStart=/path/to/coffee_dealer/.venv/bin/python -m src.main
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl daemon-reload
sudo systemctl enable coffee-dealer-bot
sudo systemctl start coffee-dealer-bot
sudo systemctl status coffee-dealer-bot
```

### Docker (Optional)

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "-m", "src.main"]
```

```bash
docker build -t coffee-dealer-bot .
docker run -d --env-file .env --name coffee-bot coffee-dealer-bot
```

## Roadmap

- [ ] CSV/PDF export
- [ ] Multi-language support (English)
- [ ] User preference storage (last viewed month)
- [ ] Statistics dashboard
- [ ] GitHub Actions CI/CD
- [ ] Webhook mode for production

## Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## License

MIT License - See LICENSE file for details

## Acknowledgments

- [Google Gemini API](https://ai.google.dev/) - Powerful NLP capabilities
- [aiogram](https://docs.aiogram.dev/) - Modern Telegram bot framework
- [Pillow](https://pillow.readthedocs.io/) - Image processing
- [Babel](https://babel.pocoo.org/) - Internationalization

## Support

For issues and questions:
- Open an issue on GitHub
- Contact: [Your Contact Info]

---

Made with ☕ for Coffee Dealer
