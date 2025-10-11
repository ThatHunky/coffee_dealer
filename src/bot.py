"""Telegram bot handlers and routers."""

from datetime import date
from functools import wraps
from io import BytesIO

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    BotCommand,
    BotCommandScopeAllPrivateChats,
    BotCommandScopeChat,
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)
from dateutil.relativedelta import relativedelta
from loguru import logger

from .config import config
from .image_render import renderer
from .intents import NLCommand, ScheduleFromImage
from .models import Assignment, CombinationColor, UserConfig
from .nlp import parse_utterance
from .repo import repo
from .user_manager import user_manager

# Create router
router = Router()

# In-memory storage for pending schedule imports
# Key: user_id, Value: ScheduleFromImage
pending_schedule_imports: dict[int, "ScheduleFromImage"] = {}


def is_admin(user_id: int) -> bool:
    """Check if user is admin."""
    return user_id in config.ADMIN_IDS


def get_main_keyboard() -> ReplyKeyboardMarkup:
    """Get main keyboard with Ukrainian labels."""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📅 Показати місяць")],
            [KeyboardButton(text="❓ Допомога")],
        ],
        resize_keyboard=True,
    )
    return keyboard


@router.message(CommandStart())
async def cmd_start(message: Message, **kwargs):
    """Handle /start command with user approval check."""
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    from .models import UserApproval

    user_id = message.from_user.id

    # Check if user is approved
    if is_admin(user_id):
        # Admins are always approved
        welcome_text = (
            "👋 Вітаю в боті розкладу Coffee Dealer!\n\n"
            "Я можу показати розклад роботи та допомогти з призначеннями.\n\n"
            "Використовуй кнопки меню або пиши вільною мовою:\n"
            '• "покажи жовтень"\n'
            '• "хто працює 15 числа?"\n'
            '• "постав Діану на 5 жовтня"\n'
            "\n✅ У тебе є права адміністратора."
        )
        await message.answer(welcome_text, reply_markup=get_main_keyboard())
        return

    # Check approval status
    approval = repo.get_user_approval(user_id)

    if approval is None:
        # New user - create approval request
        approval = UserApproval(
            telegram_id=user_id,
            telegram_username=message.from_user.username or "",
            telegram_first_name=message.from_user.first_name or "",
            telegram_last_name=message.from_user.last_name or "",
            full_name=message.from_user.full_name or "Користувач",
        )
        approval = repo.create_user_approval(approval)

        # Notify admins
        await notify_admins_new_user(message.bot, approval)

        await message.answer(
            "👋 Вітаю!\n\n"
            "📬 Ваш запит на доступ до бота відправлено адміністраторам.\n"
            "Очікуйте підтвердження - ви отримаєте повідомлення, коли доступ буде надано.",
            reply_markup=get_main_keyboard(),
        )
        return

    if approval.status == "pending":
        await message.answer(
            "⏳ Ваш запит на доступ очікує розгляду адміністраторами.\n"
            "Будь ласка, зачекайте підтвердження.",
            reply_markup=get_main_keyboard(),
        )
        return

    if approval.status == "denied":
        await message.answer(
            "❌ На жаль, вам було відмовлено в доступі до бота.\n"
            f"Причина: {approval.review_note or 'Не вказано'}",
            reply_markup=get_main_keyboard(),
        )
        return

    # User is approved
    welcome_text = (
        "👋 Вітаю в боті розкладу Coffee Dealer!\n\n"
        "Я можу показати розклад роботи.\n\n"
        "Використовуй кнопки меню або пиши вільною мовою:\n"
        '• "покажи жовтень"\n'
        '• "хто працює 15 числа?"\n'
        "\n✅ У вас є доступ до бота."
    )
    await message.answer(welcome_text, reply_markup=get_main_keyboard())


async def notify_admins_new_user(bot: Bot, approval):
    """Notify admins about new user requesting access."""
    from .models import UserApproval

    text = (
        f"👤 Новий користувач запитує доступ\n\n"
        f"📝 Ім'я: {approval.full_name}\n"
        f"🆔 ID: {approval.telegram_id}\n"
        f"👤 Username: @{approval.telegram_username or 'немає'}\n"
        f"⏰ {approval.requested_at.strftime('%d.%m.%Y %H:%M')}"
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Схвалити",
                    callback_data=f"approve_user_{approval.telegram_id}",
                ),
                InlineKeyboardButton(
                    text="❌ Відхилити",
                    callback_data=f"deny_user_{approval.telegram_id}",
                ),
            ]
        ]
    )

    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text, reply_markup=keyboard)
        except Exception as e:
            logger.error(f"Failed to notify admin {admin_id}: {e}")


def require_approval(handler):
    """Decorator to check if user is approved before executing handler."""

    @wraps(handler)
    async def wrapper(message: Message, *args, **kwargs):
        user_id = message.from_user.id

        if not is_admin(user_id) and not repo.is_user_approved(user_id):
            approval = repo.get_user_approval(user_id)
            if approval and approval.status == "denied":
                await message.answer(
                    "❌ Вам було відмовлено в доступі до бота.",
                    reply_markup=get_main_keyboard(),
                )
            else:
                await message.answer(
                    "⏳ Ваш доступ ще не підтверджено адміністраторами.\n"
                    "Використайте /start щоб надіслати запит.",
                    reply_markup=get_main_keyboard(),
                )
            return

        return await handler(message, *args, **kwargs)

    return wrapper


def require_approval_callback(handler):
    """Decorator to check if user is approved before executing callback handler."""

    @wraps(handler)
    async def wrapper(callback: CallbackQuery, *args, **kwargs):
        user_id = callback.from_user.id

        if not is_admin(user_id) and not repo.is_user_approved(user_id):
            approval = repo.get_user_approval(user_id)
            if approval and approval.status == "denied":
                await callback.answer(
                    "❌ Вам було відмовлено в доступі до бота.",
                    show_alert=True,
                )
            else:
                await callback.answer(
                    "⏳ Ваш доступ ще не підтверджено адміністраторами.\n"
                    "Використайте /start щоб надіслати запит.",
                    show_alert=True,
                )
            return

        return await handler(callback, *args, **kwargs)

    return wrapper


