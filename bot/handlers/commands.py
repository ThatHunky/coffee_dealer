"""Command handlers"""

from datetime import date
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command

from bot.database.operations import (
    get_user, create_user, update_user, get_all_users,
    async_session_maker
)
from bot.services.gemini import gemini_service
from bot.services.calendar import (
    build_calendar_keyboard, 
    get_calendar_text,
    generate_calendar_image,
    build_calendar_image_keyboard,
    get_month_name_ukrainian
)
from bot.utils.colors import parse_color, assign_color_to_user, get_color_emoji
from bot.middleware.permissions import is_admin, ADMIN_IDS

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message):
    """Handle /start command"""
    user_id = message.from_user.id
    username = message.from_user.username
    full_name = message.from_user.full_name or f"User {user_id}"
    
    async with async_session_maker() as session:
        user = await get_user(session, user_id)
        
        if not user:
            # Create user if doesn't exist
            is_admin_user = user_id in ADMIN_IDS
            await create_user(
                session,
                user_id=user_id,
                name=full_name,
                username=username,
                is_admin=is_admin_user,
                is_allowed=is_admin_user  # Admins are auto-allowed
            )
            welcome_text = "👋 Вітаємо! Ви зареєстровані в системі."
            if is_admin_user:
                welcome_text += "\n🔑 Ви маєте права адміністратора."
        else:
            welcome_text = f"👋 Вітаємо, {user.name}!"
            if user.is_admin:
                welcome_text += "\n🔑 Ви маєте права адміністратора."
        
        if not user or not user.is_allowed:
            if not is_admin_user:
                welcome_text += "\n⚠️ Очікуйте дозволу від адміністратора для використання бота."
    
    await message.answer(welcome_text)


@router.message(Command("calendar"))
async def cmd_calendar(message: Message):
    """Handle /calendar command"""
    today = date.today()
    # Generate calendar image
    image = await generate_calendar_image(today.year, today.month)
    keyboard = build_calendar_image_keyboard(today.year, today.month)
    text = get_calendar_text(today.year, today.month)
    
    await message.answer_photo(image, caption=text, reply_markup=keyboard)


@router.message(Command("history"))
async def cmd_history(message: Message):
    """Handle /history command"""
    args = message.text.split()[1:] if message.text else []
    
    if len(args) >= 2:
        try:
            year = int(args[0])
            month = int(args[1])
            if month < 1 or month > 12:
                raise ValueError
        except ValueError:
            await message.answer("❌ Невірний формат. Використовуйте: /history [рік] [місяць]")
            return
    else:
        # Default to previous month
        today = date.today()
        month = today.month - 1
        year = today.year
        if month < 1:
            month = 12
            year -= 1
    
    # Generate calendar image for history
    image = await generate_calendar_image(year, month, is_history=True)
    keyboard = build_calendar_image_keyboard(year, month, is_history=True)
    text = get_calendar_text(year, month, is_history=True)
    
    await message.answer_photo(image, caption=text, reply_markup=keyboard)


@router.message(Command("allow"))
async def cmd_allow(message: Message):
    """Handle /allow command (admin only)"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Тільки адміністратори можуть використовувати цю команду.")
        return
    
    args = message.text.split()[1:] if message.text else []
    if not args:
        await message.answer("❌ Використовуйте: /allow &lt;user_id&gt; або /allow @username")
        return
    
    identifier = args[0].strip()
    
    # Try to parse as user ID
    user_id = None
    if identifier.startswith("@"):
        # Username - need to get from message entities or ask user to provide ID
        await message.answer(
            "❌ Для дозволу за username, будь ласка, надайте user_id. "
            "Або перешліть повідомлення від користувача."
        )
        return
    else:
        try:
            user_id = int(identifier)
        except ValueError:
            await message.answer("❌ Невірний формат. Використовуйте: /allow &lt;user_id&gt;")
            return
    
    async with async_session_maker() as session:
        user = await get_user(session, user_id)
        if not user:
            await message.answer(f"❌ Користувач з ID {user_id} не знайдений.")
            return
        
        await update_user(session, user_id, is_allowed=True)
        await message.answer(f"✅ Користувач {user.name} (ID: {user_id}) тепер має доступ до бота.")


@router.message(Command("adduser"))
async def cmd_adduser(message: Message):
    """Handle /adduser command (admin only)"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Тільки адміністратори можуть використовувати цю команду.")
        return
    
    args = message.text.split()[1:] if message.text else []
    if len(args) < 1:
        await message.answer("❌ Використовуйте: /adduser &lt;name&gt; [user_id] [color]\n"
                           "або: /adduser &lt;user_id&gt; &lt;name&gt; [color]\n\n"
                           "Якщо user_id не вказано, буде згенеровано автоматично.")
        return
    
    # Parse arguments - support both formats:
    # /adduser name [user_id] [color]  OR  /adduser user_id name [color]
    name = None
    user_id = None
    color = None
    
    # Try to parse first argument as user_id (if it's numeric)
    try:
        potential_id = int(args[0])
        # If first arg is numeric and we have at least 2 args, treat it as: user_id name [color]
        if len(args) >= 2:
            user_id = potential_id
            name = args[1]
            color = args[2] if len(args) > 2 else None
        else:
            # Only one numeric arg - treat as name
            name = args[0]
            color = args[1] if len(args) > 1 else None
    except ValueError:
        # First arg is not numeric - treat as: name [user_id] [color]
        name = args[0]
        if len(args) > 1:
            try:
                user_id = int(args[1])
                color = args[2] if len(args) > 2 else None
            except ValueError:
                # Second arg is not numeric either - treat as color
                color = args[1]
    
    if not name:
        await message.answer("❌ Не вказано ім'я користувача.")
        return
    
    async with async_session_maker() as session:
        from bot.database.operations import get_next_negative_user_id
        
        # Generate negative user_id if not provided
        if user_id is None:
            user_id = await get_next_negative_user_id(session)
        
        existing_user = await get_user(session, user_id)
        if existing_user:
            await message.answer(f"❌ Користувач з ID {user_id} вже існує.")
            return
        
        # Parse color if provided
        color_code = None
        if color:
            color_code = parse_color(color)
            if not color_code:
                await message.answer(f"⚠️ Невірний колір '{color}', користувач створений без кольору.")
        
        # Assign default color if not provided
        if not color_code:
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
            f"Колір: {color_code or 'не встановлено'}"
        )


