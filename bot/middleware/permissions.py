"""Permission checking middleware"""

import os
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from dotenv import load_dotenv

from bot.database.operations import get_user, async_session_maker

load_dotenv()

# Get admin IDs from environment
ADMIN_IDS = [int(uid.strip()) for uid in os.getenv("ADMIN_IDS", "").split(",") if uid.strip()]


class PermissionMiddleware(BaseMiddleware):
    """Middleware to check user permissions"""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """Check if user has permission to interact with bot"""
        
        # Get user ID from event
        user_id = None
        if isinstance(event, Message):
            user_id = event.from_user.id if event.from_user else None
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id if event.from_user else None
        
        if not user_id:
            return await handler(event, data)
        
        # Check if user is admin (from env)
        if user_id in ADMIN_IDS:
            # Ensure admin user exists in database
            async with async_session_maker() as session:
                user = await get_user(session, user_id)
                if not user:
                    # Create admin user if doesn't exist
                    from bot.database.operations import create_user
                    await create_user(
                        session,
                        user_id=user_id,
                        name=event.from_user.full_name or f"User {user_id}",
                        username=event.from_user.username,
                        is_admin=True,
                        is_allowed=True
                    )
                elif not user.is_admin or not user.is_allowed:
                    # Update existing user to admin
                    from bot.database.operations import update_user
                    await update_user(
                        session,
                        user_id=user_id,
                        is_admin=True,
                        is_allowed=True
                    )
            return await handler(event, data)
        
        # Check if user is allowed (from database)
        async with async_session_maker() as session:
            user = await get_user(session, user_id)
            if not user or not user.is_allowed:
                # Send not authorized message
                if isinstance(event, Message):
                    await event.answer(
                        "❌ Ви не маєте дозволу на використання цього бота. "
                        "Зверніться до адміністратора."
                    )
                elif isinstance(event, CallbackQuery):
                    await event.answer(
                        "❌ Ви не маєте дозволу на використання цього бота.",
                        show_alert=True
                    )
                return
        
        return await handler(event, data)


def is_admin(user_id: int) -> bool:
    """Check if user is admin"""
    return user_id in ADMIN_IDS


async def is_user_allowed(user_id: int) -> bool:
    """Check if user is allowed to interact with bot"""
    if is_admin(user_id):
        return True
    
    async with async_session_maker() as session:
        user = await get_user(session, user_id)
        return user is not None and user.is_allowed