@require_approval
@router.message(Command("help"))
@router.message(F.text == "❓ Допомога")
async def cmd_help(message: Message, **kwargs):
    """Handle /help command."""
    help_text = (
        "📖 Довідка по боту Coffee Dealer\n\n"
        "🔹 Показати календар:\n"
        '• "покажи жовтень"\n'
        '• "розклад на листопад"\n'
        '• "📅 Показати місяць" (кнопка)\n\n'
        "🔹 Дізнатись, хто працює:\n"
        '• "хто працює 15 числа?"\n'
        '• "хто на 10 жовтня?"\n\n'
    )

    if is_admin(message.from_user.id):
        help_text += (
            "🔹 Призначити людей (адмін):\n"
            '• "постав Діану на 5 жовтня"\n'
            '• "Діана і Женя на 15"\n'
            '• "Дана на 20 листопада"\n\n'
            "🔹 Призначення на декілька днів (адмін):\n"
            '• "постав Діану на 25 та 26 жовтня"\n'
            '• "Дана на 10, 15 та 20"\n'
            '• "Женя на 5-10 листопада" (діапазон)\n'
            '• "дану та діану на 7, 8, та 20" (декілька людей)\n\n'
            "🔹 Масове призначення (адмін):\n"
            '• "признач Діану на усі неділі"\n'
            '• "Дана на всі суботи листопада"\n'
            '• "Женя на всі вихідні"\n'
            '• "Діана на всі будні"\n'
            '• "Дана на весь жовтень"\n'
            '• "дану та діану на всі неділі" (декілька людей)\n\n'
            "� Імпорт з зображення (адмін):\n"
            "• Надішліть фото календаря, і бот автоматично розпізнає розклад\n"
            "• Працює з кольоровими календарями (🔵🟣🟢🔴🩷🟡)\n\n"
            "�🛠 Команди адміністратора:\n"
            "• /users — список користувачів\n"
            "• /adduser — додати/оновити користувача\n"
            "• /edituser — редагувати користувача\n"
            "• /removeuser — деактивувати користувача\n"
            "• /activateuser — активувати користувача\n"
            "• /setcombo — встановити колір комбінації\n"
            "• /colors — показати всі кольори\n"
            "• /changes — останні зміни в розкладі\n"
            "• /approvals — переглянути запити на доступ\n\n"
            "💡 При зміні розкладу всі адміни отримують сповіщення.\n"
        )

    await message.answer(help_text, reply_markup=get_main_keyboard())


@require_approval
@router.message(F.text == "📅 Показати місяць")
async def show_current_month(message: Message, **kwargs):
    """Show current month calendar."""
    today = date.today()
    await send_calendar(message, today.year, today.month)


def get_month_navigation_keyboard(year: int, month: int) -> InlineKeyboardMarkup:
    """Get inline keyboard for month navigation with 12-month max history."""
    from babel.dates import format_date

    today = date.today()
    current_date = date(year, month, 1)

    # Calculate 12 months ago from today
    twelve_months_ago = today.replace(day=1) - relativedelta(months=11)

    # Check if we can go back (not more than 12 months)
    can_go_back = current_date > twelve_months_ago

    # Calculate previous and next months
    prev_month = current_date - relativedelta(months=1)
    next_month = current_date + relativedelta(months=1)

    # Build keyboard
    buttons = []

    if can_go_back:
        buttons.append(
            InlineKeyboardButton(
                text="◀️ Попередній",
                callback_data=f"month_{prev_month.year}_{prev_month.month}",
            )
        )
    else:
        # Placeholder to maintain layout
        buttons.append(InlineKeyboardButton(text="⏹️", callback_data="month_limit"))

    # Current month button (no action)
    month_name = format_date(current_date, "LLLL yyyy", locale="uk").capitalize()
    buttons.append(
        InlineKeyboardButton(text=f"📅 {month_name}", callback_data="month_current")
    )

    # Next month button
    buttons.append(
        InlineKeyboardButton(
            text="Наступний ▶️",
            callback_data=f"month_{next_month.year}_{next_month.month}",
        )
    )

    return InlineKeyboardMarkup(inline_keyboard=[buttons])


async def send_calendar(message: Message, year: int, month: int, edit: bool = False):
    """Send calendar image for specified month."""
    try:
        # Render calendar
        logger.info(f"Rendering calendar for {year}-{month:02d}")

        try:
            image_buffer = renderer.render(year, month)
        except Exception as e:
            logger.error(f"Failed to render calendar image: {e}", exc_info=True)
            raise

        # Send as photo
        photo = BufferedInputFile(
            image_buffer.read(), filename=f"calendar_{year}_{month:02d}.png"
        )

        # Get month name in Ukrainian
        from babel.dates import format_date

        month_name = format_date(
            date(year, month, 1), "LLLL yyyy", locale="uk"
        ).capitalize()

        # Get navigation keyboard
        keyboard = get_month_navigation_keyboard(year, month)

        if edit and hasattr(message, "edit_media"):
            # Edit existing message (for callback queries)
            from aiogram.types import InputMediaPhoto

            await message.edit_media(
                media=InputMediaPhoto(
                    media=photo, caption=f"📅 Розклад на {month_name}"
                ),
                reply_markup=keyboard,
            )
            logger.debug("Calendar edited successfully")
        else:
            # Send new message
            await message.answer_photo(
                photo=photo,
                caption=f"📅 Розклад на {month_name}",
                reply_markup=keyboard,
            )
            logger.debug("Calendar sent successfully")
    except Exception as e:
        logger.error(f"Failed to render/send calendar: {e}", exc_info=True)
        error_msg = "❌ Помилка при створенні календаря. Спробуй ще раз."
        if edit and hasattr(message, "answer"):
            await message.answer(error_msg)
        else:
            await message.answer(
                error_msg,
                reply_markup=get_main_keyboard(),
            )


async def handle_show_month(message: Message, cmd: NLCommand):
    """Handle show_month action."""
    today = date.today()
    year = cmd.year or today.year
    month = cmd.month or today.month

    await send_calendar(message, year, month)


async def handle_who_works(message: Message, cmd: NLCommand):
    """Handle who_works action."""
    today = date.today()
    year = cmd.year or today.year
    month = cmd.month or today.month
    day = cmd.day or today.day

    try:
        query_date = date(year, month, day)
        assignment = repo.get_by_day(query_date)

        if assignment and assignment.mask > 0:
            names = assignment.get_people_names()
            names_text = ", ".join(names)
            response = f"👥 {query_date.strftime('%d.%m.%Y')}: працює {names_text}"
            if assignment.note:
                response += f"\n📝 {assignment.note}"
        else:
            response = f"❌ На {query_date.strftime('%d.%m.%Y')} ніхто не призначений."

        await message.answer(response, reply_markup=get_main_keyboard())
    except ValueError as e:
        await message.answer(
            f"❌ Некоректна дата: {e}", reply_markup=get_main_keyboard()
        )


