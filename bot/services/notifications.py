"""Admin notification service"""

from typing import List, Dict, Any
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.database.operations import get_admins, get_user, async_session_maker
from bot.utils.colors import get_color_emoji


async def notify_admins_of_request(
    bot: Bot,
    request_id: int,
    user_id: int,
    message: str,
    parsed_intent: Dict[str, Any]
) -> None:
    """
    Notify all admins about a user request.
    
    Args:
        bot: Bot instance
        request_id: Request ID
        user_id: User who made the request
        message: Original message
        parsed_intent: Parsed intent from Gemini
    """
    async with async_session_maker() as session:
        admins = await get_admins(session)
        user = await get_user(session, user_id)
    
    if not user:
        return
    
    # Build notification text
    user_info = f"👤 {user.name}"
    if user.username:
        user_info += f" (@{user.username})"
    user_info += f" (ID: {user_id})"
    
    text = f"🔔 Новий запит від користувача\n\n"
    text += f"{user_info}\n\n"
    text += f"📝 Повідомлення:\n{message}\n\n"
    
    if parsed_intent:
        text += f"🤖 Розпізнано:\n"
        text += f"Дія: {parsed_intent.get('action', 'невідомо')}\n"
        if parsed_intent.get('dates'):
            text += f"Дати: {', '.join(parsed_intent['dates'])}\n"
        if parsed_intent.get('user_names'):
            text += f"Користувачі: {', '.join(parsed_intent['user_names'])}\n"
        if parsed_intent.get('summary'):
            text += f"Опис: {parsed_intent['summary']}\n"
        text += f"Впевненість: {parsed_intent.get('confidence', 0):.0%}\n"
    
    # Build approval buttons
    builder = InlineKeyboardBuilder()
    builder.button(
        text="✅ Затвердити",
        callback_data=f"approve_request_{request_id}"
    )
    builder.button(
        text="❌ Відхилити",
        callback_data=f"reject_request_{request_id}"
    )
    builder.adjust(2)
    keyboard = builder.as_markup()
    
    # Send to all admins
    for admin in admins:
        try:
            await bot.send_message(
                chat_id=admin.user_id,
                text=text,
                reply_markup=keyboard
            )
        except Exception as e:
            print(f"Error notifying admin {admin.user_id}: {e}")


async def notify_user_of_request_status(
    bot: Bot,
    user_id: int,
    request_id: int,
    status: str,
    message: str = ""
) -> None:
    """
    Notify user about their request status.
    
    Args:
        bot: Bot instance
        user_id: User ID
        request_id: Request ID
        status: Status (approved/rejected)
        message: Additional message
    """
    if status == "approved":
        text = f"✅ Ваш запит #{request_id} було затверджено!"
    elif status == "rejected":
        text = f"❌ Ваш запит #{request_id} було відхилено."
    else:
        return
    
    if message:
        text += f"\n\n{message}"
    
    try:
        await bot.send_message(chat_id=user_id, text=text)
    except Exception as e:
        print(f"Error notifying user {user_id}: {e}")

