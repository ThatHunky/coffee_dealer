# Development Guide

## Project Structure

```
coffee_dealer/
├── src/                    # Source code
│   ├── __init__.py
│   ├── config.py          # Configuration and environment variables
│   ├── models.py          # SQLModel data models (bitmask-based)
│   ├── repo.py            # Database repository layer
│   ├── image_render.py    # Pillow calendar renderer
│   ├── intents.py         # Pydantic intent models
│   ├── nlp.py             # Google Gemini NLP integration
│   ├── bot.py             # aiogram handlers and routers
│   └── main.py            # Application entry point
├── tests/                 # Test suite
│   ├── __init__.py
│   ├── test_image.py      # Renderer tests
│   └── test_nlp.py        # NLP intent parsing tests
├── .github/
│   └── workflows/
│       └── ci.yml         # GitHub Actions CI pipeline
├── .env.example           # Environment template
├── .gitignore
├── requirements.txt       # Python dependencies
├── pyproject.toml         # Tool configuration
├── Dockerfile
├── docker-compose.yml
├── setup.sh               # Setup script
├── LICENSE
├── README.md
└── QUICKSTART.md
```

## Development Setup

### Prerequisites

- Python 3.12+
- Git
- Telegram account
- Google Gemini API access

### Initial Setup

```bash
# Clone repository
git clone <repo-url>
cd coffee_dealer

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies + dev tools
pip install -r requirements.txt
pip install pytest-cov ruff mypy black

# Copy environment template
cp .env.example .env
# Edit .env with your credentials

# Initialize database
python -c "from src.repo import init_db; init_db()"

# Run tests
pytest
```

## Code Architecture

### 1. Data Layer (`models.py` + `repo.py`)

**Bitmask Design:**
```python
# Assignment model uses bitwise operations for efficiency
1 (0b001) = Diana
2 (0b010) = Dana  
4 (0b100) = Zhenya

# Combinations via OR:
Diana + Dana = 1 | 2 = 3 (0b011)
Diana + Zhenya = 1 | 4 = 5 (0b101)
```

**Adding a New Person:**
```python
# 1. Add new bitmask (next power of 2)
ALICE_MASK = 8  # 0b1000

# 2. Update Assignment.from_people()
if person_lower in ("alice", "аліса"):
    mask |= 8

# 3. Add property
@property
def alice(self) -> bool:
    return bool(self.mask & 8)

# 4. Update get_color() for new combinations
# 5. Update get_people_names()
```

### 2. NLP Layer (`nlp.py` + `intents.py`)

**Flow:**
1. User sends text → `parse_utterance()`
2. Gemini processes with JSON schema constraint
3. Response validated via Pydantic `NLCommand`
4. Dispatcher routes to handler based on `action`

**JSON Schema Enforcement:**
```python
# Gemini is forced to return valid JSON matching NLCommand schema
config = types.GenerateContentConfig(
    response_mime_type="application/json",
    response_schema=NLCommand,  # Pydantic model
    temperature=0.1,  # Deterministic
)
```

**Improving Accuracy:**
Add few-shot examples to `SYSTEM_INSTRUCTION`:
```python
SYSTEM_INSTRUCTION = """
...

Приклади розбору:
- Вхід: "покажи жовтень 2024"
  Вихід: {"action": "show_month", "month": 10, "year": 2024}
  
- Вхід: "постав Діану на 5"  
  Вихід: {"action": "assign_day", "day": 5, "people": ["diana"]}
"""
```

### 3. Rendering Layer (`image_render.py`)

**Calendar Generation:**
```python
# 1. Get assignments for month
assignments = repo.get_month(year, month)

# 2. Create assignment lookup
assignment_map = {a.day: a for a in assignments}

# 3. Generate calendar grid
cal = calendar.monthcalendar(year, month)  # Monday-first

# 4. For each day:
#    - Get assignment color via bitmask
#    - Draw cell background
#    - Add names
```

**Customizing Colors:**
```python
def get_color(self) -> str:
    if self.mask == 1:  # Diana
        return "#4A90E2"  # Blue
    elif self.mask == 2:  # Dana
        return "#9B59B6"  # Purple
    # ... add your colors
```

### 4. Bot Layer (`bot.py`)

**Message Flow:**
```
User Message
    ↓
nlp_entry() handler (F.text filter)
    ↓
parse_utterance() → NLCommand
    ↓
Dispatcher based on action:
    ├── show_month → handle_show_month()
    ├── assign_day → handle_assign_day() [admin check]
    ├── who_works → handle_who_works()
    └── help → cmd_help()
```

**Admin Guard Pattern:**
```python
if cmd.action == "assign_day":
    if not is_admin(message.from_user.id):
        await message.answer("Лише для адміністратора")
        return
    # ... proceed with assignment
```

