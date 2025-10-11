"""Main entry point for the Coffee Dealer bot."""

import asyncio

from loguru import logger

from .bot import setup_bot
from .config import config
from .repo import init_db


async def main():
    """Run the bot."""
    # Validate configuration
    try:
        config.validate()
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        logger.info("Please create a .env file based on .env.example")
        return

    # Initialize database
    logger.info("Initializing database...")
    init_db()

    # Set up bot
    logger.info("Starting Coffee Dealer bot...")
    bot, dp = await setup_bot()

    # Start polling
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