async def handle_assign_days(message: Message, cmd: NLCommand):
    """Handle assign_days action (admin only) - assign to multiple specific days."""
    # Check admin permission
    if not is_admin(message.from_user.id):
        await message.answer(
            "🔒 Лише адміністратори можуть змінювати розклад.",
            reply_markup=get_main_keyboard(),
        )
        return

    today = date.today()
    year = cmd.year or today.year
    month = cmd.month or today.month

    if not cmd.days:
        await message.answer(
            "❌ Не вказано дні для призначення.",
            reply_markup=get_main_keyboard(),
        )
        return

    try:
        from calendar import monthrange

        # Validate all days are within month range
        _, last_day = monthrange(year, month)
        invalid_days = [d for d in cmd.days if d < 1 or d > last_day]

        if invalid_days:
            await message.answer(
                f"❌ Некоректні дні для {month}/{year}: {', '.join(map(str, invalid_days))}",
                reply_markup=get_main_keyboard(),
            )
            return

        # Assign to all specified days
        days_to_assign = []
        for day in cmd.days:
            assign_date = date(year, month, day)
            assignment = Assignment.from_people(
                day=assign_date, people=cmd.people, note=cmd.note
            )
            repo.upsert_with_notification(assignment, message.from_user.id)
            days_to_assign.append(assign_date)

        # Prepare response
        names = cmd.people
        names_text = ", ".join(names)

        from babel.dates import format_date

        month_name = format_date(date(year, month, 1), "LLLL", locale="uk").capitalize()

        days_text = ", ".join(str(d) for d in sorted(cmd.days))

        response = (
            f"✅ Призначення завершено!\n\n"
            f"📅 Дні: {days_text} {month_name}\n"
            f"👥 Призначено: {names_text}\n"
            f"📊 Кількість днів: {len(cmd.days)}"
        )

        await message.answer(response, reply_markup=get_main_keyboard())

        # Show updated calendar
        await send_calendar(message, year, month)

    except ValueError as e:
        await message.answer(
            f"❌ Некоректна дата: {e}", reply_markup=get_main_keyboard()
        )


async def handle_assign_bulk(message: Message, cmd: NLCommand):
    """Handle assign_bulk action (admin only) - assign to multiple days based on pattern."""
    # Check admin permission
    if not is_admin(message.from_user.id):
        await message.answer(
            "🔒 Лише адміністратори можуть змінювати розклад.",
            reply_markup=get_main_keyboard(),
        )
        return

    today = date.today()
    year = cmd.year or today.year
    month = cmd.month or today.month

    if not cmd.pattern:
        await message.answer(
            "❌ Не вказано шаблон для масового призначення.",
            reply_markup=get_main_keyboard(),
        )
        return

    try:
        from calendar import monthrange

        # Get all days in the month
        _, last_day = monthrange(year, month)

        # Determine which days to assign based on pattern
        days_to_assign = []

        for day in range(1, last_day + 1):
            target_date = date(year, month, day)
            weekday = target_date.weekday()  # 0=Monday, 6=Sunday

            if cmd.pattern == "all_sundays" and weekday == 6:
                days_to_assign.append(target_date)
            elif cmd.pattern == "all_saturdays" and weekday == 5:
                days_to_assign.append(target_date)
            elif cmd.pattern == "all_weekends" and weekday in (5, 6):
                days_to_assign.append(target_date)
            elif cmd.pattern == "all_weekdays" and weekday < 5:
                days_to_assign.append(target_date)
            elif cmd.pattern == "whole_month":
                days_to_assign.append(target_date)

        if not days_to_assign:
            await message.answer(
                f"❌ Не знайдено днів для шаблону '{cmd.pattern}' у {month}/{year}.",
                reply_markup=get_main_keyboard(),
            )
            return

        # Assign to all matching days
        assigned_count = 0
        for assign_date in days_to_assign:
            assignment = Assignment.from_people(
                day=assign_date, people=cmd.people, note=cmd.note
            )
            repo.upsert_with_notification(assignment, message.from_user.id)
            assigned_count += 1

        # Prepare pattern name in Ukrainian
        pattern_names = {
            "all_sundays": "всі неділі",
            "all_saturdays": "всі суботи",
            "all_weekends": "всі вихідні",
            "all_weekdays": "всі будні",
            "whole_month": "весь місяць",
        }
        pattern_name = pattern_names.get(cmd.pattern, cmd.pattern)

        # Prepare response
        names = cmd.people
        names_text = ", ".join(names)

        from babel.dates import format_date

        month_name = format_date(
            date(year, month, 1), "LLLL yyyy", locale="uk"
        ).capitalize()

        response = (
            f"✅ Масове призначення завершено!\n\n"
            f"📅 {pattern_name} у {month_name}\n"
            f"👥 Призначено: {names_text}\n"
            f"📊 Кількість днів: {assigned_count}"
        )

        await message.answer(response, reply_markup=get_main_keyboard())

        # Show updated calendar
        await send_calendar(message, year, month)

    except ValueError as e:
        await message.answer(
            f"❌ Некоректна дата: {e}", reply_markup=get_main_keyboard()
        )


async def send_change_notification(bot: Bot, notification):
    """Send change notification to ALL users (admins and non-admins)."""
    from .config import config
    from .user_manager import user_manager

    old_names = user_manager.mask_to_names(notification.old_mask)
    new_names = user_manager.mask_to_names(notification.new_mask)

    old_text = ", ".join(old_names) if old_names else "—"
    new_text = ", ".join(new_names) if new_names else "—"

    notification_text = (
        f"🔔 Зміна в розкладі\n\n"
        f"📅 Дата: {notification.change_date.strftime('%d.%m.%Y')}\n"
        f"👤 Було: {old_text}\n"
        f"👤 Стало: {new_text}\n"
        f"⏰ {notification.changed_at.strftime('%H:%M:%S')}"
    )

    # Get all user IDs to notify (both admins and regular users)
    # You should maintain a list of all subscribed user IDs
    # For now, we'll notify admins + anyone in ALLOWED_USERS if configured
    notify_users = set(config.ADMIN_IDS)

    # Add any configured regular users (you can extend this)
    if hasattr(config, "NOTIFY_USERS"):
        notify_users.update(config.NOTIFY_USERS)

    # Send to all users except the one who made the change
    for user_id in notify_users:
        if user_id != notification.changed_by:
            try:
                await bot.send_message(user_id, notification_text)
            except Exception as e:
                logger.error(f"Failed to notify user {user_id}: {e}")

    # Mark notification as sent
    repo.mark_notification_sent(notification.id)


async def send_request_notification(bot: Bot, request, message: Message):
    """Send change request notification to all admins for approval."""
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    request_text = (
        f"📬 Новий запит на зміну розкладу\n\n"
        f"👤 Від: {request.requested_by_name}\n"
        f"📝 Запит: {request.get_description()}\n"
        f"📅 Місяць: {request.month}/{request.year}\n"
        f"⏰ {request.requested_at.strftime('%d.%m %H:%M')}"
    )

    # Create inline keyboard for approval/denial
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Схвалити", callback_data=f"approve_{request.id}"
                ),
                InlineKeyboardButton(
                    text="❌ Відхилити", callback_data=f"deny_{request.id}"
                ),
            ]
        ]
    )

    # Send to all admins
    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(admin_id, request_text, reply_markup=keyboard)
        except Exception as e:
            logger.error(f"Failed to notify admin {admin_id}: {e}")


