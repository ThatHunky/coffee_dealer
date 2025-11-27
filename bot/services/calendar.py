"""Calendar rendering service"""

import io
import os
import random
import math
from datetime import date, datetime, timedelta
from typing import List, Dict, Optional, Tuple
from calendar import monthrange, month_name
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance, ImageChops

from bot.database.operations import get_shift, get_all_users, async_session_maker
from bot.utils.colors import get_color_emoji, get_combined_color_emoji


# Ukrainian month names
UKRAINIAN_MONTHS = {
    1: "Січень",
    2: "Лютий",
    3: "Березень",
    4: "Квітень",
    5: "Травень",
    6: "Червень",
    7: "Липень",
    8: "Серпень",
    9: "Вересень",
    10: "Жовтень",
    11: "Листопад",
    12: "Грудень",
}

# Ukrainian day abbreviations
UKRAINIAN_DAYS = ["П", "В", "С", "Ч", "П", "С", "Н"]  # Mon-Sun


def get_month_name_ukrainian(month: int) -> str:
    """Get Ukrainian month name"""
    return UKRAINIAN_MONTHS.get(month, month_name[month])


def add_noise(image: Image.Image, intensity: int = 15) -> Image.Image:
    """Add Gaussian noise to image"""
    width, height = image.size
    noise = Image.effect_noise((width, height), intensity)
    noise = noise.convert("RGB")

    # Blend noise with image
    if image.mode == "RGBA":
        noise = noise.convert("RGBA")
        # Make noise semi-transparent
        noise.putalpha(30)
        return Image.alpha_composite(image, noise)
    else:
        return ImageChops.blend(image, noise, 0.05)


