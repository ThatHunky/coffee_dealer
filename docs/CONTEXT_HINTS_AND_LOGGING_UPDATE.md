# Context Hints and Error Logging Update

## Summary
Added comprehensive context hints for all bot commands and enhanced error logging throughout the application for better debugging and user experience.

## Changes Made

### 1. Bot Command Hints (Context Menus)

#### Modified Files:
- `src/bot.py`

#### New Features:

**Added Imports:**
```python
from aiogram.types import (
    BotCommand,
    BotCommandScopeAllPrivateChats,
    BotCommandScopeChat,
    ...
)
```

**New Function: `set_bot_commands()`**
- Automatically sets command hints for all users and admins
- Called during bot initialization in `setup_bot()`
- Commands are visible when users type "/" in the chat

**User Commands (All Users):**
- `/start` - 🏠 Початок роботи з ботом
- `/help` - ❓ Показати довідку

**Admin Commands (Additional for Admins):**
- `/users` - 👥 Список користувачів
- `/adduser` - ➕ Додати/оновити користувача
- `/setcombo` - 🎨 Встановити колір комбінації
- `/colors` - 🌈 Показати всі кольори
- `/changes` - 📋 Останні зміни (7 днів)
- `/approvals` - ✅ Запити на підтвердження

**Implementation:**
```python
async def set_bot_commands(bot: Bot):
    """Set bot command hints for users and admins."""
    # Commands for all users
    user_commands = [
        BotCommand(command="start", description="🏠 Початок роботи з ботом"),
        BotCommand(command="help", description="❓ Показати довідку"),
    ]
    
    # Set for all private chats
    await bot.set_my_commands(
        commands=user_commands,
        scope=BotCommandScopeAllPrivateChats()
    )
    
    # Additional admin commands
    admin_commands = [...]
    
    # Set for each admin individually
    for admin_id in config.ADMIN_IDS:
        await bot.set_my_commands(
            commands=admin_commands,
            scope=BotCommandScopeChat(chat_id=admin_id)
        )
```

### 2. Enhanced Error Logging

#### Logging Improvements by Area:

**A. Month Navigation Callback (`callback_month_navigation`)**

Added logging for:
- Debug log when navigation is triggered
- Error log with full traceback when parsing fails
- Warning when user tries to navigate beyond 12-month limit
- Info log when calendar is successfully rendered
- Warning when callback message is missing
- Error log with full context for rendering failures
- Catch-all error handler for unhandled exceptions

```python
logger.debug(f"Month navigation callback: {callback.data}")
logger.error(f"Failed to parse month callback data '{callback.data}': {e}")
logger.warning(f"User tried to navigate beyond 12 months: {requested_date}")
logger.info(f"Calendar updated to {year}-{month:02d}")
logger.error(f"Unhandled error in month navigation callback: {e}", exc_info=True)
```

**B. User Approval Callbacks (`callback_approve_user`, `callback_deny_user`)**

Added logging for:
- Info log when admin approves/denies a user
- Error log when parsing callback data fails
- Warning when user not found
- Info log when user is successfully notified
- Error log for notification failures
- Catch-all error handler with full traceback

```python
logger.info(f"Admin {callback.from_user.id} approving user {user_id}")
logger.error(f"Failed to parse user approval callback data: {e}")
logger.warning(f"User {user_id} not found for approval")
logger.info(f"User {user_id} notified of approval")
logger.error(f"Unhandled error in user approval callback: {e}", exc_info=True)
```

**C. Calendar Rendering (`send_calendar`)**

Enhanced logging for:
- Info log when rendering starts
- Separate error log for image rendering failures
- Debug log for successful calendar send/edit
- Error log with full traceback for send failures

```python
logger.info(f"Rendering calendar for {year}-{month:02d}")
logger.error(f"Failed to render calendar image: {e}", exc_info=True)
logger.debug("Calendar sent successfully")
logger.error(f"Failed to render/send calendar: {e}", exc_info=True)
```

**D. NLP Entry Point (`nlp_entry`)**

Added comprehensive error handling:
- Warning for messages without user or text
- Info log for all user messages
- Debug log for parsed commands
- Error log when parsing fails
- User-friendly error messages
- Catch-all error handler for unhandled exceptions

```python
logger.warning("Received message without user or text")
logger.info(f"User {message.from_user.id}: {message.text}")
logger.debug(f"Parsed command: {cmd.action}")
logger.error(f"Failed to parse utterance: {e}", exc_info=True)
logger.error(f"Unhandled error in NLP entry: {e}", exc_info=True)
```

**E. Admin Commands**

