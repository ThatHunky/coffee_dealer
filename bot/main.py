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
from bot.middleware.permissions import PermissionMiddleware, is_admin
from bot.handlers import commands, callbacks, messages

load_dotenv()


async def setup_bot_commands(bot: Bot):
    """Set up bot commands for Telegram's command menu"""
    # All commands (admin commands are protected by middleware)
    commands_list = [
        BotCommand(command="start", description="Початок роботи з ботом"),
        BotCommand(command="calendar", description="Показати календар змін"),
        BotCommand(command="history", description="Переглянути історію змін"),
        BotCommand(command="help", description="Довідка по командам"),
        BotCommand(command="allow", description="[Адмін] Дозволити користувачу використовувати бота"),
        BotCommand(command="adduser", description="[Адмін] Додати нового користувача"),
        BotCommand(command="setcolor", description="[Адмін] Змінити колір користувача"),
        BotCommand(command="setname", description="[Адмін] Змінити ім'я користувача"),
        BotCommand(command="listusers", description="[Адмін] Список всіх користувачів"),
        BotCommand(command="users", description="[Адмін] Список користувачів (alias)"),
        BotCommand(command="edituser", description="[Адмін] Редагувати користувача (NLP)"),
        BotCommand(command="hideuser", description="[Адмін] Приховати користувача"),
        BotCommand(command="showuser", description="[Адмін] Показати прихованого користувача"),
    ]
    
    # Set commands (admin commands are visible but protected by middleware)
    await bot.set_my_commands(commands_list)
    print(f"✅ Registered {len(commands_list)} bot commands")


async def main():
    """Main function to start the bot"""
    # Get bot token
    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token:
        print("❌ BOT_TOKEN not found in environment variables!")
        print("Please create a .env file with BOT_TOKEN=your_token")
        sys.exit(1)
    
    # Initialize database
    print("📦 Initializing database...")
    try:
        await init_db()
        print("✅ Database initialized")
    except Exception as e:
        print(f"❌ Database initialization error: {e}")
        print("Make sure DATABASE_URL is correct (defaults to SQLite: sqlite+aiosqlite:///shiftbot.db)")
        sys.exit(1)
    
    # Initialize bot and dispatcher
    bot = Bot(
        token=bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
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
        print(f"✅ Bot connected: @{bot_info.username} ({bot_info.first_name})")
    except Exception as e:
        print(f"⚠️ Could not get bot info: {e}")
    
    # Start polling
    print("🤖 Starting bot polling...")
    print("📡 Bot is now running and listening for messages...")
    print("💡 Press Ctrl+C to stop the bot\n")
    try:
        await dp.start_polling(bot, skip_updates=True)
    except KeyboardInterrupt:
        print("\n⚠️ Received interrupt signal")
    except Exception as e:
        print(f"❌ Error during polling: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        print("🛑 Stopping bot...")
        await bot.session.close()
        print("✅ Bot stopped successfully")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Bot stopped by user")

