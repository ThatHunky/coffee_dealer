"""Message handlers for natural language processing"""

import io
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
from bot.utils.logging_config import get_logger

router = Router()
logger = get_logger(__name__)


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
    image_file = await message.bot.download_file(file.file_path)
    
    # Read bytes from BytesIO object (download_file returns BytesIO in some aiogram versions)
    if isinstance(image_file, io.BytesIO):
        image_data = image_file.read()
    elif isinstance(image_file, bytes):
        image_data = image_file
    elif hasattr(image_file, 'read'):
        image_data = image_file.read()
    else:
        # Fallback: try to convert to bytes
        image_data = bytes(image_file) if image_file else b''
    
    await message.answer("🔄 Аналізую зображення календаря...")
    
    logger.info(f"[IMAGE IMPORT] Received image from user {message.from_user.id}")
    logger.info(f"[IMAGE IMPORT] Image details: {len(image_data)} bytes, file_id: {photo.file_id}")
    logger.info(f"[IMAGE IMPORT] Photo sizes available: {[(p.width, p.height, p.file_size) for p in message.photo]}")
    logger.info(f"[IMAGE IMPORT] Selected largest photo: {photo.width}x{photo.height}, {photo.file_size} bytes")
    
    # Get users for context
    async with async_session_maker() as session:
        users = await get_all_users(session, include_hidden=False)
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
        logger.info(f"[IMAGE IMPORT] Loaded {len(users_list)} users for context:")
        for user in users_list:
            logger.debug(f"[IMAGE IMPORT]   - {user['name']} (ID: {user['user_id']}, Color: {user.get('color_code', 'N/A')})")
    
    # Parse image with Gemini
    logger.info(f"[IMAGE IMPORT] Calling Gemini API to parse calendar image...")
    parsed = await gemini_service.parse_calendar_image(image_data, users_list)
    
    if not parsed:
        logger.error("[IMAGE IMPORT] Gemini parsing returned None - check logs above for details")
        await message.answer(
            "❌ Не вдалося розпізнати календар на зображенні. "
            "Переконайтеся, що зображення містить календар з кольоровими днями.\n\n"
            "Перевірте логи для деталей помилки."
        )
        return
    
    year = parsed.get("year")
    month = parsed.get("month")
    assignments = parsed.get("assignments", [])
    
    print(f"📅 [IMAGE IMPORT] Parsed calendar data:")
    print(f"📅 [IMAGE IMPORT]   - Year: {year}")
    print(f"📅 [IMAGE IMPORT]   - Month: {month}")
    print(f"📅 [IMAGE IMPORT]   - Assignments count: {len(assignments)}")
    print(f"📅 [IMAGE IMPORT]   - Full parsed data: {parsed}")
    
    if not year or not month:
        print(f"❌ [IMAGE IMPORT] Missing year or month: year={year}, month={month}")
        print(f"❌ [IMAGE IMPORT] Full parsed response: {parsed}")
        await message.answer("❌ Не вдалося визначити рік або місяць з зображення.")
        return
    
    # Only correct year if it's clearly wrong (much older than current year)
    # Trust Gemini's parsing - only fix obvious errors
    current_date = date.today()
    current_year = current_date.year
    current_month = current_date.month
    
    logger.info(f"[IMAGE IMPORT] Current date: {current_date} (year={current_year}, month={current_month})")
    
    # Only correct if year is more than 1 year in the past (likely a misread)
    # Don't automatically assume December = next year - trust Gemini's parsing
    if year < current_year - 1:
        # Year is more than 1 year old - likely wrong, but be conservative
        # Only correct if it's clearly an old year (e.g., 2023 or earlier when we're in 2024+)
        logger.warning(f"[IMAGE IMPORT] Parsed year {year} is more than 1 year in the past. Trusting Gemini's parsing unless clearly wrong.")
        # Don't auto-correct - the year might be correct for historical imports
    
    if not assignments:
        print(f"⚠️ [IMAGE IMPORT] No assignments found in parsed calendar")
        print(f"⚠️ [IMAGE IMPORT] Full parsed response: {parsed}")
        await message.answer(
            f"⚠️ Календарь розпізнано ({month}/{year}), але не знайдено призначень. "
            "Можливо, всі дні порожні або кольори не відповідають користувачам."
        )
        return
    
    print(f"📋 [IMAGE IMPORT] Processing {len(assignments)} assignments...")
    
    # Apply assignments to database
    executed = []
    failed = []
    async with async_session_maker() as session:
        for idx, assignment in enumerate(assignments, 1):
            try:
                print(f"📋 [IMAGE IMPORT] Processing assignment {idx}/{len(assignments)}: {assignment}")
                date_str = assignment.get("date")
                user_names = assignment.get("user_names", [])
                user_ids = assignment.get("user_ids", [])
                color = assignment.get("color")
                
                print(f"📋 [IMAGE IMPORT]   Date: {date_str}")
                print(f"📋 [IMAGE IMPORT]   User names: {user_names}")
                print(f"📋 [IMAGE IMPORT]   User IDs (from parsing): {user_ids}")
                print(f"📋 [IMAGE IMPORT]   Color: {color}")
                
                if not date_str:
                    print(f"⚠️ [IMAGE IMPORT]   Assignment missing date: {assignment}")
                    failed.append(f"⚠️ Пропущено (немає дати): {assignment.get('user_names', ['Unknown'])}")
                    continue
                
                try:
                    shift_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                    print(f"📋 [IMAGE IMPORT]   Parsed date: {shift_date}")
                except ValueError as date_error:
                    print(f"❌ [IMAGE IMPORT]   Invalid date format '{date_str}': {date_error}")
                    failed.append(f"❌ Невірна дата: {date_str}")
                    continue
                
                # Match user names to user IDs if IDs not provided
                if not user_ids and user_names:
                    print(f"📋 [IMAGE IMPORT]   Matching user names to IDs...")
                    matched_ids = []
                    for name in user_names:
                        matched = False
                        for user in users:
                            if user.name == name or user.name.lower() == name.lower():
                                matched_ids.append(user.user_id)
                                matched = True
                                print(f"📋 [IMAGE IMPORT]     Matched '{name}' -> ID {user.user_id}")
                                break
                        if not matched:
                            print(f"⚠️ [IMAGE IMPORT]     User name '{name}' not found in users list")
                    user_ids = matched_ids
                    print(f"📋 [IMAGE IMPORT]   Matched user IDs: {user_ids}")
                
                if user_ids:
                    print(f"📋 [IMAGE IMPORT]   Creating/updating shift for {shift_date} with user IDs: {user_ids}")
                    await create_or_update_shift(session, shift_date, user_ids)
                    executed.append(f"✅ {date_str}: {', '.join(user_names)}")
                    print(f"✅ [IMAGE IMPORT]   Successfully imported shift for {date_str}: {user_names} (IDs: {user_ids})")
                else:
                    print(f"⚠️ [IMAGE IMPORT]   No user IDs matched for {date_str}: {user_names}")
                    failed.append(f"⚠️ {date_str}: не знайдено користувачів ({', '.join(user_names)})")
            except Exception as e:
                import traceback
                print(f"❌ [IMAGE IMPORT]   Error processing assignment {assignment}: {e}")
                print(f"❌ [IMAGE IMPORT]   Traceback: {traceback.format_exc()}")
                failed.append(f"❌ Помилка для {assignment.get('date', 'unknown')}: {str(e)}")
    
    if executed:
        summary = "\n".join(executed[:20])  # Limit to first 20
        if len(executed) > 20:
            summary += f"\n... та ще {len(executed) - 20} призначень"
        
        response_text = f"✅ Календарь імпортовано для {month}/{year}:\n\n{summary}"
        
        if failed:
            response_text += f"\n\n⚠️ Помилки ({len(failed)}):\n" + "\n".join(failed[:10])
            if len(failed) > 10:
                response_text += f"\n... та ще {len(failed) - 10} помилок"
        
        await message.answer(response_text)
        print(f"✅ Successfully imported {len(executed)} shifts, {len(failed)} failed")
    else:
        error_msg = "⚠️ Не вдалося імпортувати жодних призначень."
        if failed:
            error_msg += f"\n\nПомилки:\n" + "\n".join(failed[:10])
        await message.answer(error_msg)
        print(f"❌ Failed to import any shifts. Errors: {len(failed)}")


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
    """Handle user request - fully NLP powered"""
    text = message.text
    
    # Parse with Gemini
    parsed_intent = await gemini_service.parse_user_request(text, users_list)
    
    if not parsed_intent:
        # Fallback response if parsing completely fails - be very explainative
        await message.answer(
            "Привіт! 👋 Я бот для управління змінами в кав'ярні.\n\n"
            "Я розумію повідомлення природною мовою та можу допомогти з:\n\n"
            "📅 <b>Перегляд календаря:</b>\n"
            "• /calendar - показати календар на поточний місяць\n"
            "• /history - переглянути минулі місяці\n\n"
            "💬 <b>Запити природною мовою:</b>\n"
            "• \"Які зміни у мене наступного тижня?\"\n"
            "• \"Можу я помінятися зміною 20 липня?\"\n"
            "• \"Покажи мені календар на липень\"\n\n"
            "📝 <b>Запити на зміну:</b>\n"
            "Просто напишіть, що ви хочете змінити, і адміністратори отримають ваш запит.\n\n"
            "Використайте /help для повного списку команд або просто напишіть мені своє питання!"
        )
        return
    
    message_type = parsed_intent.get("message_type", "unclear")
    response_text = parsed_intent.get("response")
    
    # Handle different message types - always use explainative responses
    if message_type == "greeting":
        # Direct response for greetings - use Gemini's response or detailed fallback
        if response_text:
            await message.answer(response_text, parse_mode="HTML")
        else:
            await message.answer(
                "Привіт! 👋 Я бот для управління змінами в кав'ярні.\n\n"
                "<b>Що я можу зробити:</b>\n"
                "• Показати календар змін: /calendar\n"
                "• Показати історію: /history\n"
                "• Відповісти на питання про зміни природною мовою\n"
                "• Прийняти ваш запит на зміну зміни\n\n"
                "Просто напишіть мені своє питання або використайте /help для повного списку команд!",
                parse_mode="HTML"
            )
        return
    
    elif message_type == "general":
        # Direct response for general questions - use Gemini's response or detailed fallback
        if response_text:
            await message.answer(response_text, parse_mode="HTML")
        else:
            await message.answer(
                "Я допоможу вам з управлінням змінами! 📅\n\n"
                "<b>Доступні можливості:</b>\n"
                "• /calendar - переглянути календар змін на поточний місяць\n"
                "• /history - переглянути минулі місяці\n"
                "• Надішліть повідомлення природною мовою для запитів про зміни\n\n"
                "<b>Приклади запитів:</b>\n"
                "• \"Які зміни у мене наступного тижня?\"\n"
                "• \"Покажи календар на липень\"\n"
                "• \"Можу я помінятися зміною?\"\n\n"
                "Що саме вас цікавить?",
                parse_mode="HTML"
            )
        return
    
    elif message_type == "unclear":
        # Helpful response for unclear messages - use Gemini's response or detailed fallback
        if response_text:
            await message.answer(response_text, parse_mode="HTML")
        else:
            await message.answer(
                "Не зовсім зрозумів ваш запит. 😅\n\n"
                "<b>Ось що я можу зробити:</b>\n\n"
                "📅 <b>Перегляд календаря:</b>\n"
                "• /calendar - календар на поточний місяць\n"
                "• /history - минулі місяці\n\n"
                "💬 <b>Запити природною мовою:</b>\n"
                "• \"Які зміни у мене наступного тижня?\"\n"
                "• \"Покажи мені календар на липень\"\n"
                "• \"Хто працює 15 липня?\"\n\n"
                "📝 <b>Запити на зміну:</b>\n"
                "• \"Можу я помінятися зміною 20 липня?\"\n"
                "• \"Зніми мене зі зміни 25 липня\"\n\n"
                "Спробуйте сформулювати інакше або використайте /help для повної довідки.",
                parse_mode="HTML"
            )
        return
    
    elif message_type == "shift_request":
        # Handle shift-related requests - create request and notify admins
        action = parsed_intent.get("action")
        dates = parsed_intent.get("dates", [])
        
        # If it's just a query (no action needed), respond directly with explanation
        if action == "query" and not dates:
            if response_text:
                await message.answer(response_text, parse_mode="HTML")
            else:
                await message.answer(
                    "Для перегляду календаря змін використайте:\n\n"
                    "• /calendar - показати календар на поточний місяць\n"
                    "• /history - переглянути минулі місяці\n\n"
                    "Або запитайте конкретно, наприклад:\n"
                    "• \"Покажи мені календар на липень\"\n"
                    "• \"Які зміни у мене наступного тижня?\"",
                    parse_mode="HTML"
                )
            return
        
        # Create request in database for actual shift changes
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
        
        # Provide explainative response about what happened
        if response_text:
            await message.answer(
                f"{response_text}\n\n"
                "✅ Ваш запит також було передано адміністраторам для розгляду. "
                "Вони отримають повідомлення та зможуть виконати ваш запит найближчим часом.",
                parse_mode="HTML"
            )
        else:
            summary = parsed_intent.get("summary", "ваш запит")
            await message.answer(
                f"Зрозумів ваш запит: {summary}\n\n"
                "✅ Ваш запит отримано та передано адміністраторам для розгляду.\n\n"
                "Адміністратори отримають повідомлення про ваш запит та зможуть виконати його найближчим часом.\n\n"
                "Якщо потрібно переглянути календар, використайте /calendar",
                parse_mode="HTML"
            )
    else:
        # Fallback for unknown types - be explainative
        if response_text:
            await message.answer(response_text, parse_mode="HTML")
        else:
            await message.answer(
                "Дякую за повідомлення! 📝\n\n"
                "Якщо це запит про зміни, він буде передано адміністраторам для розгляду.\n\n"
                "Для перегляду календаря використайте /calendar або /history.\n"
                "Для повної довідки - /help",
                parse_mode="HTML"
            )