async def handle_assign_day(message: Message, cmd: NLCommand):
    """Handle assign_day action - admins can assign directly, users create requests."""
    today = date.today()
    year = cmd.year or today.year
    month = cmd.month or today.month

    if not cmd.day:
        await message.answer(
            "❌ Не вказано день. Спробуй ще раз, наприклад: 'постав Діану на 5 жовтня'",
            reply_markup=get_main_keyboard(),
        )
        return

    try:
        assign_date = date(year, month, cmd.day)

        # Check if user is admin
        if is_admin(message.from_user.id):
            # Admin: apply changes directly
            assignment = Assignment.from_people(
                day=assign_date, people=cmd.people, note=cmd.note
            )

            saved_assignment, notification = repo.upsert_with_notification(
                assignment, message.from_user.id
            )

            if saved_assignment.mask > 0:
                names = saved_assignment.get_people_names()
                names_text = ", ".join(names)
                response = (
                    f"✅ Призначено на {assign_date.strftime('%d.%m.%Y')}: {names_text}"
                )
            else:
                response = (
                    f"✅ Видалено призначення на {assign_date.strftime('%d.%m.%Y')}"
                )

            change_desc = notification.get_change_description()
            response += f"\n📝 {change_desc}"

            await message.answer(response, reply_markup=get_main_keyboard())
            await send_change_notification(message.bot, notification)
            await send_calendar(message, year, month)
        else:
            # Regular user: create change request
            import json

            from .models import ChangeRequest

            request = ChangeRequest(
                request_type="assign_day",
                requested_by=message.from_user.id,
                requested_by_name=message.from_user.full_name or "Користувач",
                days=json.dumps([cmd.day]),
                people=json.dumps(cmd.people),
                year=year,
                month=month,
                note=cmd.note,
            )

            saved_request = repo.create_change_request(request)

            await message.answer(
                f"📬 Запит на зміну відправлено!\n\n"
                f"📅 {assign_date.strftime('%d.%m.%Y')}: {', '.join(cmd.people)}\n\n"
                f"Адміністратор розгляне запит найближчим часом.",
                reply_markup=get_main_keyboard(),
            )

            await send_request_notification(message.bot, saved_request, message)

    except ValueError as e:
        await message.answer(
            f"❌ Некоректна дата: {e}", reply_markup=get_main_keyboard()
        )


async def send_change_notification_to_admins(bot: Bot, notification):
    """Send change notification to all admins."""
    from .user_manager import user_manager

    old_names = user_manager.mask_to_names(notification.old_mask)
    new_names = user_manager.mask_to_names(notification.new_mask)

    old_text = ", ".join(old_names) if old_names else "—"
    new_text = ", ".join(new_names) if new_names else "—"

    notification_text = (
        f"🔔 Зміна в розкладі\n\n"
        f"📅 Дата: {notification.change_date.strftime('%d.%m.%Y')}\n"
        f"👤 Було: {old_text}\n"
        f"👤 Стало: {new_text}\n"
        f"⏰ {notification.changed_at.strftime('%H:%M:%S')}"
    )

    # Send to all admins except the one who made the change
    for admin_id in config.ADMIN_IDS:
        if admin_id != notification.changed_by:
            try:
                await bot.send_message(admin_id, notification_text)
            except Exception as e:
                logger.error(f"Failed to notify admin {admin_id}: {e}")

    # Mark notification as sent
    repo.mark_notification_sent(notification.id)


@router.message(Command("users"))
async def cmd_users(message: Message, **kwargs):
    """List all users (admin only)."""
    try:
        if not message.from_user:
            return

        if not is_admin(message.from_user.id):
            await message.answer("🔒 Команда доступна лише адміністраторам.")
            return

        logger.info(f"Admin {message.from_user.id} listing users")
        users = repo.get_all_users(active_only=False)

        if not users:
            await message.answer("❌ Користувачів не знайдено.")
            return

        text = "👥 Список користувачів:\n\n"
        for user in users:
            status = "✅" if user.is_active else "❌"
            text += f"{status} Позиція {user.bit_position}: {user.name_uk} ({user.name_en})\n"
            text += f"   {user.emoji} Емодзі\n\n"

        await message.answer(text)
        logger.debug(f"Sent {len(users)} users to admin {message.from_user.id}")
    except Exception as e:
        logger.error(f"Error in cmd_users: {e}", exc_info=True)
        await message.answer("❌ Сталася помилка при отриманні списку користувачів.")


@router.message(Command("adduser"))
async def cmd_add_user(message: Message, **kwargs):
    """Add or update a user (admin only)."""
    try:
        if not message.from_user:
            return

        if not is_admin(message.from_user.id):
            await message.answer("🔒 Команда доступна лише адміністраторам.")
            return

        help_text = (
            "📝 Додати/оновити користувача:\n\n"
            "Формат:\n"
            "/adduser <позиція> <ім'я_укр> <ім'я_англ> <емодзі>\n\n"
            "Приклад:\n"
            "/adduser 0 Діана diana 🔵\n\n"
            "Позиція: 0-7 (для бітової маски)\n"
            "Емодзі: будь-який емодзі (напр. 🔵 🟣 🟢)"
        )

        # Parse command
        parts = message.text.split() if message.text else []
        if len(parts) < 5:
            await message.answer(help_text)
            return

        try:
            bit_position = int(parts[1])
            name_uk = parts[2]
            name_en = parts[3]
            emoji = parts[4]

            logger.info(
                f"Admin {message.from_user.id} adding/updating user: {name_en} at position {bit_position}"
            )

            if bit_position < 0 or bit_position > 7:
                await message.answer("❌ Позиція має бути від 0 до 7")
                return

            user = user_manager.update_user(bit_position, name_uk, name_en, emoji)

            await message.answer(
                f"✅ Користувача оновлено:\n"
                f"Позиція: {user.bit_position}\n"
                f"Ім'я: {user.name_uk} ({user.name_en})\n"
                f"Емодзі: {user.emoji}"
            )
            logger.info(
                f"User {name_en} successfully updated by admin {message.from_user.id}"
            )

        except ValueError as e:
            logger.error(f"ValueError in cmd_add_user: {e}")
            await message.answer(f"❌ Помилка: {e}\n\n{help_text}")
    except Exception as e:
        logger.error(f"Error in cmd_add_user: {e}", exc_info=True)
        await message.answer("❌ Сталася помилка при додаванні користувача.")


@router.message(Command("setcombo"))
async def cmd_set_combo(message: Message, **kwargs):
    """Set combination color (admin only)."""
    if not is_admin(message.from_user.id):
        await message.answer("🔒 Команда доступна лише адміністраторам.")
        return

    help_text = (
        "🎨 Встановити емодзі для комбінації:\n\n"
        "Формат:\n"
        "/setcombo <маска> <емодзі> <назва>\n\n"
        "Приклад:\n"
        "/setcombo 5 🩷 Діана+Женя\n\n"
        "Маска: число (сума позицій: 1+4=5)\n"
        "Емодзі: будь-який емодзі\n"
        "Назва: текст для легенди"
    )

    # Parse command
    parts = message.text.split(maxsplit=3) if message.text else []
    if len(parts) < 4:
        await message.answer(help_text)
        return

    try:
        mask = int(parts[1])
        emoji = parts[2]
        label = parts[3]

        if mask < 0 or mask > 255:
            await message.answer("❌ Маска має бути від 0 до 255")
            return

        combo = user_manager.update_combination(mask, emoji, label)

        await message.answer(
            f"✅ Комбінацію оновлено:\n"
            f"Маска: {combo.mask}\n"
            f"Назва: {combo.label_uk}\n"
            f"Емодзі: {combo.emoji}"
        )

    except ValueError as e:
        await message.answer(f"❌ Помилка: {e}\n\n{help_text}")


