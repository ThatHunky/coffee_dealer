"""Helper to convert print statements to logging"""

import logging
import sys

logger = logging.getLogger(__name__)

# Monkey patch print to also log (only for specific modules)
_original_print = print

def print_to_logger(*args, **kwargs):
    """Wrapper around print that also logs messages"""
    # Call original print first
    _original_print(*args, **kwargs)
    
    # Also log the message
    message = ' '.join(str(arg) for arg in args)
    if '[IMAGE IMPORT]' in message or '[GEMINI]' in message:
        if '❌' in message or 'ERROR' in message.upper():
            logger.error(message)
        elif '⚠️' in message or 'WARNING' in message.upper():
            logger.warning(message)
        elif '✅' in message or 'SUCCESS' in message.upper():
            logger.info(message)
        else:
            logger.debug(message)