@router.message(Command("setcolor"))
async def cmd_setcolor(message: Message):
    """Handle /setcolor command (admin only)"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Тільки адміністратори можуть використовувати цю команду.")
        return
    
    args = message.text.split()[1:] if message.text else []
    if len(args) < 2:
        await message.answer("❌ Використовуйте: /setcolor &lt;user_id&gt; &lt;color&gt;")
        return
    
    try:
        user_id = int(args[0])
    except ValueError:
        await message.answer("❌ Невірний user_id.")
        return
    
    color_input = args[1]
    color_code = parse_color(color_input)
    
    if not color_code:
        await message.answer(f"❌ Невірний колір: {color_input}")
        return
    
    async with async_session_maker() as session:
        user = await update_user(session, user_id, color_code=color_code)
        if not user:
            await message.answer(f"❌ Користувач з ID {user_id} не знайдений.")
            return
        
        await message.answer(f"✅ Колір користувача {user.name} змінено на {color_code}.")


@router.message(Command("setname"))
async def cmd_setname(message: Message):
    """Handle /setname command (admin only)"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Тільки адміністратори можуть використовувати цю команду.")
        return
    
    args = message.text.split()[1:] if message.text else []
    if len(args) < 2:
        await message.answer("❌ Використовуйте: /setname &lt;user_id&gt; &lt;name&gt;")
        return
    
    try:
        user_id = int(args[0])
    except ValueError:
        await message.answer("❌ Невірний user_id.")
        return
    
    name = " ".join(args[1:])
    
    async with async_session_maker() as session:
        user = await update_user(session, user_id, name=name)
        if not user:
            await message.answer(f"❌ Користувач з ID {user_id} не знайдений.")
            return
        
        await message.answer(f"✅ Ім'я користувача змінено на {user.name}.")


@router.message(Command("listusers"))
async def cmd_listusers(message: Message):
    """Handle /listusers command (admin only)"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Тільки адміністратори можуть використовувати цю команду.")
        return
    
    # Check if user wants to see hidden users
    args = message.text.split()[1:] if message.text else []
    include_hidden = "hidden" in args or "all" in args
    
    async with async_session_maker() as session:
        users = await get_all_users(session, include_hidden=include_hidden)
    
    if not users:
        await message.answer("📋 Користувачі не знайдені.")
        return
    
    text = "📋 Список користувачів"
    if include_hidden:
        text += " (включно з прихованими)"
    text += ":\n\n"
    
    for user in users:
        emoji = get_color_emoji(user.color_code) if user.color_code else "⚪"
        admin_badge = "🔑" if user.is_admin else ""
        allowed_badge = "✅" if user.is_allowed else "❌"
        hidden_badge = "👁️‍🗨️" if user.is_hidden else ""
        text += f"{emoji} {user.name} (ID: {user.user_id})"
        if user.is_hidden:
            text += " [ПРИХОВАНО]"
        text += "\n"
        text += f"   Колір: {user.color_code or 'не встановлено'}\n"
        text += f"   {admin_badge} Адмін: {'Так' if user.is_admin else 'Ні'}\n"
        text += f"   {allowed_badge} Дозвіл: {'Так' if user.is_allowed else 'Ні'}\n"
        if user.is_hidden:
            text += f"   {hidden_badge} Приховано: Так\n"
        text += "\n"
    
    await message.answer(text)


@router.message(Command("users"))
async def cmd_users(message: Message):
    """Handle /users command (alias for /listusers)"""
    await cmd_listusers(message)


@router.message(Command("hideuser"))
async def cmd_hideuser(message: Message):
    """Handle /hideuser command (admin only) - hide a user"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Тільки адміністратори можуть використовувати цю команду.")
        return
    
    args = message.text.split()[1:] if message.text else []
    if len(args) < 1:
        await message.answer("❌ Використовуйте: /hideuser &lt;user_id&gt;")
        return
    
    try:
        user_id = int(args[0])
    except ValueError:
        await message.answer("❌ Невірний user_id.")
        return
    
    async with async_session_maker() as session:
        user = await update_user(session, user_id, is_hidden=True)
        if not user:
            await message.answer(f"❌ Користувач з ID {user_id} не знайдений.")
            return
        
        await message.answer(f"✅ Користувач {user.name} (ID: {user_id}) тепер прихований.")