@router.message(Command("colors"))
async def cmd_colors(message: Message, **kwargs):
    """Show all emojis and combinations (admin only)."""
    if not is_admin(message.from_user.id):
        await message.answer("🔒 Команда доступна лише адміністраторам.")
        return

    legend = user_manager.get_all_colors_legend()

    text = "🎨 Емодзі та комбінації:\n\n"
    for emoji, label in legend:
        text += f"{emoji} — {label}\n"

    await message.answer(text)


@router.message(Command("edituser"))
async def cmd_edit_user(message: Message, **kwargs):
    """Edit a user interactively (admin only)."""
    try:
        if not message.from_user:
            return

        if not is_admin(message.from_user.id):
            await message.answer("🔒 Команда доступна лише адміністраторам.")
            return

        help_text = (
            "📝 Редагувати користувача:\n\n"
            "Формат:\n"
            "/edituser <позиція|ім'я> [нове_ім'я_укр] [нове_ім'я_англ] [новий_емодзі]\n\n"
            "Приклади:\n"
            "/edituser 0 Діана diana 🔵\n"
            "/edituser diana - - 🟣\n"
            "(тире '-' означає не змінювати)\n\n"
            "Позиція: 0-7 або поточне ім'я\n"
            "Емодзі: будь-який емодзі (напр. 🔵)"
        )

        # Parse command
        parts = message.text.split() if message.text else []
        if len(parts) < 2:
            await message.answer(help_text)
            return

        # Find user by position or name
        identifier = parts[1]
        user = None

        try:
            # Try as bit position first
            bit_position = int(identifier)
            user = repo.get_user_by_bit(bit_position)
        except ValueError:
            # Try as name
            user = repo.get_user_by_name(identifier)

        if not user:
            await message.answer(
                f"❌ Користувача '{identifier}' не знайдено.\n"
                f"Використовуйте /users для перегляду списку."
            )
            return

        logger.info(
            f"Admin {message.from_user.id} editing user: {user.name_en} (position {user.bit_position})"
        )

        # Extract new values (use '-' to skip)
        new_name_uk = parts[2] if len(parts) > 2 and parts[2] != "-" else user.name_uk
        new_name_en = parts[3] if len(parts) > 3 and parts[3] != "-" else user.name_en
        new_emoji = parts[4] if len(parts) > 4 and parts[4] != "-" else user.emoji

        # Update user
        updated_user = user_manager.update_user(
            user.bit_position, new_name_uk, new_name_en, new_emoji, user.is_active
        )

        await message.answer(
            f"✅ Користувача оновлено:\n"
            f"Позиція: {updated_user.bit_position}\n"
            f"Ім'я: {updated_user.name_uk} ({updated_user.name_en})\n"
            f"Емодзі: {updated_user.emoji}\n"
            f"Статус: {'✅ Активний' if updated_user.is_active else '❌ Неактивний'}"
        )
        logger.info(
            f"User {updated_user.name_en} successfully updated by admin {message.from_user.id}"
        )

    except Exception as e:
        logger.error(f"Error in cmd_edit_user: {e}", exc_info=True)
        await message.answer("❌ Сталася помилка при редагуванні користувача.")


@router.message(Command("removeuser"))
async def cmd_remove_user(message: Message, **kwargs):
    """Deactivate a user (admin only)."""
    try:
        if not message.from_user:
            return

        if not is_admin(message.from_user.id):
            await message.answer("🔒 Команда доступна лише адміністраторам.")
            return

        help_text = (
            "🗑️ Деактивувати користувача:\n\n"
            "Формат:\n"
            "/removeuser <позиція|ім'я>\n\n"
            "Приклади:\n"
            "/removeuser 0\n"
            "/removeuser diana\n\n"
            "⚠️ Це деактивує користувача, але не видалить історію."
        )

        # Parse command
        parts = message.text.split() if message.text else []
        if len(parts) < 2:
            await message.answer(help_text)
            return

        # Find user by position or name
        identifier = parts[1]
        user = None

        try:
            # Try as bit position first
            bit_position = int(identifier)
            user = repo.get_user_by_bit(bit_position)
        except ValueError:
            # Try as name
            user = repo.get_user_by_name(identifier)

        if not user:
            await message.answer(
                f"❌ Користувача '{identifier}' не знайдено.\n"
                f"Використовуйте /users для перегляду списку."
            )
            return

        if not user.is_active:
            await message.answer(f"ℹ️ Користувач {user.name_uk} вже деактивований.")
            return

        logger.info(
            f"Admin {message.from_user.id} removing user: {user.name_en} (position {user.bit_position})"
        )

        # Deactivate user
        updated_user = user_manager.update_user(
            user.bit_position,
            user.name_uk,
            user.name_en,
            user.emoji,
            is_active=False,
        )

        await message.answer(
            f"✅ Користувача деактивовано:\n"
            f"Позиція: {updated_user.bit_position}\n"
            f"Ім'я: {updated_user.name_uk} ({updated_user.name_en})\n\n"
            f"⚠️ Користувач більше не буде відображатися в розкладі.\n"
            f"Для повторної активації використовуйте /edituser або /adduser."
        )
        logger.info(
            f"User {updated_user.name_en} successfully deactivated by admin {message.from_user.id}"
        )

    except Exception as e:
        logger.error(f"Error in cmd_remove_user: {e}", exc_info=True)
        await message.answer("❌ Сталася помилка при видаленні користувача.")


