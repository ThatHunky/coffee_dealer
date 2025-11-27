"""Main bot entry point"""

import asyncio
import os
import sys
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand
from dotenv import load_dotenv

from bot.database.models import init_db
from bot.database.operations import cleanup_old_shifts, async_session_maker
from bot.middleware.permissions import PermissionMiddleware, is_admin
from bot.handlers import commands, callbacks, messages
from bot.utils.logging_config import setup_logging, get_logger

load_dotenv()

# Set up logging first
setup_logging()
logger = get_logger(__name__)


async def setup_bot_commands(bot: Bot):
    """Set up bot commands for Telegram's command menu"""
    # All commands (admin commands are protected by middleware)
    # Note: Telegram shows these in the menu, but actual access is controlled by middleware
    commands_list = [
        BotCommand(command="start", description="Початок роботи з ботом"),
        BotCommand(command="calendar", description="Показати календар змін"),
        BotCommand(command="history", description="Переглянути історію змін"),
        BotCommand(command="help", description="Показати довідку по командам"),
        BotCommand(command="users", description="Список користувачів"),
        BotCommand(command="adduser", description="Додати/оновити користувача"),
        BotCommand(command="edituser", description="Редагувати користувача"),
        BotCommand(command="setcolor", description="Змінити колір користувача"),
        BotCommand(command="setname", description="Змінити ім'я користувача"),
        BotCommand(
            command="allow", description="Дозволити користувачу використовувати бота"
        ),
        BotCommand(command="hideuser", description="Приховати користувача"),
        BotCommand(command="showuser", description="Показати прихованого користувача"),
        BotCommand(command="clearmonth", description="Очистити всі зміни за місяць"),
    ]

    # Set commands (admin commands are visible but protected by middleware)
    await bot.set_my_commands(commands_list)
    logger = get_logger(__name__)
    logger.info(f"✅ Registered {len(commands_list)} bot commands")


async def main():
    """Main function to start the bot"""
    # Get bot token
    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token:
        logger.error("BOT_TOKEN not found in environment variables!")
        logger.error("Please create a .env file with BOT_TOKEN=your_token")
        sys.exit(1)

    # Initialize database
    logger.info("📦 Initializing database...")
    try:
        await init_db()
        logger.info("✅ Database initialized")
        
        # Clean up old calendar shifts (keep max 1 year)
        logger.info("🧹 Cleaning up old calendar shifts (keeping last 1 year)...")
        async with async_session_maker() as session:
            deleted_count = await cleanup_old_shifts(session, max_age_years=1)
            if deleted_count > 0:
                logger.info(f"✅ Deleted {deleted_count} old shift(s) older than 1 year")
            else:
                logger.debug("No old shifts to clean up")
    except Exception as e:
        logger.error(f"❌ Database initialization error: {e}")
        logger.error(
            "Make sure DATABASE_URL is correct (defaults to SQLite: sqlite+aiosqlite:///shiftbot.db)"
        )
        sys.exit(1)

    # Initialize bot and dispatcher
    bot = Bot(token=bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    # Register middleware
    dp.message.middleware(PermissionMiddleware())
    dp.callback_query.middleware(PermissionMiddleware())

    # Register routers
    dp.include_router(commands.router)
    dp.include_router(callbacks.router)
    dp.include_router(messages.router)

    # Set up bot commands for Telegram's command hints
    await setup_bot_commands(bot)

    # Get bot info
    try:
        bot_info = await bot.get_me()
        logger.info(f"✅ Bot connected: @{bot_info.username} ({bot_info.first_name})")
    except Exception as e:
        logger.warning(f"⚠️ Could not get bot info: {e}")

    # Start polling
    logger.info("🤖 Starting bot polling...")
    logger.info("📡 Bot is now running and listening for messages...")
    logger.info("💡 Press Ctrl+C to stop the bot")
    try:
        await dp.start_polling(bot, skip_updates=True)
    except KeyboardInterrupt:
        logger.warning("\n⚠️ Received interrupt signal")
    except Exception as e:
        logger.error(f"❌ Error during polling: {e}", exc_info=True)
        sys.exit(1)
    finally:
        logger.info("🛑 Stopping bot...")
        await bot.session.close()
        logger.info("✅ Bot stopped successfully")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n👋 Bot stopped by user")
