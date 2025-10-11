# Logging Quick Reference Guide

## Log Levels and When to Check Them

### 🐛 DEBUG
**When to check:** Development and detailed troubleshooting
**What you'll find:**
- Calendar successfully sent/edited
- Parsed NLP commands
- Number of users sent to admin
- Operation completion confirmations

### ℹ️ INFO
**When to check:** Normal operation monitoring
**What you'll find:**
- User message inputs: `User 123456: покажи жовтень`
- Calendar rendering starts: `Rendering calendar for 2025-10`
- Admin actions: `Admin 123456 listing users`
- User approval/denial actions
- Bot startup: `Starting Coffee Dealer bot...`
- Database initialization
- Command configuration success

### ⚠️ WARNING
**When to check:** Potential issues that didn't break functionality
**What you'll find:**
- Message received without user or text
- User tried to navigate beyond 12 months
- User not found for approval
- Failed to set commands for specific admin
- NLP timeout warnings
- JSON decode issues

### ❌ ERROR
**When to check:** When something broke
**What you'll find:**
- Failed to parse callback data
- Failed to render calendar image
- Failed to notify user
- Unhandled exceptions in callbacks
- Database connection issues
- Failed to set bot commands

## Common Error Patterns

### Calendar Rendering Errors
```
ERROR | bot:send_calendar - Failed to render calendar image: [error]
```
**Possible causes:**
- Missing fonts
- PIL/Pillow issues
- Database connection lost
- Invalid date parameters

**How to debug:**
- Check if fonts exist in `fonts/` directory
- Verify PIL is installed correctly
- Check database connectivity
- Review date parameters in log

### NLP Parsing Errors
```
ERROR | bot:nlp_entry - Failed to parse utterance: [error]
```
**Possible causes:**
- Gemini API timeout
- Invalid API key
- Network issues
- Malformed response from Gemini

**How to debug:**
- Check GOOGLE_API_KEY in .env
- Verify network connectivity
- Review the utterance text in logs
- Check Gemini API status

### Callback Errors
```
ERROR | bot:callback_month_navigation - Unhandled error in month navigation callback: [error]
```
**Possible causes:**
- Invalid callback data format
- Database issues
- Image rendering failure
- Network timeout

**How to debug:**
- Check callback data in DEBUG logs
- Verify database is accessible
- Review image rendering logs
- Check for timeout errors

### User Notification Errors
```
ERROR | bot:callback_approve_user - Failed to notify user 123456: [error]
```
**Possible causes:**
- User blocked the bot
- Invalid user ID
- Network issues
- Bot token issues

**How to debug:**
- Verify user hasn't blocked bot
- Check user ID is correct
- Test bot token validity
- Check network connectivity

## Monitoring Best Practices

### Daily Checks
1. **Count ERROR logs:** Should be near zero
2. **Check WARNING logs:** Investigate patterns
3. **Monitor INFO logs:** Verify normal operation

### Commands to Monitor Logs

**Show all errors today:**
```bash
grep "ERROR" bot.log | grep "$(date +%Y-%m-%d)"
```

**Show warnings:**
```bash
grep "WARNING" bot.log | tail -50
```

**Monitor live logs:**
```bash
tail -f bot.log
```

**Count errors by type:**
```bash
grep "ERROR" bot.log | cut -d'|' -f3 | sort | uniq -c | sort -rn
```

### What to Look For

**Good signs:**
- Steady stream of INFO logs
- Few or no ERROR logs
- Occasional WARNING logs (expected)
- DEBUG logs show successful operations

**Warning signs:**
- Repeated ERROR logs
- Same WARNING appearing frequently
- No INFO logs (bot not running)
- Stack traces in logs

## Error Resolution

### Common Fixes

**1. "Failed to render calendar"**
```bash
# Check fonts exist
ls fonts/
# Reinstall PIL if needed
pip install --upgrade Pillow
```

**2. "Failed to parse utterance"**
```bash
# Check API key
grep GOOGLE_API_KEY .env
# Test API connectivity
curl https://generativelanguage.googleapis.com/v1/models
```

**3. "Failed to notify user"**
- User has blocked bot (not fixable)
- Or check bot token is valid

**4. "Database connection"**
```bash
# Check database file exists
ls *.db
# Check permissions
ls -la *.db
```

## Log File Management

### Loguru Configuration
Add to `main.py` or config:
```python
from loguru import logger

# Rotate logs daily, keep 7 days
logger.add(
    "logs/bot_{time:YYYY-MM-DD}.log",
    rotation="1 day",
    retention="7 days",
    level="DEBUG"
)

# Separate error log
logger.add(
    "logs/errors_{time:YYYY-MM-DD}.log",
    rotation="1 day",
    retention="30 days",
    level="ERROR"
)
```

### Storage Recommendations
- **DEBUG logs:** 1-3 days retention
- **INFO logs:** 7 days retention
- **ERROR logs:** 30 days retention
- Rotate daily to prevent huge files

## Debugging Workflows

### Workflow 1: User Reports Error
1. Get user ID and timestamp
2. `grep "User {ID}" bot.log | grep "{timestamp}"`
3. Look for ERROR or WARNING near that time
4. Review full stack trace
5. Check previous successful operations

### Workflow 2: Bot Not Responding
1. Check if bot is running: `ps aux | grep python`
2. Check latest logs: `tail -100 bot.log`
3. Look for startup ERROR logs
4. Verify configuration: `python -m src.main` (test run)

### Workflow 3: Calendar Issues
1. `grep "Rendering calendar" bot.log | tail -20`
2. Check for errors after render attempts
3. Verify image files can be created: `python -c "from PIL import Image; Image.new('RGB', (100,100)).save('test.png')"`
4. Check font availability

### Workflow 4: Admin Command Failed
1. `grep "Admin {ID}" bot.log`
2. Check what command was executed
3. Look for parsing errors
4. Verify permissions in code

## Log Format

Standard log line format:
```
YYYY-MM-DD HH:MM:SS.mmm | LEVEL | module:function:line - Message
```

Example:
```
2025-10-11 14:32:15.123 | INFO | bot:nlp_entry:1139 - User 123456: покажи жовтень
```

**Components:**
- **Timestamp:** When it happened
- **Level:** Severity (DEBUG/INFO/WARNING/ERROR)
- **Location:** `module:function:line` for quick code lookup
- **Message:** What happened

## Quick Diagnostics

**Is bot healthy?**
```bash
# Should see recent INFO logs
tail -20 bot.log | grep INFO
```

**Any errors in last hour?**
```bash
grep "ERROR" bot.log | tail -50
```

**What are users doing?**
```bash
grep "User" bot.log | tail -20
```

**Admin activity?**
```bash
grep "Admin" bot.log | tail -20
```

## Alert Triggers (Recommended)

Set up alerts for:
1. **More than 10 ERRORs in 10 minutes** - Major issue
2. **Same ERROR 5+ times** - Recurring problem
3. **No INFO logs for 10+ minutes** - Bot might be down
4. **"Failed to notify" repeated** - Bot token issues
5. **"Database" + "ERROR"** - Data persistence issues

## Summary

✅ **Check logs regularly** - Don't wait for issues
✅ **Use appropriate log levels** - DEBUG for dev, INFO for production monitoring
✅ **Set up log rotation** - Prevent disk space issues
✅ **Monitor ERROR patterns** - Fix recurring issues
✅ **Keep ERROR logs longer** - Useful for troubleshooting