@router.message(Command("showuser"))
async def cmd_showuser(message: Message):
    """Handle /showuser command (admin only) - show a hidden user"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Тільки адміністратори можуть використовувати цю команду.")
        return
    
    args = message.text.split()[1:] if message.text else []
    if len(args) < 1:
        await message.answer("❌ Використовуйте: /showuser &lt;user_id&gt;")
        return
    
    try:
        user_id = int(args[0])
    except ValueError:
        await message.answer("❌ Невірний user_id.")
        return
    
    async with async_session_maker() as session:
        user = await update_user(session, user_id, is_hidden=False)
        if not user:
            await message.answer(f"❌ Користувач з ID {user_id} не знайдений.")
            return
        
        await message.answer(f"✅ Користувач {user.name} (ID: {user_id}) тепер видимий.")


@router.message(Command("edituser"))
async def cmd_edituser(message: Message):
    """Handle /edituser command (admin only) - edit user with natural language"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Тільки адміністратори можуть використовувати цю команду.")
        return
    
    args = message.text.split()[1:] if message.text else []
    if not args:
        await message.answer(
            "❌ Використовуйте: /edituser &lt;user_id&gt; &lt;зміни&gt;\n"
            "Або надішліть повідомлення природною мовою, наприклад:\n"
            "• \"Зміни ім'я користувача 123 на Дана\"\n"
            "• \"Встанови колір жовтий для користувача 456\""
        )
        return
    
    # If user_id is provided, treat rest as natural language command
    try:
        user_id = int(args[0])
        command_text = " ".join(args[1:]) if len(args) > 1 else ""
        
        if not command_text:
            await message.answer("❌ Вкажіть, що саме змінити (ім'я, колір, тощо).")
            return
        
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
        
        # Parse with Gemini
        parsed = await gemini_service.parse_user_management_command(
            f"edit user {user_id} {command_text}", users_list
        )
        
        if not parsed or parsed.get("confidence", 0) < 0.7:
            await message.answer("❌ Не вдалося розпізнати команду. Спробуйте уточнити.")
            return
        
        # Apply changes
        user = await get_user(session, user_id)
        if not user:
            await message.answer(f"❌ Користувач з ID {user_id} не знайдений.")
            return
        
        updates = {}
        if parsed.get("name"):
            updates["name"] = parsed["name"]
        if parsed.get("color"):
            color_code = parse_color(parsed["color"])
            if color_code:
                updates["color_code"] = color_code
        
        if updates:
            await update_user(session, user_id, **updates)
            updated_user = await get_user(session, user_id)
            await message.answer(
                f"✅ Користувач {updated_user.name} (ID: {user_id}) оновлено.\n" +
                "\n".join([f"  {k}: {v}" for k, v in updates.items()])
            )
        else:
            await message.answer("⚠️ Не вдалося визначити зміни для застосування.")
            
    except ValueError:
        # If first arg is not a number, treat entire message as natural language
        async with async_session_maker() as session:
            users = await get_all_users(session)
            users_list = [
                {
                    "user_id": u.user_id,
                    "name": u.name,
                    "username": u.username,
                    "color_code": u.color_code
                }
                for u in users
            ]
        
        parsed = await gemini_service.parse_user_management_command(message.text, users_list)
        
        if parsed and parsed.get("confidence", 0) >= 0.7:
            # Handle via user management NLP
            from bot.handlers.messages import handle_user_management_nlp
            users_dict = {u.user_id: u for u in users}
            await handle_user_management_nlp(message, users_list, users_dict)
        else:
            await message.answer("❌ Не вдалося розпізнати команду редагування користувача.")