@router.message(Command("activateuser"))
async def cmd_activate_user(message: Message, **kwargs):
    """Reactivate a user (admin only)."""
    try:
        if not message.from_user:
            return

        if not is_admin(message.from_user.id):
            await message.answer("🔒 Команда доступна лише адміністраторам.")
            return

        help_text = (
            "✅ Активувати користувача:\n\n"
            "Формат:\n"
            "/activateuser <позиція|ім'я>\n\n"
            "Приклади:\n"
            "/activateuser 0\n"
            "/activateuser diana\n\n"
            "ℹ️ Це активує раніше деактивованого користувача."
        )

        # Parse command
        parts = message.text.split() if message.text else []
        if len(parts) < 2:
            await message.answer(help_text)
            return

        # Find user by position or name
        identifier = parts[1]
        user = None

        try:
            # Try as bit position first
            bit_position = int(identifier)
            user = repo.get_user_by_bit(bit_position)
        except ValueError:
            # Try as name
            user = repo.get_user_by_name(identifier)

        if not user:
            await message.answer(
                f"❌ Користувача '{identifier}' не знайдено.\n"
                f"Використовуйте /users для перегляду списку."
            )
            return

        if user.is_active:
            await message.answer(f"ℹ️ Користувач {user.name_uk} вже активний.")
            return

        logger.info(
            f"Admin {message.from_user.id} activating user: {user.name_en} (position {user.bit_position})"
        )

        # Activate user
        updated_user = user_manager.update_user(
            user.bit_position,
            user.name_uk,
            user.name_en,
            user.emoji,
            is_active=True,
        )

        await message.answer(
            f"✅ Користувача активовано:\n"
            f"Позиція: {updated_user.bit_position}\n"
            f"Ім'я: {updated_user.name_uk} ({updated_user.name_en})\n\n"
            f"✅ Користувач тепер буде відображатися в розкладі."
        )
        logger.info(
            f"User {updated_user.name_en} successfully activated by admin {message.from_user.id}"
        )

    except Exception as e:
        logger.error(f"Error in cmd_activate_user: {e}", exc_info=True)
        await message.answer("❌ Сталася помилка при активації користувача.")


@router.message(Command("changes"))
async def cmd_recent_changes(message: Message, **kwargs):
    """Show recent changes (admin only)."""
    if not is_admin(message.from_user.id):
        await message.answer("🔒 Команда доступна лише адміністраторам.")
        return

    changes = repo.get_recent_changes(days=7, limit=10)

    if not changes:
        await message.answer("📋 Немає нещодавніх змін.")
        return

    text = "📋 Останні зміни (7 днів):\n\n"
    for change in changes:
        old_names = user_manager.mask_to_names(change.old_mask)
        new_names = user_manager.mask_to_names(change.new_mask)

        old_text = ", ".join(old_names) if old_names else "—"
        new_text = ", ".join(new_names) if new_names else "—"

        text += f"📅 {change.change_date.strftime('%d.%m.%Y')}\n"
        text += f"   {old_text} → {new_text}\n"
        text += f"   ⏰ {change.changed_at.strftime('%d.%m %H:%M')}\n\n"

    await message.answer(text)


@router.message(Command("approvals"))
async def cmd_approvals(message: Message, **kwargs):
    """Show pending user approvals (admin only)."""
    if not is_admin(message.from_user.id):
        await message.answer("🔒 Команда доступна лише адміністраторам.")
        return

    pending = repo.get_pending_approvals()

    if not pending:
        await message.answer("✅ Немає запитів на підтвердження.")
        return

    text = f"👥 Очікують підтвердження ({len(pending)}):\n\n"

    for approval in pending:
        text += f"📝 {approval.full_name}\n"
        text += f"🆔 ID: {approval.telegram_id}\n"
        text += f"👤 @{approval.telegram_username or 'немає'}\n"
        text += f"⏰ {approval.requested_at.strftime('%d.%m.%Y %H:%M')}\n"

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="✅ Схвалити",
                        callback_data=f"approve_user_{approval.telegram_id}",
                    ),
                    InlineKeyboardButton(
                        text="❌ Відхилити",
                        callback_data=f"deny_user_{approval.telegram_id}",
                    ),
                ]
            ]
        )

        await message.answer(text, reply_markup=keyboard)
        text = ""  # Reset for next approval


@require_approval_callback
@router.callback_query(F.data.startswith("month_"))
async def callback_month_navigation(callback: CallbackQuery, **kwargs):
    """Handle month navigation callbacks."""
    try:
        if not callback.data:
            await callback.answer()
            return

        logger.debug(f"Month navigation callback: {callback.data}")

        # Handle special cases
        if callback.data == "month_limit":
            await callback.answer(
                "⏹️ Досягнуто ліміт (12 місяців назад)", show_alert=True
            )
            return

        if callback.data == "month_current":
            await callback.answer()
            return

        # Parse month data: month_YYYY_MM
        try:
            _, year_str, month_str = callback.data.split("_")
            year = int(year_str)
            month = int(month_str)
        except (ValueError, IndexError) as e:
            logger.error(f"Failed to parse month callback data '{callback.data}': {e}")
            await callback.answer("❌ Невірний формат", show_alert=True)
            return

        # Validate month is within 12-month history
        today = date.today()
        twelve_months_ago = today.replace(day=1) - relativedelta(months=11)
        requested_date = date(year, month, 1)

        if requested_date < twelve_months_ago:
            logger.warning(f"User tried to navigate beyond 12 months: {requested_date}")
            await callback.answer(
                "⏹️ Можна переглядати лише останні 12 місяців", show_alert=True
            )
            return

        # Render and send calendar
        try:
            from aiogram.types import InputMediaPhoto
            from babel.dates import format_date

            logger.info(f"Rendering calendar for {year}-{month:02d}")
            image_buffer = renderer.render(year, month)

            month_name = format_date(
                date(year, month, 1), "LLLL yyyy", locale="uk"
            ).capitalize()

            # Get navigation keyboard
            keyboard = get_month_navigation_keyboard(year, month)

            # Create new media
            photo = BufferedInputFile(
                image_buffer.read(), filename=f"calendar_{year}_{month:02d}.png"
            )

            # Edit message with new calendar
            if callback.message:
                await callback.message.edit_media(
                    media=InputMediaPhoto(
                        media=photo, caption=f"📅 Розклад на {month_name}"
                    ),
                    reply_markup=keyboard,
                )
                logger.info(f"Calendar updated to {year}-{month:02d}")
            else:
                logger.warning("No callback message to edit")

            await callback.answer()
        except Exception as e:
            logger.error(f"Failed to render calendar in callback: {e}", exc_info=True)
            await callback.answer(
                "❌ Помилка при завантаженні календаря", show_alert=True
            )
    except Exception as e:
        logger.error(
            f"Unhandled error in month navigation callback: {e}", exc_info=True
        )
        await callback.answer("❌ Сталася помилка", show_alert=True)


