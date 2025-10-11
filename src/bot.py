"""Telegram bot handlers and routers."""

from datetime import date
from io import BytesIO

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    BufferedInputFile,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)
from loguru import logger

from .config import config
from .image_render import renderer
from .intents import NLCommand
from .models import Assignment
from .nlp import parse_utterance
from .repo import repo

# Create router
router = Router()


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
async def cmd_start(message: Message):
    """Handle /start command."""
    welcome_text = (
        "👋 Вітаю в боті розкладу Coffee Dealer!\n\n"
        "Я можу показати розклад роботи та допомогти з призначеннями.\n\n"
        "Використовуй кнопки меню або пиши вільною мовою:\n"
        '• "покажи жовтень"\n'
        '• "хто працює 15 числа?"\n'
    )

    if is_admin(message.from_user.id):
        welcome_text += '• "постав Діану на 5 жовтня"\n'
        welcome_text += "\n✅ У тебе є права адміністратора."
    else:
        welcome_text += "\n⚠️ Змінювати розклад можуть лише адміністратори."

    await message.answer(welcome_text, reply_markup=get_main_keyboard())


@router.message(Command("help"))
@router.message(F.text == "❓ Допомога")
async def cmd_help(message: Message):
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
            "👥 Люди: Діана, Дана, Женя\n\n"
            "🎨 Кольори:\n"
            "• Синій = Діана\n"
            "• Фіолетовий = Дана\n"
            "• Зелений = Женя\n"
            "• Рожевий = Діана+Женя\n"
            "• Жовтий = Дана+Женя\n"
            "• Червоний = Дана+Діана\n"
        )

    await message.answer(help_text, reply_markup=get_main_keyboard())


@router.message(F.text == "📅 Показати місяць")
async def show_current_month(message: Message):
    """Show current month calendar."""
    today = date.today()
    await send_calendar(message, today.year, today.month)


async def send_calendar(message: Message, year: int, month: int):
    """Send calendar image for specified month."""
    try:
        # Render calendar
        logger.info(f"Rendering calendar for {year}-{month:02d}")
        image_buffer = renderer.render(year, month)

        # Send as photo
        photo = BufferedInputFile(
            image_buffer.read(), filename=f"calendar_{year}_{month:02d}.png"
        )

        # Get month name in Ukrainian
        from babel.dates import format_date

        month_name = format_date(
            date(year, month, 1), "LLLL yyyy", locale="uk"
        ).capitalize()

        await message.answer_photo(
            photo=photo,
            caption=f"📅 Розклад на {month_name}",
            reply_markup=get_main_keyboard(),
        )
    except Exception as e:
        logger.error(f"Failed to render calendar: {e}")
        await message.answer(
            "❌ Помилка при створенні календаря. Спробуй ще раз.",
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


async def handle_assign_day(message: Message, cmd: NLCommand):
    """Handle assign_day action (admin only)."""
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

    if not cmd.day:
        await message.answer(
            "❌ Не вказано день. Спробуй ще раз, наприклад: 'постав Діану на 5 жовтня'",
            reply_markup=get_main_keyboard(),
        )
        return

    try:
        assign_date = date(year, month, cmd.day)

        # Create assignment
        assignment = Assignment.from_people(
            day=assign_date, people=cmd.people, note=cmd.note
        )

        # Save to database
        repo.upsert(assignment)

        # Prepare response
        if assignment.mask > 0:
            names = assignment.get_people_names()
            names_text = ", ".join(names)
            response = (
                f"✅ Призначено на {assign_date.strftime('%d.%m.%Y')}: {names_text}"
            )
        else:
            response = f"✅ Видалено призначення на {assign_date.strftime('%d.%m.%Y')}"

        await message.answer(response, reply_markup=get_main_keyboard())

        # Also show updated month
        await send_calendar(message, year, month)

    except ValueError as e:
        await message.answer(
            f"❌ Некоректна дата: {e}", reply_markup=get_main_keyboard()
        )


@router.message(F.text)
async def nlp_entry(message: Message):
    """
    Handle natural language text input.

    Intents:
    - action: "show_month" | "assign_day" | "who_works" | "help"
    - fields: year?, month?, day?, people?: ["diana"|"dana"|"zhenya"], note?
    - Map: show->render; assign->upsert; who_works->lookup; help->tips.

    Admin guard:
    - if cmd.action == "assign_day" and not is_admin(user_id): reply("Лише для адміністратора.")
    """
    today = date.today()

    # Parse utterance with Gemini
    logger.info(f"User {message.from_user.id}: {message.text}")
    cmd: NLCommand = await parse_utterance(message.text, today)

    # Dispatch based on action
    if cmd.action == "show_month":
        await handle_show_month(message, cmd)
    elif cmd.action == "who_works":
        await handle_who_works(message, cmd)
    elif cmd.action == "assign_day":
        await handle_assign_day(message, cmd)
    else:  # help
        await cmd_help(message)


async def setup_bot() -> tuple[Bot, Dispatcher]:
    """Set up and return bot and dispatcher."""
    bot = Bot(token=config.BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)
    return bot, dp
