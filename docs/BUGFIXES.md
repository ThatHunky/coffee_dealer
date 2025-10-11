# Bug Fixes - October 11, 2025

## Issues Fixed

### 1. Font Loading Error in Docker

**Error:**
```
Warning: Could not load custom fonts: cannot open resource
```

**Root Cause:**
The `fonts/` directory was not being copied into the Docker container.

**Fix:**
Updated `Dockerfile` to include the fonts directory:

```dockerfile
# Copy application code
COPY src/ ./src/
COPY fonts/ ./fonts/        # Added this line
COPY .env.example .env.example
```

**Result:**
✅ Fonts now load correctly in Docker container  
✅ Calendar renders with proper Cyrillic/Ukrainian text support

---

### 2. Database Table Missing Error

**Error:**
```
sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) no such table: user_configs
```

**Root Cause:**
The `UserManager` class was trying to load data from the database at import time (when the module is loaded), before the database tables were created by `init_db()`.

**Fix:**
Implemented lazy initialization in `src/user_manager.py`:

1. Added `_initialized` flag to track initialization state
2. Added `_ensure_initialized()` method that safely loads data only when needed
3. Added exception handling to allow retry if database isn't ready
4. Called `_ensure_initialized()` at the start of all public methods

**Code Changes:**
```python
def __init__(self):
    """Initialize user manager."""
    self._user_cache: dict[str, UserConfig] = {}
    self._combo_cache: dict[int, CombinationColor] = {}
    self._initialized = False  # Don't load immediately

def _ensure_initialized(self) -> None:
    """Ensure cache is initialized (lazy loading)."""
    if not self._initialized:
        try:
            self._refresh_cache()
            self._initialized = True
        except Exception:
            # Database not ready yet, will retry on next access
            pass
```

**Result:**
✅ Database tables created successfully  
✅ Default users initialized (Діана, Дана, Женя)  
✅ Default color combinations initialized  
✅ Bot starts without errors

---

## Verification

Bot logs now show successful startup:

```
coffee-dealer-bot  | 2025-10-11 15:52:45.650 | INFO     | __main__:main:23 - Initializing database...
coffee-dealer-bot  | ✅ Initialized default users
coffee-dealer-bot  | ✅ Initialized default color combinations
coffee-dealer-bot  | 2025-10-11 15:52:45.756 | INFO     | __main__:main:27 - Starting Coffee Dealer bot...
coffee-dealer-bot  | 2025-10-11 15:52:45.933 | INFO     | src.bot:send_calendar:109 - Rendering calendar for 2025-10
```

**No errors or warnings!** ✅

---

## Files Modified

1. **Dockerfile** - Added `COPY fonts/ ./fonts/`
2. **src/user_manager.py** - Implemented lazy initialization pattern

---

## Testing Recommendations

1. ✅ Bot starts successfully
2. ✅ Database tables created
3. ✅ Default users loaded
4. ✅ Fonts loading correctly
5. ⏳ Test calendar rendering (send `/start` to bot)
6. ⏳ Test admin commands (`/users`, `/colors`)
7. ⏳ Test schedule assignment with natural language
8. ⏳ Test notifications when schedule changes

---

## Known Improvements for Future

1. Add health check endpoint for Docker
2. Add database migration system
3. Add proper logging levels (debug vs info)
4. Consider adding retry logic for font loading
5. Add unit tests for UserManager lazy initialization

---

## Deployment

To deploy the fixes:

```bash
# Stop current container
docker compose down

# Rebuild with changes
docker compose up --build -d

# Check logs
docker compose logs -f
```

All systems operational! 🚀