Enhanced logging for `/users` and `/adduser`:
- Info log when admin executes command
- Debug log with details of operation
- Error log for failures with full traceback
- User-friendly error messages

```python
logger.info(f"Admin {message.from_user.id} listing users")
logger.debug(f"Sent {len(users)} users to admin {message.from_user.id}")
logger.info(f"Admin {message.from_user.id} adding/updating user: {name_en}")
logger.error(f"Error in cmd_users: {e}", exc_info=True)
```

**F. Bot Setup (`set_bot_commands`)**

Added logging for:
- Warning when setting commands for specific admin fails
- Info log when all commands are configured
- Error log if command setup completely fails

```python
logger.warning(f"Failed to set commands for admin {admin_id}: {e}")
logger.info("Bot commands configured successfully")
logger.error(f"Failed to set bot commands: {e}")
```

### 3. Error Handling Patterns

#### Consistent Error Handling Structure:

**Try-Catch Blocks:**
All critical functions now have try-catch blocks with:
1. Specific exception handling for known issues
2. Detailed logging with `exc_info=True` for stack traces
3. User-friendly error messages
4. Fallback error handlers for unexpected issues

**Example Pattern:**
```python
try:
    # Main logic
    logger.info("Starting operation...")
    result = perform_operation()
    logger.debug("Operation completed successfully")
except SpecificError as e:
    logger.error(f"Specific error occurred: {e}", exc_info=True)
    await message.answer("❌ Specific error message")
except Exception as e:
    logger.error(f"Unhandled error: {e}", exc_info=True)
    await message.answer("❌ Загальна помилка")
```

### 4. Log Levels Used

- **`DEBUG`**: Detailed information for debugging (successful operations, state changes)
- **`INFO`**: General information (user actions, major operations)
- **`WARNING`**: Unexpected situations that don't break functionality
- **`ERROR`**: Errors that prevent operations from completing

### 5. Benefits

**For Users:**
- ✅ Command hints visible when typing "/" in chat
- ✅ Better error messages when something goes wrong
- ✅ Clearer feedback on what went wrong

**For Developers:**
- ✅ Comprehensive logging for debugging
- ✅ Stack traces for all errors (`exc_info=True`)
- ✅ User action tracking
- ✅ Performance monitoring (render times, etc.)

**For Admins:**
- ✅ Separate command menu with admin-only commands
- ✅ Detailed logs of all admin actions
- ✅ Audit trail for user management

## Usage

### Viewing Command Hints:
1. Open chat with the bot
2. Type "/" 
3. See available commands with descriptions
4. Admins see additional commands automatically

### Checking Logs:
The bot uses `loguru` for logging. All logs include:
- Timestamp
- Log level
- Source location
- Message
- Stack trace (for errors)

**Example log output:**
```
2025-10-11 14:32:15.123 | INFO     | bot:nlp_entry:1139 - User 123456: покажи жовтень
2025-10-11 14:32:15.456 | DEBUG    | bot:nlp_entry:1145 - Parsed command: show_month
2025-10-11 14:32:15.789 | INFO     | bot:send_calendar:292 - Rendering calendar for 2025-10
2025-10-11 14:32:16.012 | DEBUG    | bot:send_calendar:330 - Calendar sent successfully
```

**Error example:**
```
2025-10-11 14:35:22.345 | ERROR    | bot:callback_month_navigation:1004 - Failed to render calendar in callback: Connection timeout
Traceback (most recent call last):
  File "bot.py", line 978, in callback_month_navigation
    image_buffer = renderer.render(year, month)
  ...
```

## Testing Recommendations

1. **Test Command Hints:**
   - Start bot as regular user - should see 2 commands
   - Start bot as admin - should see 8 commands
   - Commands should have emojis and Ukrainian descriptions

2. **Test Error Logging:**
   - Trigger various errors (invalid input, network issues)
   - Check logs for detailed error information
   - Verify user-friendly error messages appear in chat

3. **Test Callback Logging:**
   - Navigate between months
   - Approve/deny users
   - Check logs for debug information

4. **Monitor Production:**
   - Review logs regularly for warnings and errors
   - Track user actions via INFO logs
   - Use ERROR logs to identify issues quickly

## Technical Notes

- Command hints are set during bot initialization
- Admin commands are scoped per-admin using `BotCommandScopeChat`
- All error logs include `exc_info=True` for full stack traces
- Logging follows best practices with appropriate log levels
- All user-facing errors have Ukrainian translations
- Critical operations have multi-level error handling

## Compatibility

- Works with aiogram 3.x
- Compatible with existing code structure
- No breaking changes to existing functionality
- Logging can be configured via loguru settings