def create_organic_blob(
    width: int, height: int, color: Tuple[int, int, int]
) -> Image.Image:
    """Create a fuzzy organic blob"""
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Random blob parameters
    cx, cy = width // 2, height // 2
    radius = min(width, height) // 3
    points = []
    steps = 12
    for i in range(steps):
        angle = (i / steps) * 2 * math.pi
        r = radius * random.uniform(0.8, 1.2)
        x = cx + math.cos(angle) * r
        y = cy + math.sin(angle) * r
        points.append((x, y))

    # Draw polygon and blur heavily
    draw.polygon(points, fill=color + (200,))
    return img.filter(ImageFilter.GaussianBlur(radius=radius // 2))


def create_mesh_gradient(
    width: int, height: int, colors: List[Tuple[int, int, int]]
) -> Image.Image:
    """Create a complex mesh-like gradient background"""
    base = Image.new("RGB", (width, height), colors[0])

    # Add random blobs of other colors
    for color in colors[1:]:
        # Random position and size
        blob_w = int(width * random.uniform(0.8, 1.5))
        blob_h = int(height * random.uniform(0.8, 1.5))
        blob = create_organic_blob(blob_w, blob_h, color)

        # Paste at random position
        x = random.randint(-blob_w // 2, width - blob_w // 2)
        y = random.randint(-blob_h // 2, height - blob_h // 2)

        base.paste(blob, (x, y), blob)

    return base


def draw_squircle(draw, xy, radius, fill=None, outline=None, width=1):
    """Draw a superellipse (squircle) approximation"""
    x1, y1, x2, y2 = xy

    # Use standard rounded rect for now but with smoother corners logic if needed
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=None, width=0)

    if outline and width > 0:
        draw.rounded_rectangle(
            xy, radius=radius, fill=None, outline=outline, width=width
        )


def draw_glass_panel(draw, xy, radius):
    """Draw a glass panel effect with highlight and shadow"""
    x1, y1, x2, y2 = xy

    # Main glass body
    draw_squircle(draw, xy, radius, fill=(255, 255, 255, 15))

    # Top/Left Highlight (Rim light)
    draw.line(
        [(x1 + radius, y1), (x2 - radius, y1)], fill=(255, 255, 255, 100), width=1
    )
    draw.line(
        [(x1, y1 + radius), (x1, y2 - radius)], fill=(255, 255, 255, 100), width=1
    )

    # Bottom/Right Shadow (Rim shadow)
    draw.line([(x1 + radius, y2), (x2 - radius, y2)], fill=(0, 0, 0, 40), width=1)
    draw.line([(x2, y1 + radius), (x2, y2 - radius)], fill=(0, 0, 0, 40), width=1)


def draw_text_with_glow_v2(
    image, text, position, font, color, glow_color, glow_radius=3
):
    """
    Draw text with Gaussian blur glow.
    """
    draw = ImageDraw.Draw(image)
    x, y = position

    # Create a separate image for the glow
    # Make it large enough to hold the text + padding for blur
    # We need to measure text size first
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    # Padding for glow
    padding = glow_radius * 3

    # Create temp image
    glow_img = Image.new(
        "RGBA", (text_width + padding * 2, text_height + padding * 2), (0, 0, 0, 0)
    )
    glow_draw = ImageDraw.Draw(glow_img)

    # Draw text centered in temp image
    # Note: textbbox coordinates are relative to (0,0) but might have offset
    # We want to draw at (padding, padding) roughly, but need to account for font metrics
    # simpler: draw at (padding - bbox[0], padding - bbox[1]) to align top-left

    glow_draw.text(
        (padding - bbox[0], padding - bbox[1]), text, font=font, fill=glow_color
    )

    # Apply blur
    glow_blurred = glow_img.filter(ImageFilter.GaussianBlur(radius=glow_radius))

    # Paste
    image.paste(glow_blurred, (int(x - padding), int(y - padding)), glow_blurred)

    # Draw main text
    draw.text((x, y), text, fill=color, font=font)


async def build_calendar_keyboard(
    year: int, month: int, is_history: bool = False
) -> InlineKeyboardMarkup:
    """
    Build calendar inline keyboard for a given month.

    Args:
        year: Year
        month: Month (1-12)
        is_history: Whether this is a historical view (read-only)

    Returns:
        InlineKeyboardMarkup with calendar
    """
    builder = InlineKeyboardBuilder()

    # Get all users and shifts for the month (exclude hidden users)
    async with async_session_maker() as session:
        users = await get_all_users(session, include_hidden=False)
        users_dict = {u.user_id: u for u in users}

        # Get first and last day of month
        first_day = date(year, month, 1)
        last_day_num = monthrange(year, month)[1]
        last_day = date(year, month, last_day_num)

        # Get all shifts in the month
        from bot.database.operations import get_shifts_in_range

        shifts = await get_shifts_in_range(session, first_day, last_day)
        shifts_dict = {s.date: s for s in shifts}

    # Header with month name
    month_name_ukr = get_month_name_ukrainian(month)
    header_text = f"{month_name_ukr} {year}"

    # Day headers row
    day_headers = []
    for day_abbr in UKRAINIAN_DAYS:
        day_headers.append(InlineKeyboardButton(text=day_abbr, callback_data="ignore"))
    builder.row(*day_headers)

    # Get first weekday of month (0=Monday, 6=Sunday)
    first_weekday = first_day.weekday()  # 0=Monday

    # Add empty cells for days before month starts
    for _ in range(first_weekday):
        builder.button(text=" ", callback_data="ignore")

    # Add day buttons
    today = date.today()
    for day in range(1, last_day_num + 1):
        current_date = date(year, month, day)

        # Get shift for this day
        shift = shifts_dict.get(current_date)
        user_ids = shift.user_ids if shift else []

        # Get colors for users
        colors = []
        user_names = []
        for user_id in user_ids:
            user = users_dict.get(user_id)
            if user and user.color_code:
                colors.append(user.color_code)
                user_names.append(user.name)

        # Get emoji for display
        if colors:
            emoji = get_combined_color_emoji(colors)
        else:
            emoji = "⚪"

        # Format button text
        button_text = f"{day} {emoji}"

        # Highlight today
        if current_date == today and not is_history:
            button_text = f"📍 {day}"

        # Callback data
        if is_history:
            callback_data = f"ignore"  # Read-only
        else:
            callback_data = f"day_{year}_{month:02d}_{day:02d}"

        builder.button(text=button_text, callback_data=callback_data)

    # Add empty cells to complete last row if needed
    last_weekday = last_day.weekday()
    remaining_cells = 6 - last_weekday
    for _ in range(remaining_cells):
        builder.button(text=" ", callback_data="ignore")

    # Navigation buttons
    nav_buttons = []

    # Previous month
    prev_month = month - 1
    prev_year = year
    if prev_month < 1:
        prev_month = 12
        prev_year -= 1

    if is_history:
        nav_buttons.append(
            InlineKeyboardButton(
                text="<< Попередній",
                callback_data=f"history_{prev_year}_{prev_month:02d}",
            )
        )
    else:
        nav_buttons.append(
            InlineKeyboardButton(
                text="<< Попередній",
                callback_data=f"calendar_{prev_year}_{prev_month:02d}",
            )
        )

    # Today button (only for current calendar)
    if not is_history:
        today_date = date.today()
        nav_buttons.append(
            InlineKeyboardButton(
                text="📅 Сьогодні",
                callback_data=f"calendar_{today_date.year}_{today_date.month:02d}",
            )
        )

    # Next month
    next_month = month + 1
    next_year = year
    if next_month > 12:
        next_month = 1
        next_year += 1

    if is_history:
        # Don't allow future months in history
        if next_year < date.today().year or (
            next_year == date.today().year and next_month <= date.today().month
        ):
            nav_buttons.append(
                InlineKeyboardButton(
                    text="Наступний >>",
                    callback_data=f"history_{next_year}_{next_month:02d}",
                )
            )
    else:
        nav_buttons.append(
            InlineKeyboardButton(
                text="Наступний >>",
                callback_data=f"calendar_{next_year}_{next_month:02d}",
            )
        )

    builder.row(*nav_buttons)

    return builder.as_markup()


async def build_day_user_selection_keyboard(
    year: int, month: int, day: int
) -> InlineKeyboardMarkup:
    """
    Build keyboard for selecting users for a specific day.

    Args:
        year: Year
        month: Month
        day: Day

    Returns:
        InlineKeyboardMarkup with user selection
    """
    builder = InlineKeyboardBuilder()

    async with async_session_maker() as session:
        users = await get_all_users(session, include_hidden=False)
        current_date = date(year, month, day)
        shift = await get_shift(session, current_date)
        current_user_ids = set(shift.user_ids) if shift else set()

    # Add user buttons
    for user in users:
        emoji = get_color_emoji(user.color_code) if user.color_code else "⚪"
        is_selected = "✅" if user.user_id in current_user_ids else "⚪"
        button_text = f"{is_selected} {emoji} {user.name}"

        builder.button(
            text=button_text,
            callback_data=f"toggle_user_{year}_{month:02d}_{day:02d}_{user.user_id}",
        )

    # Add "Clear" button
    builder.button(
        text="🗑️ Очистити", callback_data=f"clear_day_{year}_{month:02d}_{day:02d}"
    )

    # Add "Back" button (returns to image view)
    builder.button(
        text="⬅️ Назад до календаря", callback_data=f"view_calendar_{year}_{month:02d}"
    )

    builder.adjust(1)  # One button per row
    return builder.as_markup()


def get_calendar_text(year: int, month: int, is_history: bool = False) -> str:
    """Get calendar header text"""
    month_name_ukr = get_month_name_ukrainian(month)
    header = f"📅 {month_name_ukr} {year}"
    if is_history:
        header += " (Історія)"
    return header


def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """Convert hex color to RGB tuple"""
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))


async def generate_calendar_image(
    year: int, month: int, is_history: bool = False
) -> BufferedInputFile:
    """
    Generate a calendar image with colored days and enhanced graphics.

    Args:
        year: Year
        month: Month (1-12)
        is_history: Whether this is a historical view

    Returns:
        BufferedInputFile with the calendar image
    """
    # --- CONFIGURATION ---
    cell_size = 110
    header_height = 100
    day_header_height = 50
    padding = 50
    cols = 7
    rows = 6

    # Legend configuration (Right side)
    legend_width = 300

    # Calculate dimensions
    calendar_width = cols * cell_size + 2 * padding
    total_width = calendar_width + legend_width
    height = header_height + day_header_height + rows * cell_size + 2 * padding

    # Get data
    async with async_session_maker() as session:
        users = await get_all_users(session, include_hidden=False)

        first_day = date(year, month, 1)
        last_day_num = monthrange(year, month)[1]
        last_day = date(year, month, last_day_num)

        from bot.database.operations import get_shifts_in_range

        shifts = await get_shifts_in_range(session, first_day, last_day)
        shifts_dict = {s.date: s for s in shifts}

    # Create background (Mesh Gradient)
    colors = [
        (10, 20, 40),  # Deep Blue
        (40, 10, 60),  # Deep Purple
        (0, 40, 60),  # Deep Teal
        (60, 20, 40),  # Deep Magenta
    ]
    bg_img = create_mesh_gradient(total_width, height, colors)

    # Add noise texture
    bg_img = add_noise(bg_img, intensity=20)

    # Create drawing context
    draw = ImageDraw.Draw(bg_img, "RGBA")

    # Fonts
    try:
        font_path_bold = "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"
        font_path_reg = "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"

        title_font = ImageFont.truetype(font_path_bold, 56)
        day_font = ImageFont.truetype(font_path_bold, 24)
        number_font = ImageFont.truetype(font_path_bold, 36)
        legend_font = ImageFont.truetype(font_path_reg, 24)
    except:
        title_font = ImageFont.load_default()
        day_font = ImageFont.load_default()
        number_font = ImageFont.load_default()
        legend_font = ImageFont.load_default()

    # --- MAIN GLASS PANEL ---
    panel_margin = 20
    draw_glass_panel(
        draw,
        (
            panel_margin,
            panel_margin,
            calendar_width - panel_margin,
            height - panel_margin,
        ),
        radius=30,
    )

    # --- HEADER ---
    month_name_ukr = get_month_name_ukrainian(month)
    header_text = f"{month_name_ukr} {year}"
    if is_history:
        header_text += " (Історія)"

    bbox = draw.textbbox((0, 0), header_text, font=title_font)
    text_width = bbox[2] - bbox[0]
    text_x = (calendar_width - text_width) // 2
    text_y = padding + 10

    draw_text_with_glow_v2(
        bg_img,
        header_text,
        (text_x, text_y),
        title_font,
        (255, 255, 255, 255),
        (255, 255, 255, 150),
        glow_radius=8,
    )

    # --- CALENDAR GRID ---
    y_start = header_height + padding

    # Day headers
    for i, day_abbr in enumerate(UKRAINIAN_DAYS):
        x = padding + i * cell_size
        y = y_start

        bbox = draw.textbbox((0, 0), day_abbr, font=day_font)
        tw = bbox[2] - bbox[0]
        tx = x + (cell_size - tw) // 2
        ty = y + (day_header_height - (bbox[3] - bbox[1])) // 2
        draw.text((tx, ty), day_abbr, fill=(255, 255, 255, 180), font=day_font)

    # Days
    first_day_obj = date(year, month, 1)
    first_weekday = first_day_obj.weekday()
    y_start += day_header_height

    day_num = 1

    for row in range(rows):
        for col in range(cols):
            x = padding + col * cell_size
            y = y_start + row * cell_size

            # Cell box
            box = (x + 5, y + 5, x + cell_size - 5, y + cell_size - 5)

            if row == 0 and col < first_weekday:
                continue

            if day_num > last_day_num:
                break

            current_date = date(year, month, day_num)
            shift = shifts_dict.get(current_date)

            # Day Cell Glass
            if shift:
                fill_color = (255, 255, 255, 30)
                outline_color = (255, 255, 255, 80)
            else:
                fill_color = (255, 255, 255, 10)
                outline_color = (255, 255, 255, 30)

            draw_squircle(
                draw, box, radius=16, fill=fill_color, outline=outline_color, width=1
            )

            # Draw number
            draw.text(
                (x + 15, y + 10),
                str(day_num),
                fill=(255, 255, 255, 220),
                font=number_font,
            )

            # Draw user indicators
            if shift and shift.user_ids:
                bar_height = 6
                bar_y = y + cell_size - 20
                # Filter users that exist in our users list
                valid_user_ids = [
                    uid
                    for uid in shift.user_ids
                    if any(u.user_id == uid for u in users)
                ]

                if valid_user_ids:
                    bar_width = (cell_size - 30) / len(valid_user_ids)
                    start_x = x + 15

                    for i, uid in enumerate(valid_user_ids):
                        user = next((u for u in users if u.user_id == uid), None)
                        if user and user.color_code:
                            color = hex_to_rgb(user.color_code)
                            bx = start_x + i * bar_width
                            draw.rectangle(
                                [bx, bar_y, bx + bar_width - 2, bar_y + bar_height],
                                fill=color + (255,),
                            )
                            draw.rectangle(
                                [
                                    bx - 1,
                                    bar_y - 1,
                                    bx + bar_width - 1,
                                    bar_y + bar_height + 1,
                                ],
                                outline=color + (100,),
                                width=1,
                            )

            day_num += 1

    # --- LEGEND (RIGHT SIDE) ---
    legend_x = calendar_width
    legend_y = padding

    draw_glass_panel(
        draw, (legend_x, legend_y, total_width - padding, height - padding), radius=30
    )

    draw.text(
        (legend_x + 30, legend_y + 30),
        "Легенда",
        fill=(255, 255, 255, 255),
        font=day_font,
    )

    item_y = legend_y + 80
    for user in users:
        if not user.color_code:
            continue

        color = hex_to_rgb(user.color_code)

        pill_box = (legend_x + 30, item_y, legend_x + 250, item_y + 40)
        draw_squircle(draw, pill_box, radius=20, fill=(255, 255, 255, 10))

        cx, cy = legend_x + 50, item_y + 20
        r = 8
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color + (255,))
        draw.ellipse(
            [cx - r - 2, cy - r - 2, cx + r + 2, cy + r + 2],
            outline=color + (100,),
            width=2,
        )

        draw.text(
            (legend_x + 80, item_y + 8),
            user.name,
            fill=(255, 255, 255, 220),
            font=legend_font,
        )

        item_y += 55

    # Save to buffer
    output = io.BytesIO()
    bg_img.save(output, format="PNG")
    output.seek(0)

    return BufferedInputFile(output.read(), filename=f"calendar_{year}_{month}.png")


