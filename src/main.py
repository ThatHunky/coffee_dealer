"""Main entry point for the Coffee Dealer bot."""

import asyncio
import sys
from pathlib import Path

from loguru import logger

from .bot import setup_bot
from .config import config
from .repo import init_db


def setup_logging():
    """Configure file-based logging with rotation and retention."""
    # Remove default handler
    logger.remove()

    # Add console handler (colorized, minimal format)
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
        level=config.LOG_LEVEL,
        colorize=True,
    )

    # Create logs directory if it doesn't exist
    log_dir = Path(config.LOG_DIR)
    log_dir.mkdir(exist_ok=True)

    # Add file handler with rotation and retention
    logger.add(
        log_dir / "coffee_dealer_{time:YYYY-MM-DD}.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level=config.LOG_LEVEL,
        rotation=config.LOG_ROTATION,  # Rotate at midnight
        retention=config.LOG_RETENTION,  # Keep logs for 7 days
        compression="zip",  # Compress old logs
        encoding="utf-8",
        backtrace=True,
        diagnose=True,
    )

    logger.info(
        "Logging configured", log_dir=str(log_dir), retention=config.LOG_RETENTION
    )


async def main():
    """Run the bot."""
    # Set up logging first
    setup_logging()

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
