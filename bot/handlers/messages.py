"""Message handlers for natural language processing"""

from datetime import date, datetime, timedelta
from typing import List, Dict, Any
from aiogram import Router, F
from aiogram.types import Message, PhotoSize
from aiogram.filters import Command

from bot.database.operations import (
    get_all_users, create_user, update_user, create_request, get_shifts_in_range,
    get_shift, create_or_update_shift, delete_shift,
    async_session_maker
)
from bot.services.gemini import gemini_service
from bot.services.notifications import notify_admins_of_request
from bot.middleware.permissions import is_admin
from bot.utils.colors import parse_color

router = Router()


@router.message(F.photo)
async def handle_image(message: Message):
    """Handle image messages - parse calendar images for admins"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Тільки адміністратори можуть імпортувати календарі з зображень.")
        return
    
    # Get the largest photo
    photo: PhotoSize = max(message.photo, key=lambda p: p.file_size)
    
    # Download image
    file = await message.bot.get_file(photo.file_id)
    image_data = b""
    async for chunk in message.bot.download_file(file.file_path):
        image_data += chunk
    
    await message.answer("🔄 Аналізую зображення календаря...")
    
    # Get users for context
    async with async_session_maker() as session:
        users = await get_all_users(session)
        users_dict = {u.user_id: u for u in users}
        users_list = [
            {
                "user_id": u.user_id,
                "name": u.name,
                "username": u.username,
                "color_code": u.color_code
            }
            for u in users
        ]
    
    # Parse image with Gemini
    parsed = await gemini_service.parse_calendar_image(image_data, users_list)
    
    if not parsed:
        await message.answer(
            "❌ Не вдалося розпізнати календар на зображенні. "
            "Переконайтеся, що зображення містить календар з кольоровими днями."
        )
        return
    
    year = parsed.get("year")
    month = parsed.get("month")
    assignments = parsed.get("assignments", [])
    
    if not year or not month or not assignments:
        await message.answer("❌ Не вдалося визначити рік, місяць або призначення з зображення.")
        return
    
    # Apply assignments to database
    executed = []
    async with async_session_maker() as session:
        for assignment in assignments:
            try:
                date_str = assignment.get("date")
                user_names = assignment.get("user_names", [])
                user_ids = assignment.get("user_ids", [])
                
                if not date_str:
                    continue
                
                shift_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                
                # Match user names to user IDs if IDs not provided
                if not user_ids and user_names:
                    matched_ids = []
                    for name in user_names:
                        for user in users:
                            if user.name == name or user.name.lower() == name.lower():
                                matched_ids.append(user.user_id)
                                break
                    user_ids = matched_ids
                
                if user_ids:
                    await create_or_update_shift(session, shift_date, user_ids)
                    executed.append(f"✅ {date_str}: {', '.join(user_names)}")
            except Exception as e:
                executed.append(f"❌ Помилка для {assignment.get('date', 'unknown')}: {str(e)}")
    
    if executed:
        summary = "\n".join(executed[:20])  # Limit to first 20
        if len(executed) > 20:
            summary += f"\n... та ще {len(executed) - 20} призначень"
        await message.answer(
            f"✅ Календарь імпортовано для {month}/{year}:\n\n{summary}"
        )
    else:
        await message.answer("⚠️ Не вдалося імпортувати жодних призначень.")


@router.message(F.text & ~F.text.startswith("/"))
async def handle_natural_language(message: Message):
    """Handle natural language messages"""
    user_id = message.from_user.id
    text = message.text.strip()
    
    # Skip empty messages
    if not text:
        return
    
    async with async_session_maker() as session:
        users = await get_all_users(session)
        users_dict = {u.user_id: u for u in users}
        users_list = [
            {
                "user_id": u.user_id,
                "name": u.name,
                "username": u.username
            }
            for u in users
        ]
    
    # Check if user is admin
    if is_admin(user_id):
        # Admin can execute commands directly
        await handle_admin_nlp_command(message, users_list, users_dict)
    else:
        # Regular user - create request
        await handle_user_request(message, user_id, users_list)


async def handle_user_request(
    message: Message,
    user_id: int,
    users_list: List[Dict[str, Any]]
):
    """Handle user request - create request and notify admins"""
    text = message.text
    
    # Parse with Gemini
    parsed_intent = await gemini_service.parse_user_request(text, users_list)
    
    if not parsed_intent:
        await message.answer(
            "❌ Не вдалося обробити ваш запит. "
            "Будь ласка, спробуйте сформулювати його інакше або зверніться до адміністратора."
        )
        return
    
    # Create request in database
    async with async_session_maker() as session:
        request = await create_request(
            session,
            user_id=user_id,
            message=text,
            parsed_intent=parsed_intent
        )
    
    # Notify admins
    await notify_admins_of_request(
        message.bot,
        request.id,
        user_id,
        text,
        parsed_intent
    )
    
    await message.answer(
        "✅ Ваш запит отримано! Адміністратори були повідомлені та розглянуть його найближчим часом."
    )


async def handle_admin_nlp_command(
    message: Message,
    users_list: List[Dict[str, Any]],
    users_dict: Dict[int, Any]
):
    """Handle admin natural language command - execute directly"""
    text = message.text
    
    # Check if it's a user management command
    user_management_keywords = ["додай користувача", "add user", "створи користувача", 
                                "edit user", "редагуй користувача", "зміни користувача",
                                "додати користувача", "створити користувача"]
    if any(keyword in text.lower() for keyword in user_management_keywords):
        await handle_user_management_nlp(message, users_list, users_dict)
        return
    
    # Get current shifts for context
    today = date.today()
    start_date = date(today.year, today.month, 1)
    end_date = date(today.year, today.month, 28) + timedelta(days=4)
    end_date = date(end_date.year, end_date.month, 1) - timedelta(days=1)
    
    async with async_session_maker() as session:
        shifts = await get_shifts_in_range(session, start_date, end_date)
        current_shifts = [
            {
                "date": s.date.isoformat(),
                "user_ids": s.user_ids,
                "user_names": [users_dict.get(uid, {}).get("name", f"User {uid}") for uid in s.user_ids]
            }
            for s in shifts
        ]
    
    # Parse with Gemini
    parsed = await gemini_service.parse_admin_command(text, users_list, current_shifts)
    
    if not parsed:
        await message.answer(
            "❌ Не вдалося обробити команду. "
            "Будь ласка, спробуйте сформулювати її інакше."
        )
        return
    
    if parsed.get("confidence", 0) < 0.7:
        await message.answer(
            f"⚠️ Низька впевненість у розпізнаванні ({parsed.get('confidence', 0):.0%}). "
            "Будь ласка, уточніть команду."
        )
        return
    
    # Execute the command
    action = parsed.get("action")
    dates = parsed.get("dates", [])
    user_ids = parsed.get("user_ids", [])
    
    if not dates or not user_ids:
        await message.answer(
            "❌ Не вдалося визначити дати або користувачів. "
            "Будь ласка, уточніть команду."
        )
        return
    
    # Execute based on action
    executed = []
    async with async_session_maker() as session:
        for date_str in dates:
            try:
                shift_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                
                if action == "assign":
                    shift = await get_shift(session, shift_date)
                    current_user_ids = list(shift.user_ids) if shift else []
                    for uid in user_ids:
                        if uid not in current_user_ids:
                            current_user_ids.append(uid)
                    await create_or_update_shift(session, shift_date, current_user_ids)
                    executed.append(f"✅ Призначено на {date_str}")
                
                elif action == "unassign":
                    shift = await get_shift(session, shift_date)
                    if shift:
                        current_user_ids = list(shift.user_ids)
                        for uid in user_ids:
                            if uid in current_user_ids:
                                current_user_ids.remove(uid)
                        if current_user_ids:
                            await create_or_update_shift(session, shift_date, current_user_ids)
                        else:
                            await delete_shift(session, shift_date)
                        executed.append(f"✅ Знято з {date_str}")
                
                elif action == "clear":
                    await delete_shift(session, shift_date)
                    executed.append(f"✅ Очищено {date_str}")
                
            except ValueError:
                executed.append(f"❌ Невірна дата: {date_str}")
            except Exception as e:
                executed.append(f"❌ Помилка для {date_str}: {str(e)}")
    
    if executed:
        summary = "\n".join(executed)
        await message.answer(f"📋 Виконано:\n\n{summary}")
    else:
        await message.answer("❌ Не вдалося виконати команду.")


async def handle_user_management_nlp(
    message: Message,
    users_list: List[Dict[str, Any]],
    users_dict: Dict[int, Any]
):
    """Handle admin natural language commands for user management"""
    text = message.text
    
    # Parse with Gemini
    parsed = await gemini_service.parse_user_management_command(text, users_list)
    
    if not parsed:
        await message.answer(
            "❌ Не вдалося обробити команду управління користувачами. "
            "Будь ласка, спробуйте сформулювати її інакше."
        )
        return
    
    if parsed.get("confidence", 0) < 0.7:
        await message.answer(
            f"⚠️ Низька впевненість у розпізнаванні ({parsed.get('confidence', 0):.0%}). "
            "Будь ласка, уточніть команду."
        )
        return
    
    action = parsed.get("action")
    user_id = parsed.get("user_id")
    name = parsed.get("name")
    color = parsed.get("color")
    
    async with async_session_maker() as session:
        if action in ["add", "create"]:
            # Add new user
            if not name:
                await message.answer("❌ Не вдалося визначити ім'я користувача.")
                return
            
            # If user_id not provided, we need to ask for it or generate a temporary one
            if not user_id:
                await message.answer(
                    "❌ Для додавання користувача потрібен user_id. "
                    "Використовуйте: /adduser <user_id> <name> [color] "
                    "або вкажіть user_id в повідомленні."
                )
                return
            
            # Check if user exists
            from bot.database.operations import get_user
            existing_user = await get_user(session, user_id)
            if existing_user:
                await message.answer(f"❌ Користувач з ID {user_id} вже існує.")
                return
            
            # Parse color
            color_code = None
            if color:
                color_code = parse_color(color)
            
            # Assign default color if not provided
            if not color_code:
                from bot.utils.colors import assign_color_to_user
                users = await get_all_users(session)
                existing_colors = [u.color_code for u in users if u.color_code]
                color_code = assign_color_to_user(len(users), existing_colors)
            
            user = await create_user(
                session,
                user_id=user_id,
                name=name,
                color_code=color_code
            )
            
            await message.answer(
                f"✅ Користувач {user.name} (ID: {user_id}) доданий.\n"
                f"Колір: {color_code}"
            )
        
        elif action in ["edit", "update"]:
            # Edit existing user
            if not user_id:
                await message.answer("❌ Не вдалося визначити user_id для редагування.")
                return
            
            from bot.database.operations import get_user
            user = await get_user(session, user_id)
            if not user:
                await message.answer(f"❌ Користувач з ID {user_id} не знайдений.")
                return
            
            # Update fields
            updates = {}
            if name:
                updates["name"] = name
            if color:
                color_code = parse_color(color)
                if color_code:
                    updates["color_code"] = color_code
            
            if updates:
                await update_user(session, user_id, **updates)
                updated_user = await get_user(session, user_id)
                await message.answer(
                    f"✅ Користувач {updated_user.name} (ID: {user_id}) оновлено.\n"
                    + "\n".join([f"  {k}: {v}" for k, v in updates.items()])
                )
            else:
                await message.answer("⚠️ Не вказано полів для оновлення.")
        
        else:
            await message.answer(f"❌ Невідома дія: {action}")