## Testing

### Running Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=src --cov-report=html

# Specific test file
pytest tests/test_nlp.py -v

# Specific test
pytest tests/test_image.py::test_bitmask_mapping -v
```

### Writing Tests

**Image Tests:**
```python
def test_new_feature():
    assignment = Assignment.from_people(date(2024, 10, 1), ["diana"])
    assert assignment.mask == 1
    assert assignment.get_color() == "#4A90E2"
```

**NLP Tests:**
```python
@pytest.mark.asyncio
async def test_new_command():
    cmd = await parse_utterance("your text", date.today())
    assert cmd.action == "expected_action"
```

**Note:** NLP tests may be non-deterministic. Use assertions like:
```python
assert cmd.action in ("show_month", "help")  # Accept multiple valid outcomes
```

## Code Quality

### Linting

```bash
# Check code style
ruff check src/ tests/

# Auto-fix issues
ruff check src/ tests/ --fix

# Format code
black src/ tests/
```

### Type Checking

```bash
mypy src/ --ignore-missing-imports
```

### Pre-commit Checks

Create `.git/hooks/pre-commit`:
```bash
#!/bin/bash
ruff check src/ tests/ || exit 1
pytest tests/ || exit 1
```

## Adding New Features

### Example: Add "Delete Assignment" Command

**1. Update Intent Model (`intents.py`):**
```python
action: Literal["show_month", "assign_day", "who_works", "delete_day", "help"]
```

**2. Update Gemini System Instruction (`nlp.py`):**
```python
SYSTEM_INSTRUCTION = """
...
- "delete_day" — видалити призначення на день
...
"""
```

**3. Add Handler (`bot.py`):**
```python
async def handle_delete_day(message: Message, cmd: NLCommand):
    if not is_admin(message.from_user.id):
        await message.answer("Лише для адміністратора")
        return
    
    # ... get date from cmd
    repo.delete(target_date)
    await message.answer(f"✅ Видалено призначення на {target_date}")
```

**4. Update Dispatcher (`bot.py`):**
```python
elif cmd.action == "delete_day":
    await handle_delete_day(message, cmd)
```

**5. Add Tests (`tests/test_nlp.py`):**
```python
@pytest.mark.asyncio
async def test_delete_command():
    cmd = await parse_utterance("видали призначення на 5", date.today())
    assert cmd.action in ("delete_day", "help")
```

## Debugging

### Enable Debug Logging

```python
# In src/main.py or src/config.py
from loguru import logger
logger.add("debug.log", level="DEBUG", rotation="10 MB")
```

### Common Issues

**"Import google.genai not found"**
```bash
pip install --upgrade google-genai
```

**"SQLModel table not created"**
```python
# Run in Python shell:
from src.repo import init_db
init_db()
```

**"Gemini timeout/rate limit"**
- Check API quota: https://aistudio.google.com/app/apikey
- Increase timeout in `nlp.py`: `timeout=5.0`

## Performance Optimization

### Database Indexing

Already indexed on `day` column:
```python
day: date = Field(index=True, unique=True)
```

### Caching Calendar Images

Add in-memory cache:
```python
from functools import lru_cache

@lru_cache(maxsize=12)  # Cache 12 months
def render(year: int, month: int):
    # ... rendering logic
```

### Gemini Rate Limiting

Add rate limiter:
```python
import asyncio
from collections import deque

class RateLimiter:
    def __init__(self, max_calls=10, period=60):
        self.calls = deque()
        self.max_calls = max_calls
        self.period = period
    
    async def acquire(self):
        now = time.time()
        # Remove old calls
        while self.calls and self.calls[0] < now - self.period:
            self.calls.popleft()
        
        if len(self.calls) >= self.max_calls:
            sleep_time = self.period - (now - self.calls[0])
            await asyncio.sleep(sleep_time)
        
        self.calls.append(time.time())
```

## Deployment

See README.md for:
- systemd service configuration
- Docker deployment
- Environment variable best practices

## Contributing

1. Fork repository
2. Create feature branch: `git checkout -b feature/amazing-feature`
3. Make changes
4. Run tests: `pytest`
5. Commit: `git commit -m 'Add amazing feature'`
6. Push: `git push origin feature/amazing-feature`
7. Create Pull Request

## Resources

- [aiogram Documentation](https://docs.aiogram.dev/)
- [Google Gen AI SDK](https://googleapis.github.io/python-genai/)
- [SQLModel Documentation](https://sqlmodel.tiangolo.com/)
- [Pillow Documentation](https://pillow.readthedocs.io/)
- [Pydantic Documentation](https://docs.pydantic.dev/)

Happy coding! ☕