@router.callback_query(F.data.startswith("approve_user_"))
async def callback_approve_user(callback: CallbackQuery, **kwargs):
    """Handle user approval callback."""
    try:
        if not callback.from_user or not is_admin(callback.from_user.id):
            await callback.answer("🔒 Недостатньо прав", show_alert=True)
            return

        # Extract user ID from callback data
        try:
            user_id = int(callback.data.split("_")[-1])
            logger.info(f"Admin {callback.from_user.id} approving user {user_id}")
        except (ValueError, AttributeError) as e:
            logger.error(f"Failed to parse user approval callback data: {e}")
            await callback.answer("❌ Невірний формат ID", show_alert=True)
            return

        # Approve user
        approval = repo.approve_user(user_id, callback.from_user.id)

        if not approval:
            logger.warning(f"User {user_id} not found for approval")
            await callback.answer("❌ Користувача не знайдено", show_alert=True)
            return

        # Update message
        if callback.message:
            await callback.message.edit_text(
                f"✅ Користувач {approval.full_name} (ID: {user_id}) схвалений!\n"
                f"Адміністратор: {callback.from_user.full_name or callback.from_user.username}",
                reply_markup=None,
            )

        # Notify user
        if callback.bot:
            try:
                await callback.bot.send_message(
                    user_id,
                    "✅ Ваш доступ до бота схвалено!\n"
                    "Використовуйте /start для початку роботи.",
                )
                logger.info(f"User {user_id} notified of approval")
            except Exception as e:
                logger.error(f"Failed to notify user {user_id}: {e}")

        await callback.answer("✅ Користувач схвалений")
    except Exception as e:
        logger.error(f"Unhandled error in user approval callback: {e}", exc_info=True)
        await callback.answer("❌ Сталася помилка", show_alert=True)


@router.callback_query(F.data.startswith("deny_user_"))
async def callback_deny_user(callback: CallbackQuery, **kwargs):
    """Handle user denial callback."""
    try:
        if not callback.from_user or not is_admin(callback.from_user.id):
            await callback.answer("🔒 Недостатньо прав", show_alert=True)
            return

        # Extract user ID from callback data
        try:
            user_id = int(callback.data.split("_")[-1])
            logger.info(f"Admin {callback.from_user.id} denying user {user_id}")
        except (ValueError, AttributeError) as e:
            logger.error(f"Failed to parse user denial callback data: {e}")
            await callback.answer("❌ Невірний формат ID", show_alert=True)
            return

        # Deny user
        approval = repo.deny_user(user_id, callback.from_user.id)

        if not approval:
            logger.warning(f"User {user_id} not found for denial")
            await callback.answer("❌ Користувача не знайдено", show_alert=True)
            return

        # Update message
        if callback.message:
            await callback.message.edit_text(
                f"❌ Користувач {approval.full_name} (ID: {user_id}) відхилений.\n"
                f"Адміністратор: {callback.from_user.full_name or callback.from_user.username}",
                reply_markup=None,
            )

        # Notify user
        if callback.bot:
            try:
                await callback.bot.send_message(
                    user_id, "❌ На жаль, вам було відмовлено в доступі до бота."
                )
                logger.info(f"User {user_id} notified of denial")
            except Exception as e:
                logger.error(f"Failed to notify user {user_id}: {e}")

        await callback.answer("❌ Користувач відхилений")
    except Exception as e:
        logger.error(f"Unhandled error in user denial callback: {e}", exc_info=True)
        await callback.answer("❌ Сталася помилка", show_alert=True)


@router.message(F.photo)
@require_approval
async def handle_photo(message: Message, bot: Bot):
    """
    Handle photo messages for schedule extraction.

    Uses Gemini Vision to analyze calendar images and extract schedule assignments.
    Only admins can import schedules from images.
    """
    try:
        if not message.from_user:
            logger.warning("Received photo message without user")
            return

        user_id = message.from_user.id

        # Check admin permissions
        if not is_admin(user_id):
            await message.answer(
                "❌ Лише адміністратори можуть імпортувати розклади з зображень.",
                reply_markup=get_main_keyboard(),
            )
            logger.info(f"Non-admin user {user_id} tried to upload schedule image")
            return

        # Get the largest photo
        if not message.photo:
            logger.warning("Photo message has no photo array")
            return

        photo = message.photo[-1]  # Largest photo

        # Notify user we're processing
        status_msg = await message.answer("🔍 Аналізую календар...")

        logger.info(f"Admin {user_id} uploaded schedule image, file_id={photo.file_id}")

        # Download photo
        file = await bot.get_file(photo.file_id)
        if not file.file_path:
            await status_msg.edit_text("❌ Не вдалося завантажити зображення.")
            return

        # Download bytes
        from io import BytesIO

        photo_bytes = BytesIO()
        await bot.download_file(file.file_path, photo_bytes)
        photo_bytes.seek(0)
        image_data = photo_bytes.read()

        logger.debug(f"Downloaded image: {len(image_data)} bytes")

        # Parse schedule with Gemini Vision
        from .nlp import parse_schedule_from_image

        today = date.today()

        try:
            schedule = await parse_schedule_from_image(image_data, today)
            logger.info(
                f"Extracted schedule for {schedule.month}/{schedule.year}: "
                f"{len(schedule.assignments)} assignments"
            )
        except ValueError as e:
            await status_msg.edit_text(f"❌ {str(e)}")
            return
        except Exception as e:
            logger.error(f"Failed to parse schedule image: {e}", exc_info=True)
            await status_msg.edit_text(
                "❌ Не вдалося розпізнати календар. Переконайтеся, що зображення чітке і містить календар."
            )
            return

        # Show extracted data and ask for confirmation
        if not schedule.assignments:
            await status_msg.edit_text(
                "⚠️ Не знайдено жодного призначення на календарі.\n"
                "Переконайтеся, що календар має кольорові позначки для днів."
            )
            return

        # Format summary
        month_names = [
            "Січень",
            "Лютий",
            "Березень",
            "Квітень",
            "Травень",
            "Червень",
            "Липень",
            "Серпень",
            "Вересень",
            "Жовтень",
            "Листопад",
            "Грудень",
        ]
        month_name = month_names[schedule.month - 1]

        summary = f"📅 Знайдено розклад: {month_name} {schedule.year}\n\n"
        summary += f"Знайдено {len(schedule.assignments)} призначень:\n"

        # Group by person for summary
        person_days = {"diana": [], "dana": [], "zhenya": []}
        for assignment in schedule.assignments:
            for person in assignment.people:
                person_days[person].append(assignment.day)

        person_names = {"diana": "Діана 🔵", "dana": "Дана 🟣", "zhenya": "Женя 🟢"}
        for person, days in person_days.items():
            if days:
                days.sort()
                days_str = ", ".join(str(d) for d in days)
                summary += f"\n{person_names[person]}: {days_str}"

        summary += "\n\n✅ Зберегти ці призначення?"

        # Create confirmation keyboard
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="✅ Так, зберегти",
                        callback_data=f"confirm_import_{schedule.month}_{schedule.year}",
                    ),
                    InlineKeyboardButton(
                        text="❌ Скасувати", callback_data="cancel_import"
                    ),
                ]
            ]
        )

        # Store schedule in module-level dict for confirmation callback
        pending_schedule_imports[user_id] = schedule

        await status_msg.edit_text(summary, reply_markup=keyboard)

    except Exception as e:
        logger.error(f"Unhandled error in photo handler: {e}", exc_info=True)
        await message.answer(
            "❌ Сталася помилка при обробці зображення.",
            reply_markup=get_main_keyboard(),
        )