async def handle_admin_nlp_command(
    message: Message,
    users_list: List[Dict[str, Any]],
    users_dict: Dict[int, Any]
):
    """Handle admin natural language command - execute directly"""
    text = message.text
    
    # Check if it's a user management command - be more flexible
    text_lower = text.lower()
    user_management_keywords = [
        "додай користувача", "add user", "створи користувача", 
        "edit user", "редагуй користувача", "зміни користувача",
        "додати користувача", "створити користувача",
        "зміни колір", "change color", "змінити колір", "set color",
        "зміни ім'я", "change name", "змінити ім'я", "set name",
        "колір", "color", "ім'я", "name", "користувач", "user"
    ]
    # Also check if it mentions a user name/ID without dates
    has_user_mention = any(keyword in text_lower for keyword in ["користувач", "user", "ім'я", "name", "колір", "color"])
    has_date_mention = any(keyword in text_lower for keyword in ["дата", "date", "липня", "серпня", "вересня", "жовтня", "листопада", "грудня", 
                                                                  "січня", "лютого", "березня", "квітня", "травня", "червня",
                                                                  "завтра", "сьогодні", "післязавтра", "tomorrow", "today"])
    
    # If it's clearly user management (has user keywords but no dates), route there
    if has_user_mention and not has_date_mention:
        await handle_user_management_nlp(message, users_list, users_dict)
        return
    
    # Also check explicit user management keywords
    if any(keyword in text_lower for keyword in user_management_keywords):
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
                "user_names": [
                    users_dict[uid].name if uid in users_dict else f"User {uid}"
                    for uid in s.user_ids
                ]
            }
            for s in shifts
        ]
    
    # Parse with Gemini
    parsed = await gemini_service.parse_admin_command(text, users_list, current_shifts)
    
    if not parsed:
        await message.answer(
            "❌ Не вдалося обробити команду.\n\n"
            "<b>Як адміністратор, ви можете:</b>\n\n"
            "📅 <b>Управління змінами:</b>\n"
            "• \"Призначти Івана на 15 липня\"\n"
            "• \"Зніми Марію зі зміни 20 липня\"\n"
            "• \"Очистити 25 липня\"\n"
            "• \"Поміняти зміни 15 і 20 липня\"\n\n"
            "👥 <b>Управління користувачами:</b>\n"
            "• \"Додай користувача 123456789 з ім'ям Іван\"\n"
            "• \"Зміни колір користувача 123456789 на #FF0000\"\n"
            "• \"Зміни ім'я користувача 123456789 на Марія\"\n\n"
            "📋 <b>Команди:</b>\n"
            "• /listusers - список користувачів\n"
            "• /calendar - календар\n"
            "• /help - повна довідка\n\n"
            "Спробуйте сформулювати команду інакше або використайте команди з /help.",
            parse_mode="HTML"
        )
        return
    
    if parsed.get("confidence", 0) < 0.7:
        await message.answer(
            f"⚠️ Низька впевненість у розпізнаванні ({parsed.get('confidence', 0):.0%}).\n\n"
            "<b>Щоб покращити розпізнавання, будьте більш конкретними:</b>\n\n"
            "• Вказуйте повні дати: \"15 липня 2025\" або \"2025-07-15\"\n"
            "• Вказуйте повні імена користувачів або їх ID\n"
            "• Використовуйте чіткі дії: \"призначити\", \"зняти\", \"очистити\"\n\n"
            "<b>Приклади правильних команд:</b>\n"
            "• \"Призначти користувача Іван на 15 липня 2025\"\n"
            "• \"Зніми користувача 123456789 зі зміни 20 липня\"\n"
            "• \"Очистити зміну на 25 липня\"\n\n"
            "Спробуйте ще раз з більш конкретними даними.",
            parse_mode="HTML"
        )
        return
    
    # Execute the command
    action = parsed.get("action")
    dates = parsed.get("dates", [])
    user_ids = parsed.get("user_ids", [])
    
    if not dates or not user_ids:
        await message.answer(
            "❌ Не вдалося визначити дати або користувачів.\n\n"
            "<b>Що потрібно для виконання команди:</b>\n\n"
            "📅 <b>Дата:</b> Вкажіть конкретну дату\n"
            "• \"15 липня 2025\"\n"
            "• \"2025-07-15\"\n"
            "• \"завтра\" (якщо це сьогодні)\n\n"
            "👥 <b>Користувач:</b> Вкажіть ім'я або ID\n"
            "• \"Іван\" (якщо є користувач з таким ім'ям)\n"
            "• \"123456789\" (ID користувача)\n\n"
            "<b>Приклади правильних команд:</b>\n"
            "• \"Призначти користувача Іван на 15 липня 2025\"\n"
            "• \"Зніми користувача 123456789 зі зміни 20 липня\"\n"
            "• \"Призначти на 2025-07-15 користувача з ID 123456789\"\n\n"
            "Спробуйте ще раз з повною інформацією.",
            parse_mode="HTML"
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
    
    print(f"🤖 Processing user management command: {text}")
    
    # Parse with Gemini
    parsed = await gemini_service.parse_user_management_command(text, users_list)
    
    if not parsed:
        print(f"❌ Gemini returned None for command: {text}")
        await message.answer(
            "❌ Не вдалося обробити команду управління користувачами.\n\n"
            "<b>Як адміністратор, ви можете управляти користувачами:</b>\n\n"
            "➕ <b>Додавання користувача:</b>\n"
            "• \"Додай користувача 123456789 з ім'ям Іван\"\n"
            "• \"Створи користувача з ID 123456789, ім'я Марія, колір #FF0000\"\n"
            "• \"Додай нового користувача: ID 123456789, ім'я Олександр\"\n\n"
            "✏️ <b>Редагування користувача:</b>\n"
            "• \"Зміни ім'я користувача 123456789 на Петро\"\n"
            "• \"Зміни колір користувача 123456789 на синій\"\n"
            "• \"Оновити користувача 123456789: ім'я Анна, колір #00FF00\"\n\n"
            "📋 <b>Команди:</b>\n"
            "• /adduser &lt;user_id&gt; &lt;name&gt; [color] - додати користувача\n"
            "• /edituser &lt;user_id&gt; &lt;changes&gt; - редагувати користувача\n"
            "• /listusers - список всіх користувачів\n"
            "• /setname &lt;user_id&gt; &lt;name&gt; - змінити ім'я\n"
            "• /setcolor &lt;user_id&gt; &lt;color&gt; - змінити колір\n\n"
            "Спробуйте сформулювати команду інакше або використайте команди з /help.",
            parse_mode="HTML"
        )
        return
    
    # Lower confidence threshold - be more lenient
    if parsed.get("confidence", 0) < 0.5:
        await message.answer(
            f"⚠️ Не зовсім зрозумів команду (впевненість: {parsed.get('confidence', 0):.0%}).\n\n"
            "<b>Спробуйте один з варіантів:</b>\n\n"
            "👤 <b>Додавання користувача:</b>\n"
            "• \"Додай користувача 123456789 з ім'ям Іван\"\n"
            "• \"Створи користувача Іван, ID 123456789\"\n\n"
            "✏️ <b>Редагування користувача:</b>\n"
            "• \"Зміни колір Діана на синій\"\n"
            "• \"Зміни ім'я користувача 123456789 на Петро\"\n"
            "• \"Діана синій\" (якщо контекст зрозумілий)\n\n"
            "Або використайте команди: /setcolor, /setname, /adduser",
            parse_mode="HTML"
        )
        return
    
    action = parsed.get("action")
    user_id_raw = parsed.get("user_id")
    name = parsed.get("name")
    color = parsed.get("color")
    
    # Convert user_id to int if it's a string or number
    user_id = None
    if user_id_raw is not None:
        try:
            if isinstance(user_id_raw, str):
                # Remove any non-digit characters and convert
                user_id = int(''.join(filter(str.isdigit, user_id_raw)))
            elif isinstance(user_id_raw, (int, float)):
                user_id = int(user_id_raw)
            else:
                user_id = None
        except (ValueError, TypeError):
            user_id = None
            print(f"⚠️ Could not convert user_id '{user_id_raw}' to integer")
    
    async with async_session_maker() as session:
        if action in ["add", "create"]:
            # Add new user
            if not name:
                await message.answer("❌ Не вдалося визначити ім'я користувача.")
                return
            
            # If user_id not provided, generate a negative placeholder ID
            from bot.database.operations import get_next_negative_user_id
            if not user_id:
                user_id = await get_next_negative_user_id(session)
            
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
            
            id_note = f" (автоматично згенерований ID: {user_id})" if user_id < 0 else f" (ID: {user_id})"
            await message.answer(
                f"✅ Користувач {user.name}{id_note} доданий.\n"
                f"Колір: {color_code}"
            )
        
        elif action in ["edit", "update"]:
            # Edit existing user
            if not user_id:
                await message.answer(
                    "❌ Не вдалося визначити user_id для редагування.\n\n"
                    f"<b>Розпізнано:</b>\n"
                    f"• Дія: {action}\n"
                    f"• Ім'я: {name or 'не вказано'}\n"
                    f"• User ID: {user_id_raw or 'не вказано'}",
                    parse_mode="HTML"
                )
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
                print(f"🎨 Parsing color: '{color}'")
                color_code = parse_color(color)
                print(f"🎨 Parsed color result: {color_code}")
                if color_code:
                    updates["color_code"] = color_code
                else:
                    print(f"⚠️ Failed to parse color '{color}' - color not updated")
                    await message.answer(
                        f"⚠️ Не вдалося розпізнати колір '{color}'. "
                        f"Доступні кольори: жовтий, рожевий, голубий, фіолетовий, зелений, оранжевий, синій, або hex код (наприклад, #00CED1)."
                    )
                    return
            
            if updates:
                print(f"📝 Updating user {user_id} with: {updates}")
                await update_user(session, user_id, **updates)
                updated_user = await get_user(session, user_id)
                response_lines = [f"✅ Користувач {updated_user.name} (ID: {user_id}) оновлено."]
                if "name" in updates:
                    response_lines.append(f"  Ім'я: {updates['name']}")
                if "color_code" in updates:
                    response_lines.append(f"  Колір: {updates['color_code']}")
                await message.answer("\n".join(response_lines))
            else:
                await message.answer("⚠️ Не вказано полів для оновлення.")
        
        else:
            await message.answer(f"❌ Невідома дія: {action}")