@router.message(Command("clearmonth"))
async def cmd_clearmonth(message: Message):
    """Handle /clearmonth command (admin only) - clear all shifts for a month"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Тільки адміністратори можуть використовувати цю команду.")
        return
    
    args = message.text.split()[1:] if message.text else []
    
    # Parse year and month from arguments or use current month
    today = date.today()
    if len(args) >= 2:
        try:
            year = int(args[0])
            month = int(args[1])
            if month < 1 or month > 12:
                raise ValueError
        except ValueError:
            await message.answer("❌ Невірний формат. Використовуйте: /clearmonth [рік] [місяць]")
            return
    else:
        year = today.year
        month = today.month
    
    # Get month name in Ukrainian
    month_name = get_month_name_ukrainian(month)
    
    # Get count of shifts in the month
    from bot.database.operations import get_shifts_in_range
    from calendar import monthrange
    
    async with async_session_maker() as session:
        first_day = date(year, month, 1)
        last_day_num = monthrange(year, month)[1]
        last_day = date(year, month, last_day_num)
        shifts = await get_shifts_in_range(session, first_day, last_day)
        shift_count = len(shifts)
    
    # Create confirmation keyboard
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    
    builder = InlineKeyboardBuilder()
    builder.button(
        text="✅ Підтвердити",
        callback_data=f"confirm_clear_month_{year}_{month}"
    )
    builder.button(
        text="❌ Скасувати",
        callback_data=f"cancel_clear_month_{year}_{month}"
    )
    builder.adjust(2)
    
    text = (
        f"⚠️ <b>Підтвердження очищення місяця</b>\n\n"
        f"Ви впевнені, що хочете очистити всі зміни для <b>{month_name} {year}</b>?\n\n"
        f"📊 Знайдено змін: <b>{shift_count}</b>\n\n"
        f"❌ <b>Ця дія незворотна!</b> Всі призначення на цей місяць будуть видалені."
    )
    
    await message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Handle /help command - show all available commands"""
    user_id = message.from_user.id
    is_admin_user = is_admin(user_id)
    
    text = "📚 <b>Доступні команди:</b>\n\n"
    
    # User commands (available to all)
    text += "👤 <b>Команди користувача:</b>\n"
    text += "• <code>/start</code> - Початок роботи з ботом\n"
    text += "• <code>/calendar</code> - Показати календар змін на поточний місяць\n"
    text += "• <code>/history [рік] [місяць]</code> - Переглянути історію змін\n"
    text += "• <code>/help</code> - Показати цю довідку\n\n"
    
    text += "💬 <b>Натуральна мова:</b>\n"
    text += "Ви можете надсилати запити природною мовою, наприклад:\n"
    text += "• \"Чи можу я помінятися зміною 15 липня з Даною?\"\n"
    text += "• \"Признач мене на всі понеділки в липні\"\n\n"
    
    # Admin commands
    if is_admin_user:
        text += "🔑 <b>Команди адміністратора:</b>\n"
        text += "• <code>/allow &lt;user_id&gt;</code> - Дозволити користувачу використовувати бота\n"
        text += "• <code>/adduser &lt;user_id&gt; &lt;ім'я&gt; [колір]</code> - Додати нового користувача\n"
        text += "• <code>/edituser &lt;user_id&gt; &lt;зміни&gt;</code> - Редагувати користувача (NLP)\n"
        text += "• <code>/setcolor &lt;user_id&gt; &lt;колір&gt;</code> - Змінити колір користувача\n"
        text += "• <code>/setname &lt;user_id&gt; &lt;ім'я&gt;</code> - Змінити ім'я користувача\n"
        text += "• <code>/listusers</code> або <code>/users</code> - Список всіх користувачів\n"
        text += "• <code>/hideuser &lt;user_id&gt;</code> - Приховати користувача\n"
        text += "• <code>/showuser &lt;user_id&gt;</code> - Показати прихованого користувача\n"
        text += "• <code>/clearmonth [рік] [місяць]</code> - Очистити всі зміни за місяць\n\n"
        text += "📸 <b>Імпорт календаря:</b>\n"
        text += "• Надішліть зображення календаря - автоматично імпортує призначення\n\n"
        text += "💬 <b>Масові зміни (натуральна мова):</b>\n"
        text += "Адміністратори можуть виконувати масові зміни природною мовою:\n"
        text += "• \"Признач Дана на всі понеділки в липні\"\n"
        text += "• \"Зніми Діану з 15-20 липня\"\n"
    else:
        text += "⚠️ Для доступу до команд адміністратора зверніться до адміністратора.\n"
    
    await message.answer(text, parse_mode="HTML")

