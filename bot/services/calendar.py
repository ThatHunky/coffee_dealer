"""Calendar rendering service"""

import io
import os
from datetime import date, datetime, timedelta
from typing import List, Dict, Optional, Tuple
from calendar import monthrange, month_name
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

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
        button_text = f"{emoji} {day}"

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
    Generate a calendar image with colored days.

    Args:
        year: Year
        month: Month (1-12)
        is_history: Whether this is a historical view

    Returns:
        BufferedInputFile with the calendar image
    """
    # Image dimensions
    cell_size = 80
    header_height = 80
    day_header_height = 40
    padding = 20
    cols = 7
    rows = 6
    legend_item_height = 30
    legend_padding = 10
    legend_cols = 2

    # Get users first to calculate legend height (exclude hidden users)
    async with async_session_maker() as session:
        users = await get_all_users(session, include_hidden=False)
        num_users = len(users)

    # Legend: 2 columns, calculate rows needed
    legend_rows = (num_users + legend_cols - 1) // legend_cols
    legend_height = (
        legend_rows * legend_item_height + 2 * legend_padding + 40
    )  # Extra space for "Legend" header

    width = cols * cell_size + 2 * padding
    height = (
        header_height
        + day_header_height
        + rows * cell_size
        + 2 * padding
        + legend_height
    )

    # Load and prepare background image
    # Get project root (two levels up from bot/services/calendar.py)
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    bg_path = os.path.join(project_root, "assets", "coffee_dealer_bg.jpg")
    try:
        bg_img = Image.open(bg_path)
        # Convert to RGB if needed
        if bg_img.mode != "RGB":
            bg_img = bg_img.convert("RGB")
        # Resize/crop background to match calendar dimensions
        bg_img = bg_img.resize((width, height), Image.Resampling.LANCZOS)
        # Apply blur for glass effect
        bg_img = bg_img.filter(ImageFilter.GaussianBlur(radius=18))
        # Slightly increase brightness for better glass effect
        enhancer = ImageEnhance.Brightness(bg_img)
        bg_img = enhancer.enhance(1.1)
    except Exception as e:
        # Fallback to dark background if image can't be loaded
        print(f"Warning: Could not load background image: {e}")
        bg_img = Image.new("RGB", (width, height), color="#1e1e1e")

    # Create glass overlay layer (semi-transparent white)
    glass_overlay = Image.new("RGBA", (width, height), (255, 255, 255, 15))  # 15/255 ~6% opacity
    
    # Create main image with background
    img = bg_img.copy()
    
    # Create a transparent layer for calendar content
    calendar_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(calendar_layer)

    # Try to use a nice font, fallback to default
    try:
        title_font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 32
        )
        day_font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20
        )
        number_font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24
        )
        legend_font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 18
        )
        legend_title_font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22
        )
    except:
        title_font = ImageFont.load_default()
        day_font = ImageFont.load_default()
        number_font = ImageFont.load_default()
        legend_font = ImageFont.load_default()
        legend_title_font = ImageFont.load_default()

    # Create users_dict from already loaded users (hidden users already excluded)
    users_dict = {u.user_id: u for u in users}
    
    # Filter out hidden users from shifts when displaying
    # (users_dict only contains visible users, so hidden users won't appear)

    # Get shifts data
    async with async_session_maker() as session:
        first_day = date(year, month, 1)
        last_day_num = monthrange(year, month)[1]
        last_day = date(year, month, last_day_num)

        from bot.database.operations import get_shifts_in_range

        shifts = await get_shifts_in_range(session, first_day, last_day)
        shifts_dict = {s.date: s for s in shifts}

    # Draw header
    month_name_ukr = get_month_name_ukrainian(month)
    header_text = f"{month_name_ukr} {year}"
    if is_history:
        header_text += " (Історія)"

    # Center the header text with shadow for readability on glass
    bbox = draw.textbbox((0, 0), header_text, font=title_font)
    text_width = bbox[2] - bbox[0]
    text_x = (width - text_width) // 2
    # Draw text shadow
    draw.text((text_x + 2, padding + 2), header_text, fill=(0, 0, 0, 150), font=title_font)
    # Draw text
    draw.text((text_x, padding), header_text, fill=(255, 255, 255, 255), font=title_font)

    # Draw day headers
    y_start = header_height + padding
    for i, day_abbr in enumerate(UKRAINIAN_DAYS):
        x = padding + i * cell_size
        y = y_start
        # Draw header cell with glass effect
        # Semi-transparent background
        draw.rectangle(
            [x, y, x + cell_size, y + day_header_height], 
            fill=(255, 255, 255, 30),  # Semi-transparent white
            outline=(255, 255, 255, 100),  # Semi-transparent border
            width=2
        )
        # Center text with shadow
        bbox = draw.textbbox((0, 0), day_abbr, font=day_font)
        text_width = bbox[2] - bbox[0]
        text_x = x + (cell_size - text_width) // 2
        text_y = y + (day_header_height - (bbox[3] - bbox[1])) // 2
        # Text shadow
        draw.text((text_x + 1, text_y + 1), day_abbr, fill=(0, 0, 0, 100), font=day_font)
        # Text
        draw.text((text_x, text_y), day_abbr, fill=(255, 255, 255, 220), font=day_font)

    # Draw calendar grid
    first_weekday = first_day.weekday()  # 0=Monday
    today = date.today()
    y_start += day_header_height

    day_num = 1
    for row in range(rows):
        for col in range(cols):
            x = padding + col * cell_size
            y = y_start + row * cell_size

            if row == 0 and col < first_weekday:
                # Empty cell before month starts (transparent)
                draw.rectangle(
                    [x, y, x + cell_size, y + cell_size], 
                    fill=(0, 0, 0, 0),
                    outline=(255, 255, 255, 30), 
                    width=1
                )
                continue

            if day_num > last_day_num:
                # Empty cell after month ends (transparent)
                draw.rectangle(
                    [x, y, x + cell_size, y + cell_size], 
                    fill=(0, 0, 0, 0),
                    outline=(255, 255, 255, 30), 
                    width=1
                )
                continue

            current_date = date(year, month, day_num)

            # Get shift for this day
            shift = shifts_dict.get(current_date)
            user_ids = shift.user_ids if shift else []

            # Get colors for users
            colors = []
            for user_id in user_ids:
                user = users_dict.get(user_id)
                if user and user.color_code:
                    colors.append(user.color_code)

            # Draw cell background with glass effect
            if colors:
                # Use first color, or blend if multiple
                if len(colors) == 1:
                    bg_rgb = hex_to_rgb(colors[0])
                else:
                    # Blend colors (simple average)
                    rgb_colors = [hex_to_rgb(c) for c in colors[:3]]  # Max 3 colors
                    bg_rgb = tuple(
                        sum(c[i] for c in rgb_colors) // len(rgb_colors)
                        for i in range(3)
                    )
                # Semi-transparent color with glass effect (alpha ~200/255 ~78%)
                bg_color = bg_rgb + (200,)
            else:
                # Empty cell - very transparent white
                bg_color = (255, 255, 255, 40)  # Very transparent white

            # Draw cell with glass effect
            draw.rectangle(
                [x, y, x + cell_size, y + cell_size],
                fill=bg_color,
                outline=(255, 255, 255, 120),  # Semi-transparent white border
                width=2,
            )
            
            # Add glass highlight on top-left edge
            highlight_points = [
                (x + 2, y + 2),
                (x + cell_size - 2, y + 2),
                (x + cell_size - 2, y + 8),
                (x + 2, y + 8),
            ]
            draw.polygon(highlight_points, fill=(255, 255, 255, 40))

            # Highlight today with glass effect
            if current_date == today and not is_history:
                # Draw glowing border highlight
                draw.rectangle(
                    [x + 1, y + 1, x + cell_size - 1, y + cell_size - 1],
                    outline=(0, 255, 0, 200),  # Semi-transparent green
                    width=3,
                )
                # Add inner glow
                draw.rectangle(
                    [x + 3, y + 3, x + cell_size - 3, y + cell_size - 3],
                    outline=(0, 255, 0, 100),
                    width=1,
                )

            # Draw day number
            day_str = str(day_num)
            bbox = draw.textbbox((0, 0), day_str, font=number_font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            text_x = x + (cell_size - text_width) // 2
            text_y = y + (cell_size - text_height) // 2

            # Use white or black text with shadow for readability on glass
            if colors:
                brightness = sum(bg_rgb) / 3
                if brightness > 128:
                    # Light background - use dark text with shadow
                    text_color = (0, 0, 0, 255)
                    shadow_color = (255, 255, 255, 150)
                else:
                    # Dark background - use light text with shadow
                    text_color = (255, 255, 255, 255)
                    shadow_color = (0, 0, 0, 150)
            else:
                text_color = (255, 255, 255, 255)
                shadow_color = (0, 0, 0, 150)

            # Draw text shadow
            draw.text((text_x + 1, text_y + 1), day_str, fill=shadow_color, font=number_font)
            # Draw text
            draw.text((text_x, text_y), day_str, fill=text_color, font=number_font)

            # Draw user indicators (small dots for multiple users) with glass effect
            if len(colors) > 1:
                dot_size = 6
                dot_spacing = 8
                start_x = x + cell_size - 10
                start_y = y + 5
                for i, color in enumerate(colors[:3]):  # Max 3 dots
                    dot_rgb = hex_to_rgb(color)
                    dot_color = dot_rgb + (220,)  # Semi-transparent
                    dot_y = start_y + i * dot_spacing
                    draw.ellipse(
                        [start_x - dot_size, dot_y, start_x, dot_y + dot_size],
                        fill=dot_color,
                        outline=(255, 255, 255, 180),
                        width=1,
                    )

            day_num += 1

    # Draw legend
    legend_y_start = (
        header_height + day_header_height + rows * cell_size + 2 * padding + 10
    )
    legend_x_start = padding

    # Draw legend title with glass effect
    legend_title = "Легенда:"
    bbox = draw.textbbox((0, 0), legend_title, font=legend_title_font)
    # Text shadow
    draw.text(
        (legend_x_start + 1, legend_y_start + 1),
        legend_title,
        fill=(0, 0, 0, 150),
        font=legend_title_font,
    )
    # Text
    draw.text(
        (legend_x_start, legend_y_start),
        legend_title,
        fill=(255, 255, 255, 255),
        font=legend_title_font,
    )
    legend_y_start += 30

    # Draw legend items
    legend_item_width = (width - 2 * padding) // legend_cols
    for idx, user in enumerate(users):
        col = idx % legend_cols
        row = idx // legend_cols

        x = legend_x_start + col * legend_item_width
        y = legend_y_start + row * legend_item_height

        # Draw color box
        color_box_size = 20
        color_x = x
        color_y = y + (legend_item_height - color_box_size) // 2

        if user.color_code:
            color_rgb = hex_to_rgb(user.color_code)
            color_with_alpha = color_rgb + (220,)  # Semi-transparent
        else:
            color_rgb = (128, 128, 128)  # Grey for no color
            color_with_alpha = color_rgb + (220,)

        # Draw color box with glass effect
        draw.rectangle(
            [color_x, color_y, color_x + color_box_size, color_y + color_box_size],
            fill=color_with_alpha,
            outline=(255, 255, 255, 200),
            width=1,
        )
        # Add highlight
        draw.rectangle(
            [color_x + 1, color_y + 1, color_x + color_box_size - 1, color_y + 3],
            fill=(255, 255, 255, 60),
        )

        # Draw user name with shadow for readability
        name_text = user.name
        text_x = color_x + color_box_size + 8
        text_y = y + (legend_item_height - 18) // 2  # Approximate text height

        # Truncate name if too long
        max_width = legend_item_width - color_box_size - 20
        name_bbox = draw.textbbox((0, 0), name_text, font=legend_font)
        if name_bbox[2] - name_bbox[0] > max_width:
            # Truncate with ellipsis
            while len(name_text) > 1:
                test_text = name_text + "..."
                test_bbox = draw.textbbox((0, 0), test_text, font=legend_font)
                if test_bbox[2] - test_bbox[0] <= max_width:
                    name_text = test_text
                    break
                name_text = name_text[:-1]
            if not name_text.endswith("..."):
                name_text = name_text[: max(1, len(name_text) - 3)] + "..."

        # Text shadow
        draw.text((text_x + 1, text_y + 1), name_text, fill=(0, 0, 0, 150), font=legend_font)
        # Text
        draw.text((text_x, text_y), name_text, fill=(255, 255, 255, 255), font=legend_font)

    # Composite all layers: background -> glass overlay -> calendar content
    # Start with background (convert to RGBA for compositing)
    final_img = bg_img.convert("RGBA")
    
    # Apply glass overlay
    final_img = Image.alpha_composite(final_img, glass_overlay)
    
    # Add calendar content layer
    final_img = Image.alpha_composite(final_img, calendar_layer)
    
    # Convert back to RGB for final output
    # Paste onto the blurred background to preserve the glass effect
    rgb_img = bg_img.copy()
    rgb_img.paste(final_img, mask=final_img.split()[3])  # Use alpha channel as mask
    final_img = rgb_img

    # Convert to bytes
    img_buffer = io.BytesIO()
    final_img.save(img_buffer, format="PNG")
    img_buffer.seek(0)

    return BufferedInputFile(
        img_buffer.read(), filename=f"calendar_{year}_{month:02d}.png"
    )


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
