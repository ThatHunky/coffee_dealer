# GitHub Copilot Instructions for Coffee Dealer Bot

## 🎯 Project Overview

This is a Telegram bot for managing coffee shop schedules with AI-powered natural language processing. Built with aiogram 3.x, SQLModel, and Google Gemini AI.

## 📁 Repository Structure Rules

### Documentation Organization

**CRITICAL**: All documentation files MUST be placed in the `docs/` directory.

- ✅ **ALLOWED at root**: `README.md`, `LICENSE`, `pyproject.toml`, `requirements.txt`, `docker-compose.yml`, `Dockerfile`, `setup.sh`
- ❌ **FORBIDDEN at root**: Any `.md` files except README.md and LICENSE
- ✅ **Required location for docs**: `/docs/` directory

### When Creating Documentation

1. **Always use the `/docs/` directory** for:

   - Feature update documentation
   - Implementation guides
   - Admin guides
   - User guides
   - API documentation
   - Change logs
   - Bug fix documentation
   - Any other markdown files

2. **Naming conventions**:

   - Use UPPERCASE for major docs: `FEATURE_NAME.md`
   - Use lowercase for guides: `guide_name.md`
   - Use snake_case or kebab-case, not spaces
   - Be descriptive but concise

3. **Before creating a new doc**, check if existing docs can be updated instead

### Code Organization

```
coffee_dealer/
├── src/               # All Python source code
│   ├── bot.py        # Main bot handlers
│   ├── models.py     # Database models
│   ├── user_manager.py
│   ├── image_render.py
│   ├── nlp.py        # AI/NLP functionality
│   └── ...
├── tests/            # All test files
├── docs/             # ALL documentation (except README/LICENSE)
├── data/             # Database and runtime data
├── fonts/            # Font files for image rendering
├── .github/          # GitHub workflows and configs
└── README.md         # Main project readme (root only)
```

## 🔧 Development Guidelines

### Code Style

- **Language**: Python 3.11+
- **Framework**: aiogram 3.x (async)
- **Type hints**: Always use type hints
- **Logging**: Use loguru with appropriate levels (DEBUG/INFO/WARNING/ERROR)
- **Error handling**: Always use try-catch with `exc_info=True` for errors
- **Internationalization**: All user-facing messages in Ukrainian

### When Modifying Code

1. **Check current file contents** before editing (files may have changed)
2. **Include 3-5 lines of context** in replace_string_in_file operations
3. **Run tests** after significant changes
4. **Update documentation** in `/docs/` if behavior changes
5. **Add logging** for new features (INFO for actions, ERROR for failures)

### Bot-Specific Rules

1. **User messages**: Always in Ukrainian (🇺🇦)
2. **Command hints**: Use emojis for visual clarity
3. **Inline keyboards**: Use callback_data format: "action_param1_param2"
4. **Admin commands**: Check admin permissions before execution
5. **Database operations**: Use SQLModel async patterns
6. **AI responses**: Use Gemini AI for natural language parsing

## 📝 Documentation Standards

### When Creating Feature Documentation

Include these sections:

1. **Overview**: What the feature does
2. **Implementation Details**: Technical changes made
3. **Files Modified**: List all changed files
4. **Usage Examples**: How to use the feature
5. **Testing**: How to verify it works
6. **Dependencies**: Any new packages added

### Documentation File Naming

- Feature updates: `FEATURE_NAME_UPDATE.md`
- Guides: `TOPIC_GUIDE.md`
- Quick starts: `TOPIC_QUICKSTART.md`
- Summaries: `IMPLEMENTATION_SUMMARY.md`

## 🚫 What NOT to Do

1. ❌ **Don't create markdown files at repository root** (except README/LICENSE)
2. ❌ **Don't create multiple files for the same feature** - update existing docs
3. ❌ **Don't remove existing logging** - only add or enhance
4. ❌ **Don't change user-facing messages to English** - keep Ukrainian
5. ❌ **Don't modify database schema** without discussing migration strategy
6. ❌ **Don't add dependencies** without updating requirements.txt
7. ❌ **Don't create duplicate documentation** - check `/docs/` first

## ✅ Best Practices

### File Operations

```python
# ✅ GOOD: Check file before editing
read_file("src/bot.py", start_line=1, end_line=50)
# Then make informed edits

# ❌ BAD: Edit blindly without checking current state
```

### Documentation Creation

```python
# ✅ GOOD: Place in docs folder
create_file("docs/NEW_FEATURE.md", content="...")

# ❌ BAD: Place at root
create_file("NEW_FEATURE.md", content="...")
```

### Error Handling

```python
# ✅ GOOD: Comprehensive logging
try:
    await some_operation()
    logger.info("Operation successful", user_id=user.id)
except Exception as e:
    logger.error("Operation failed", user_id=user.id, exc_info=True)
    await message.answer("Помилка операції")

# ❌ BAD: Silent failures
try:
    await some_operation()
except:
    pass
```

## 🔍 Before Making Changes

Always ask yourself:

1. Do I need to check the current file state? (if file may have changed: YES)
2. Is there existing documentation I should update instead of creating new?
3. Should this doc go in `/docs/` or at root? (99% of time: `/docs/`)
4. Am I adding proper error logging?
5. Are my user messages in Ukrainian?
6. Do I need to update requirements.txt?

## 📚 Key Files Reference

- **`src/bot.py`**: Main bot handlers, commands, callbacks
- **`src/models.py`**: Database models (User, Assignment, Day)
- **`src/user_manager.py`**: User config, emoji/color management
- **`src/image_render.py`**: Calendar PNG generation
- **`src/nlp.py`**: Google Gemini AI integration
- **`requirements.txt`**: Python dependencies (update when adding packages)
- **`docs/`**: All documentation files

## 🎨 Current Features

- ✅ Month navigation with inline keyboard (12-month limit)
- ✅ Emoji legend system (🔵🟣🟢🔴🩷🟡🌈)
- ✅ Command hints for users and admins
- ✅ Comprehensive error logging
- ✅ AI-powered natural language parsing
- ✅ User approval workflow
- ✅ Dynamic color/emoji assignments
- ✅ Calendar image rendering
- ✅ Admin management commands

## 🔐 Security Notes

- Never log sensitive data (passwords, tokens, API keys)
- Admin IDs configured in environment variables
- User IDs logged for audit trail (not sensitive)
- All admin actions require permission check

## 🎯 Summary

**Golden Rule**: When in doubt, check existing files first, put docs in `/docs/`, and add comprehensive logging with Ukrainian user messages.

**Documentation Rule**: If it's a `.md` file and it's not README.md or LICENSE, it goes in `/docs/`. No exceptions.

---

_These instructions help maintain code quality and repository organization. Follow them to keep the Coffee Dealer bot clean, documented, and maintainable._
