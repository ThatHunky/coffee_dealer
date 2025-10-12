# File-Based Logging Implementation

## 📝 Overview

Implemented comprehensive file-based logging with automatic rotation and 7-day retention for the Coffee Dealer bot. All logs are now saved to files with proper formatting, timestamps, and automatic cleanup.

## ✨ Features

### Log Files
- **Location**: `logs/` directory at project root
- **Format**: `coffee_dealer_YYYY-MM-DD.log`
- **Encoding**: UTF-8
- **Compression**: Old logs automatically compressed to `.zip`

### Rotation & Retention
- **Rotation**: Daily at midnight (configurable)
- **Retention**: 7 days (configurable)
- **Automatic Cleanup**: Logs older than 7 days are automatically deleted

### Log Outputs
1. **Console (stderr)**: Colorized, minimal format for development
2. **File**: Detailed format with full context for debugging

## 🔧 Configuration

New environment variables in `.env`:

```bash
# Logging Configuration (all optional)
LOG_LEVEL=INFO                    # Log level: DEBUG, INFO, WARNING, ERROR
LOG_DIR=logs                      # Directory for log files
LOG_RETENTION=7 days              # How long to keep logs
LOG_ROTATION=00:00                # When to rotate logs (HH:MM)
```

### Default Values
- `LOG_LEVEL`: `INFO`
- `LOG_DIR`: `logs`
- `LOG_RETENTION`: `7 days`
- `LOG_ROTATION`: `00:00` (midnight)

## 📁 Files Modified

### `src/main.py`
- Added `setup_logging()` function
- Configures dual logging (console + file)
- Creates logs directory if missing
- Sets up rotation and retention policies
- Called at bot startup

### `src/config.py`
- Added logging configuration parameters
- `LOG_LEVEL`, `LOG_DIR`, `LOG_RETENTION`, `LOG_ROTATION`

### `.gitignore`
- Added `logs/` directory (with `.gitkeep` exception)
- Ensures log files aren't committed to git

### New Files
- `logs/.gitkeep`: Ensures logs directory is tracked

## 📊 Log Format

### Console Format
```
2025-01-15 14:30:45 | INFO     | bot:handle_start - User started bot
```

### File Format
```
2025-01-15 14:30:45 | INFO     | src.bot:handle_start:123 - User started bot
```

File logs include:
- Full timestamp
- Log level (padded to 8 chars)
- Module name
- Function name
- Line number
- Message
- Exception traceback (if applicable)

## 🚀 Usage

### Starting the Bot
```bash
python -m src.main
```

Logs will automatically:
1. Print to console (colorized)
2. Save to `logs/coffee_dealer_2025-01-15.log`
3. Rotate at midnight
4. Delete logs older than 7 days
5. Compress old logs to `.zip`

### Viewing Logs
```bash
# View today's log
tail -f logs/coffee_dealer_$(date +%Y-%m-%d).log

# View all logs
ls -lh logs/

# Search for errors
grep ERROR logs/*.log
```

## 🔍 Log Rotation Example

```
logs/
├── .gitkeep
├── coffee_dealer_2025-01-15.log      # Today
├── coffee_dealer_2025-01-14.log      # Yesterday
├── coffee_dealer_2025-01-13.log.zip  # Compressed
├── coffee_dealer_2025-01-12.log.zip  # Compressed
└── coffee_dealer_2025-01-11.log.zip  # Compressed
# Files older than 7 days are automatically deleted
```

## 🛠️ Customization

### Change Log Level
```bash
# In .env
LOG_LEVEL=DEBUG  # More verbose
LOG_LEVEL=ERROR  # Only errors
```

### Change Retention Period
```bash
# In .env
LOG_RETENTION=14 days  # Keep for 2 weeks
LOG_RETENTION=1 month  # Keep for 1 month
```

### Change Rotation Time
```bash
# In .env
LOG_ROTATION=06:00     # Rotate at 6 AM
LOG_ROTATION=500 MB    # Rotate when file reaches 500 MB
```

### Custom Log Directory
```bash
# In .env
LOG_DIR=/var/log/coffee_dealer  # Custom path
```

## 📝 Logging Best Practices

### In Code
```python
from loguru import logger

# ✅ GOOD: Structured logging with context
logger.info("User approved", user_id=user.id, username=user.username)

# ✅ GOOD: Error logging with exception info
try:
    await dangerous_operation()
except Exception as e:
    logger.error("Operation failed", user_id=user.id, exc_info=True)

# ❌ BAD: Unstructured logging
logger.info(f"User {user.id} approved")

# ❌ BAD: Missing context
logger.error("Error occurred")
```

### Log Levels
- **DEBUG**: Detailed debugging information
- **INFO**: General informational messages (user actions, state changes)
- **WARNING**: Warning messages (recoverable issues)
- **ERROR**: Error messages (with exc_info=True for exceptions)

## 🔐 Security Notes

- Log files contain sensitive data (user IDs, actions)
- Logs directory is git-ignored to prevent committing sensitive data
- Use `LOG_LEVEL=INFO` in production to avoid logging too much detail
- Review logs before sharing for debugging

## 🎯 Benefits

1. **Debugging**: Full history of bot operations
2. **Monitoring**: Track user activity and errors
3. **Auditing**: Complete audit trail with timestamps
4. **Troubleshooting**: Detailed error traces with line numbers
5. **Performance**: Automatic cleanup prevents disk space issues
6. **Compliance**: 7-day retention for issue investigation

## 📚 References

- [Loguru Documentation](https://loguru.readthedocs.io/)
- [LOGGING_GUIDE.md](./LOGGING_GUIDE.md) - General logging practices

---

**Implementation Date**: January 2025  
**Python Version**: 3.11+  
**Loguru Version**: 0.7.0+
