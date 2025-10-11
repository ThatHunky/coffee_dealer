# Coffee Dealer Bot Documentation

Welcome to the Coffee Dealer bot documentation! This directory contains all technical documentation, guides, and implementation details.

## 📋 Table of Contents

### Quick Start Guides

- **[QUICKSTART.md](QUICKSTART.md)** - Quick setup guide for end users
- **[ADMIN_QUICKSTART.md](ADMIN_QUICKSTART.md)** - Quick setup guide for administrators

### Administration

- **[ADMIN_GUIDE.md](ADMIN_GUIDE.md)** - Complete administrator's guide
- **[LOGGING_GUIDE.md](LOGGING_GUIDE.md)** - Log monitoring and debugging reference

### Development

- **[DEVELOPMENT.md](DEVELOPMENT.md)** - Developer setup and contribution guide
- **[PROJECT_SUMMARY.md](PROJECT_SUMMARY.md)** - High-level project architecture overview

### Feature Documentation

- **[USER_MANAGEMENT_FEATURE.md](USER_MANAGEMENT_FEATURE.md)** - User edit/remove functionality
- **[MONTH_NAVIGATION_UPDATE.md](MONTH_NAVIGATION_UPDATE.md)** - Month navigation and emoji system implementation
- **[CONTEXT_HINTS_AND_LOGGING_UPDATE.md](CONTEXT_HINTS_AND_LOGGING_UPDATE.md)** - Command hints and enhanced logging
- **[USER_APPROVAL_FEATURE.md](USER_APPROVAL_FEATURE.md)** - User approval workflow feature
- **[FEATURE_UPDATE.md](FEATURE_UPDATE.md)** - General feature updates
- **[CHANGE_REQUEST_FEATURE.md](CHANGE_REQUEST_FEATURE.md)** - Change request tracking feature

### Implementation & Maintenance

- **[IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)** - Summary of recent implementations
- **[BUGFIXES.md](BUGFIXES.md)** - Bug fix history and known issues

## 🎯 Documentation Categories

### For End Users

Start here if you're a user of the bot:
1. [QUICKSTART.md](QUICKSTART.md) - Get started quickly
2. See available commands in the bot (type `/help`)

### For Administrators

Start here if you manage the bot:
1. [ADMIN_QUICKSTART.md](ADMIN_QUICKSTART.md) - Initial setup
2. [ADMIN_GUIDE.md](ADMIN_GUIDE.md) - Complete admin reference
3. [LOGGING_GUIDE.md](LOGGING_GUIDE.md) - Monitor and troubleshoot

### For Developers

Start here if you're contributing to the bot:
1. [DEVELOPMENT.md](DEVELOPMENT.md) - Setup dev environment
2. [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md) - Understand the architecture
3. Feature docs - Learn about specific implementations

## 🔍 Finding What You Need

### I want to...

- **Use the bot**: → [QUICKSTART.md](QUICKSTART.md)
- **Set up the bot as admin**: → [ADMIN_QUICKSTART.md](ADMIN_QUICKSTART.md)
- **Understand how month navigation works**: → [MONTH_NAVIGATION_UPDATE.md](MONTH_NAVIGATION_UPDATE.md)
- **Debug an issue**: → [LOGGING_GUIDE.md](LOGGING_GUIDE.md)
- **Add a new feature**: → [DEVELOPMENT.md](DEVELOPMENT.md)
- **Understand the codebase**: → [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md)
- **See recent changes**: → [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)

## 📝 Documentation Standards

All documentation in this directory follows these standards:

- **Format**: Markdown (.md)
- **Language**: English (user-facing bot messages are in Ukrainian)
- **Structure**: Clear headings, code examples, emoji for visual clarity
- **Maintenance**: Updated whenever features change

## 🆕 Recent Updates

Latest documentation updates (newest first):

1. **IMPLEMENTATION_SUMMARY.md** - Complete summary of command hints and logging implementation
2. **LOGGING_GUIDE.md** - Operational guide for log monitoring
3. **CONTEXT_HINTS_AND_LOGGING_UPDATE.md** - Command hints and enhanced logging details
4. **MONTH_NAVIGATION_UPDATE.md** - Month navigation and emoji system

## 🤝 Contributing to Documentation

When adding or updating documentation:

1. **Check existing docs first** - Update rather than duplicate
2. **Use clear headings** - Make it scannable
3. **Include examples** - Show, don't just tell
4. **Keep it current** - Update when features change
5. **Use emojis** - Makes docs more readable (✅❌📝🔧 etc.)

## 📧 Questions?

If you can't find what you're looking for:

1. Check the main [README.md](../README.md) in the project root
2. Look through the relevant guide above
3. Check the bot's `/help` command for user-facing features
4. Review the code comments in `src/` directory

## 🎨 Quick Reference

### Bot Features

- ✅ Month navigation with 12-month history
- ✅ Emoji-based user identification (🔵🟣🟢🔴🩷🟡🌈)
- ✅ Command hints for easy discovery
- ✅ AI-powered natural language input
- ✅ User approval workflow
- ✅ Calendar image generation
- ✅ Comprehensive error logging

### Tech Stack

- **Framework**: aiogram 3.x (Telegram Bot API)
- **Database**: SQLModel (SQLite/PostgreSQL)
- **AI/NLP**: Google Gemini AI
- **Image Processing**: Pillow (PIL)
- **Logging**: Loguru
- **Language**: Python 3.11+

### Key Files

- `src/bot.py` - Main bot handlers
- `src/models.py` - Database models
- `src/user_manager.py` - User and emoji management
- `src/image_render.py` - Calendar rendering
- `src/nlp.py` - AI integration

---

**Welcome to the Coffee Dealer bot!** ☕️ Start with the quickstart guide relevant to your role and explore from there.
