"""Logging configuration for the bot"""

import logging
import os
import glob
import time
from logging.handlers import RotatingFileHandler
from datetime import datetime, timedelta


def setup_logging(log_dir: str = "logs"):
    """
    Set up logging configuration with both console and file handlers.
    
    Args:
        log_dir: Directory to store log files (default: "logs")
    """
    # Create logs directory if it doesn't exist
    os.makedirs(log_dir, exist_ok=True)
    
    # Get root logger
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    
    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    console_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    
    # Console handler (INFO and above)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # Main log file (all levels, rotated at 10MB, keeps 5 backups)
    main_log_file = os.path.join(log_dir, "bot.log")
    file_handler = RotatingFileHandler(
        main_log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(detailed_formatter)
    logger.addHandler(file_handler)
    
    # Separate log file for image imports (rotated at 5MB, keeps 3 backups)
    image_log_file = os.path.join(log_dir, "image_import.log")
    image_handler = RotatingFileHandler(
        image_log_file,
        maxBytes=5 * 1024 * 1024,  # 5MB
        backupCount=3,
        encoding='utf-8'
    )
    image_handler.setLevel(logging.DEBUG)
    image_handler.setFormatter(detailed_formatter)
    # Filter to capture any log message containing these prefixes
    class ImageImportFilter(logging.Filter):
        def filter(self, record):
            msg = record.getMessage()
            return '[IMAGE IMPORT]' in msg or '[GEMINI]' in msg or '[GEMINI RETRY]' in msg
    image_handler.addFilter(ImageImportFilter())
    logger.addHandler(image_handler)
    
    # Separate log file for errors (keeps all errors)
    error_log_file = os.path.join(log_dir, "errors.log")
    error_handler = RotatingFileHandler(
        error_log_file,
        maxBytes=5 * 1024 * 1024,  # 5MB
        backupCount=10,  # Keep more error logs
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(detailed_formatter)
    logger.addHandler(error_handler)
    
    logger.info(f"✅ Logging configured: logs directory='{log_dir}'")
    logger.info(f"   - Main log: {main_log_file}")
    logger.info(f"   - Image import log: {image_log_file}")
    logger.info(f"   - Error log: {error_log_file}")
    
    # Clean up old log files
    cleanup_old_logs(log_dir, logger)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a specific module.
    
    Args:
        name: Logger name (usually __name__)
    
    Returns:
        Logger instance
    """
    return logging.getLogger(name)


def cleanup_old_logs(log_dir: str, logger: logging.Logger, max_age_days: int = 30):
    """
    Clean up log files older than specified days.
    
    Args:
        log_dir: Directory containing log files
        logger: Logger instance for logging cleanup actions
        max_age_days: Maximum age in days for log files (default: 30)
    """
    if not os.path.exists(log_dir):
        return
    
    try:
        cutoff_time = time.time() - (max_age_days * 24 * 60 * 60)
        deleted_count = 0
        deleted_size = 0
        
        # Find all log files in the directory (including rotated backups)
        log_patterns = [
            os.path.join(log_dir, "*.log"),
            os.path.join(log_dir, "*.log.*"),  # Rotated backups
        ]
        
        for pattern in log_patterns:
            for log_file in glob.glob(pattern):
                try:
                    file_stat = os.stat(log_file)
                    # Check file modification time
                    if file_stat.st_mtime < cutoff_time:
                        file_size = file_stat.st_size
                        os.remove(log_file)
                        deleted_count += 1
                        deleted_size += file_size
                        logger.debug(f"Deleted old log file: {log_file} (age: {(time.time() - file_stat.st_mtime) / (24*60*60):.1f} days)")
                except OSError as e:
                    logger.warning(f"Could not delete old log file {log_file}: {e}")
        
        if deleted_count > 0:
            size_mb = deleted_size / (1024 * 1024)
            logger.info(f"🧹 Cleaned up {deleted_count} old log file(s), freed {size_mb:.2f} MB")
    except Exception as e:
        logger.error(f"Error cleaning up old logs: {e}", exc_info=True)


class PrintToLogger:
    """Wrapper class that intercepts print() calls and logs them"""
    
    def __init__(self, logger_instance: logging.Logger):
        self.logger = logger_instance
        self.original_print = __builtins__['print'] if isinstance(__builtins__, dict) else __builtins__.print
    
    def __call__(self, *args, **kwargs):
        # Call original print
        self.original_print(*args, **kwargs)
        
        # Also log
        message = ' '.join(str(arg) for arg in args)
        if message:
            # Determine log level from message content
            if '[IMAGE IMPORT]' in message or '[GEMINI]' in message:
                if '❌' in message or 'ERROR' in message.upper() or 'error' in message.lower():
                    self.logger.error(message)
                elif '⚠️' in message or 'WARNING' in message.upper():
                    self.logger.warning(message)
                elif '✅' in message or 'SUCCESS' in message.upper():
                    self.logger.info(message)
                else:
                    self.logger.debug(message)
            else:
                # For other messages, log at info level
                self.logger.info(message)