def build_calendar_image_keyboard(
    year: int, month: int, is_history: bool = False
) -> InlineKeyboardMarkup:
    """
    Build simple keyboard for calendar image view (with Edit button).

    Args:
        year: Year
        month: Month
        is_history: Whether this is a historical view

    Returns:
        InlineKeyboardMarkup with navigation and edit button
    """
    builder = InlineKeyboardBuilder()

    # Navigation buttons
    nav_buttons = []

    # Previous month
    prev_month = month - 1
    prev_year = year
    if prev_month < 1:
        prev_month = 12
        prev_year -= 1

    if is_history:
        nav_buttons.append(
            InlineKeyboardButton(
                text="<< Попередній",
                callback_data=f"history_{prev_year}_{prev_month:02d}",
            )
        )
    else:
        nav_buttons.append(
            InlineKeyboardButton(
                text="<< Попередній",
                callback_data=f"calendar_{prev_year}_{prev_month:02d}",
            )
        )

    # Today button (only for current calendar)
    if not is_history:
        today_date = date.today()
        nav_buttons.append(
            InlineKeyboardButton(
                text="📅 Сьогодні",
                callback_data=f"calendar_{today_date.year}_{today_date.month:02d}",
            )
        )

    # Next month
    next_month = month + 1
    next_year = year
    if next_month > 12:
        next_month = 1
        next_year += 1

    if is_history:
        if next_year < date.today().year or (
            next_year == date.today().year and next_month <= date.today().month
        ):
            nav_buttons.append(
                InlineKeyboardButton(
                    text="Наступний >>",
                    callback_data=f"history_{next_year}_{next_month:02d}",
                )
            )
    else:
        nav_buttons.append(
            InlineKeyboardButton(
                text="Наступний >>",
                callback_data=f"calendar_{next_year}_{next_month:02d}",
            )
        )

    builder.row(*nav_buttons)

    # Edit button (only for current calendar, not history)
    if not is_history:
        builder.button(
            text="✏️ Редагувати", callback_data=f"edit_calendar_{year}_{month:02d}"
        )

    return builder.as_markup()