@router.callback_query(F.data.startswith("confirm_import_"))
async def handle_confirm_import(callback: CallbackQuery, bot: Bot):
    """Handle confirmation of schedule import from image."""
    try:
        user_id = callback.from_user.id

        if not is_admin(user_id):
            await callback.answer("❌ Недостатньо прав", show_alert=True)
            return

        # Get pending import
        if user_id not in pending_schedule_imports:
            await callback.answer(
                "❌ Дані застаріли, спробуйте ще раз", show_alert=True
            )
            return

        schedule = pending_schedule_imports[user_id]

        # Import assignments
        from datetime import date as dt

        imported_count = 0
        errors = []

        for assignment in schedule.assignments:
            try:
                day_date = dt(schedule.year, schedule.month, assignment.day)

                # Create assignment from people list
                from .models import Assignment

                asg = Assignment.from_people(day_date, assignment.people)
                repo.upsert(asg)
                imported_count += 1

                logger.info(f"Imported from image: {day_date} -> {assignment.people}")
            except ValueError as e:
                errors.append(f"День {assignment.day}: {str(e)}")
                logger.warning(
                    f"Invalid date in import: {schedule.month}/{assignment.day}"
                )
            except Exception as e:
                errors.append(f"День {assignment.day}: помилка")
                logger.error(f"Failed to import assignment: {e}", exc_info=True)

        # Clear pending import
        del pending_schedule_imports[user_id]

        # Send result
        month_names = [
            "Січень",
            "Лютий",
            "Березень",
            "Квітень",
            "Травень",
            "Червень",
            "Липень",
            "Серпень",
            "Вересень",
            "Жовтень",
            "Листопад",
            "Грудень",
        ]
        result_text = f"✅ Імпортовано {imported_count} призначень для {month_names[schedule.month - 1]} {schedule.year}"

        if errors:
            result_text += f"\n\n⚠️ Помилки ({len(errors)}):\n" + "\n".join(errors[:5])
            if len(errors) > 5:
                result_text += f"\n... та ще {len(errors) - 5}"

        await callback.message.edit_text(result_text)
        await callback.answer("✅ Розклад імпортовано")

        # Log the import for admins
        logger.info(
            f"Admin {user_id} imported schedule from image: "
            f"{month_names[schedule.month - 1]} {schedule.year} ({imported_count} days)"
        )

    except Exception as e:
        logger.error(f"Unhandled error in import confirmation: {e}", exc_info=True)
        await callback.answer("❌ Сталася помилка", show_alert=True)


@router.callback_query(F.data == "cancel_import")
async def handle_cancel_import(callback: CallbackQuery, bot: Bot):
    """Handle cancellation of schedule import."""
    try:
        user_id = callback.from_user.id

        # Clear pending import if exists
        if user_id in pending_schedule_imports:
            del pending_schedule_imports[user_id]

        await callback.message.edit_text("❌ Імпорт скасовано")
        await callback.answer("Скасовано")

    except Exception as e:
        logger.error(f"Error in cancel import callback: {e}", exc_info=True)
        await callback.answer("❌ Сталася помилка", show_alert=True)


@require_approval
@router.message(F.text)
async def nlp_entry(message: Message, **kwargs):
    """
    Handle natural language text input.

    Intents:
    - action: "show_month" | "assign_day" | "assign_days" | "assign_bulk" | "who_works" | "help"
    - fields: year?, month?, day?, days?, people?: ["diana"|"dana"|"zhenya"], pattern?, note?
    - Map: show->render; assign->upsert; assign_days->multi upsert; assign_bulk->pattern upsert; who_works->lookup; help->tips.

    Admin guard:
    - if cmd.action in ("assign_day", "assign_days", "assign_bulk") and not is_admin(user_id): reply("Лише для адміністратора.")
    """
    try:
        if not message.from_user or not message.text:
            logger.warning("Received message without user or text")
            return

        today = date.today()

        # Parse utterance with Gemini
        logger.info(f"User {message.from_user.id}: {message.text}")

        try:
            cmd: NLCommand = await parse_utterance(message.text, today)
            logger.debug(f"Parsed command: {cmd.action}")
        except Exception as e:
            logger.error(f"Failed to parse utterance: {e}", exc_info=True)
            await message.answer(
                "❌ Не вдалося розпізнати команду. Спробуйте ще раз або використайте /help для довідки.",
                reply_markup=get_main_keyboard(),
            )
            return

        # Dispatch based on action
        if cmd.action == "show_month":
            await handle_show_month(message, cmd)
        elif cmd.action == "who_works":
            await handle_who_works(message, cmd)
        elif cmd.action == "assign_day":
            await handle_assign_day(message, cmd)
        elif cmd.action == "assign_days":
            await handle_assign_days(message, cmd)
        elif cmd.action == "assign_bulk":
            await handle_assign_bulk(message, cmd)
        else:  # help
            await cmd_help(message)
    except Exception as e:
        logger.error(f"Unhandled error in NLP entry: {e}", exc_info=True)
        await message.answer(
            "❌ Сталася помилка при обробці вашого запиту.",
            reply_markup=get_main_keyboard(),
        )


async def setup_bot() -> tuple[Bot, Dispatcher]:
    """Set up and return bot and dispatcher."""
    bot = Bot(token=config.BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)

    # Set command hints for all users
    await set_bot_commands(bot)

    return bot, dp


async def set_bot_commands(bot: Bot):
    """Set bot command hints for users and admins."""
    try:
        # Commands for all users
        user_commands = [
            BotCommand(command="start", description="🏠 Початок роботи з ботом"),
            BotCommand(command="help", description="❓ Показати довідку"),
        ]

        # Set commands for all private chats
        await bot.set_my_commands(
            commands=user_commands, scope=BotCommandScopeAllPrivateChats()
        )

        # Additional commands for admins
        admin_commands = [
            BotCommand(command="start", description="🏠 Початок роботи з ботом"),
            BotCommand(command="help", description="❓ Показати довідку"),
            BotCommand(command="users", description="👥 Список користувачів"),
            BotCommand(command="adduser", description="➕ Додати/оновити користувача"),
            BotCommand(command="edituser", description="✏️ Редагувати користувача"),
            BotCommand(command="removeuser", description="🗑️ Деактивувати користувача"),
            BotCommand(command="activateuser", description="✅ Активувати користувача"),
            BotCommand(
                command="setcombo", description="🎨 Встановити колір комбінації"
            ),
            BotCommand(command="colors", description="🌈 Показати всі кольори"),
            BotCommand(command="changes", description="📋 Останні зміни (7 днів)"),
            BotCommand(command="approvals", description="✅ Запити на підтвердження"),
        ]

        # Set admin commands for each admin
        for admin_id in config.ADMIN_IDS:
            try:
                await bot.set_my_commands(
                    commands=admin_commands, scope=BotCommandScopeChat(chat_id=admin_id)
                )
            except Exception as e:
                logger.warning(f"Failed to set commands for admin {admin_id}: {e}")

        logger.info("Bot commands configured successfully")
    except Exception as e:
        logger.error(f"Failed to set bot commands: {e}")
