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


def get_seasonal_gradient(month: int) -> List[Tuple[int, int, int]]:
    """
    Generate seasonal gradient colors based on month.
    
    Args:
        month: Month (1-12)
    
    Returns:
        List of RGB tuples for gradient stops
    """
    # Winter (Dec-Feb): Cool blues and purples
    if month in [12, 1, 2]:
        return [
            (30, 40, 80),   # Deep blue
            (50, 60, 120),  # Medium blue
            (80, 70, 140),  # Purple-blue
            (100, 90, 160), # Light purple
        ]
    # Spring (Mar-May): Fresh greens and pastels
    elif month in [3, 4, 5]:
        return [
            (60, 100, 80),   # Deep green
            (80, 140, 100),  # Medium green
            (120, 180, 140), # Light green
            (160, 200, 180), # Pastel green
        ]
    # Summer (Jun-Aug): Warm oranges and yellows
    elif month in [6, 7, 8]:
        return [
            (180, 100, 40),  # Deep orange
            (220, 140, 60),  # Medium orange
            (240, 180, 100), # Light orange
            (255, 220, 150), # Warm yellow
        ]
    # Autumn (Sep-Nov): Rich oranges, reds, and browns
    else:  # 9, 10, 11
        return [
            (120, 60, 40),   # Deep brown
            (160, 80, 50),   # Medium brown
            (200, 120, 70),  # Orange-brown
            (220, 160, 100), # Light orange
        ]


def create_gradient_background(
    width: int, height: int, colors: List[Tuple[int, int, int]]
) -> Image.Image:
    """
    Create a smooth gradient background.
    
    Args:
        width: Image width
        height: Image height
        colors: List of RGB color tuples for gradient stops
    
    Returns:
        PIL Image with gradient background
    """
    # Create base image
    img = Image.new("RGB", (width, height))
    pixels = img.load()
    
    # Create gradient from top to bottom
    num_stops = len(colors)
    for y in range(height):
        # Calculate which gradient segment we're in
        segment = (y / height) * (num_stops - 1)
        segment_idx = int(segment)
        segment_frac = segment - segment_idx
        
        # Handle edge case
        if segment_idx >= num_stops - 1:
            r, g, b = colors[-1]
        else:
            # Interpolate between two colors
            c1 = colors[segment_idx]
            c2 = colors[segment_idx + 1]
            r = int(c1[0] * (1 - segment_frac) + c2[0] * segment_frac)
            g = int(c1[1] * (1 - segment_frac) + c2[1] * segment_frac)
            b = int(c1[2] * (1 - segment_frac) + c2[2] * segment_frac)
        
        # Fill entire row with this color
        for x in range(width):
            pixels[x, y] = (r, g, b)
    
    return img


def draw_rounded_rectangle(
    draw: ImageDraw.Draw,
    xy: Tuple[int, int, int, int],
    radius: int,
    fill: Optional[Tuple[int, int, int, int]] = None,
    outline: Optional[Tuple[int, int, int, int]] = None,
    width: int = 1,
) -> None:
    """
    Draw a rounded rectangle.
    
    Args:
        draw: ImageDraw instance
        xy: Bounding box (x1, y1, x2, y2)
        radius: Corner radius
        fill: Fill color (RGBA)
        outline: Outline color (RGBA)
        width: Outline width
    """
    x1, y1, x2, y2 = xy
    
    # Ensure radius doesn't exceed half the smallest dimension
    max_radius = min((x2 - x1) // 2, (y2 - y1) // 2)
    radius = min(radius, max_radius)
    
    if fill:
        # Draw main rectangle (center)
        draw.rectangle(
            [x1 + radius, y1, x2 - radius, y2],
            fill=fill,
            outline=None,
        )
        draw.rectangle(
            [x1, y1 + radius, x2, y2 - radius],
            fill=fill,
            outline=None,
        )
        
        # Draw rounded corners
        # Top-left
        draw.ellipse(
            [x1, y1, x1 + 2 * radius, y1 + 2 * radius],
            fill=fill,
            outline=None,
        )
        # Top-right
        draw.ellipse(
            [x2 - 2 * radius, y1, x2, y1 + 2 * radius],
            fill=fill,
            outline=None,
        )
        # Bottom-left
        draw.ellipse(
            [x1, y2 - 2 * radius, x1 + 2 * radius, y2],
            fill=fill,
            outline=None,
        )
        # Bottom-right
        draw.ellipse(
            [x2 - 2 * radius, y2 - 2 * radius, x2, y2],
            fill=fill,
            outline=None,
        )
    
    # Draw outline if specified
    if outline and width > 0:
        # Draw outline using multiple passes for width
        for w in range(width):
            offset = w
            # Top edge
            if y2 - y1 > 2 * (radius - offset):
                draw.rectangle(
                    [x1 + radius - offset, y1 + offset, x2 - radius + offset, y1 + offset + 1],
                    fill=outline,
                    outline=None,
                )
            # Bottom edge
            if y2 - y1 > 2 * (radius - offset):
                draw.rectangle(
                    [x1 + radius - offset, y2 - offset - 1, x2 - radius + offset, y2 - offset],
                    fill=outline,
                    outline=None,
                )
            # Left edge
            if x2 - x1 > 2 * (radius - offset):
                draw.rectangle(
                    [x1 + offset, y1 + radius - offset, x1 + offset + 1, y2 - radius + offset],
                    fill=outline,
                    outline=None,
                )
            # Right edge
            if x2 - x1 > 2 * (radius - offset):
                draw.rectangle(
                    [x2 - offset - 1, y1 + radius - offset, x2 - offset, y2 - radius + offset],
                    fill=outline,
                    outline=None,
                )
            
            # Draw corner arcs using ellipses
            corner_radius = radius - offset
            if corner_radius > 0:
                # Top-left corner
                draw.ellipse(
                    [x1 + offset, y1 + offset, x1 + 2 * corner_radius + offset, y1 + 2 * corner_radius + offset],
                    fill=None,
                    outline=outline,
                    width=1,
                )
                # Top-right corner
                draw.ellipse(
                    [x2 - 2 * corner_radius - offset, y1 + offset, x2 - offset, y1 + 2 * corner_radius + offset],
                    fill=None,
                    outline=outline,
                    width=1,
                )
                # Bottom-left corner
                draw.ellipse(
                    [x1 + offset, y2 - 2 * corner_radius - offset, x1 + 2 * corner_radius + offset, y2 - offset],
                    fill=None,
                    outline=outline,
                    width=1,
                )
                # Bottom-right corner
                draw.ellipse(
                    [x2 - 2 * corner_radius - offset, y2 - 2 * corner_radius - offset, x2 - offset, y2 - offset],
                    fill=None,
                    outline=outline,
                    width=1,
                )


def draw_text_with_glow(
    draw: ImageDraw.Draw,
    text: str,
    position: Tuple[int, int],
    font: ImageFont.FreeTypeFont,
    color: Tuple[int, int, int, int],
    glow_color: Tuple[int, int, int, int],
    glow_radius: int = 3,
) -> None:
    """
    Draw text with glow effect using multiple shadow layers.
    
    Args:
        draw: ImageDraw instance
        text: Text to draw
        position: (x, y) position
        font: Font to use
        color: Text color (RGBA)
        glow_color: Glow color (RGBA)
        glow_radius: Number of glow layers
    """
    x, y = position
    
    # Draw multiple glow layers (outer to inner)
    for i in range(glow_radius, 0, -1):
        alpha = int(glow_color[3] * (0.3 / i))
        glow = (glow_color[0], glow_color[1], glow_color[2], alpha)
        for dx in range(-i, i + 1):
            for dy in range(-i, i + 1):
                if dx * dx + dy * dy <= i * i:
                    draw.text((x + dx, y + dy), text, fill=glow, font=font)
    
    # Draw main text
    draw.text((x, y), text, fill=color, font=font)


def blend_colors_gradient(
    colors: List[str], width: int, height: int
) -> Image.Image:
    """
    Create a diagonal gradient blend for multiple colors.
    
    Args:
        colors: List of hex color codes
        width: Gradient width
        height: Gradient height
    
    Returns:
        PIL Image with blended gradient
    """
    if len(colors) == 1:
        rgb = hex_to_rgb(colors[0])
        return Image.new("RGBA", (width, height), rgb + (255,))
    
    # Create gradient image
    img = Image.new("RGBA", (width, height))
    pixels = img.load()
    
    rgb_colors = [hex_to_rgb(c) for c in colors[:3]]  # Max 3 colors
    
    if len(rgb_colors) == 2:
        # Diagonal gradient from top-left to bottom-right
        for y in range(height):
            for x in range(width):
                # Calculate distance from corners
                dist1 = (x / width + y / height) / 2
                dist2 = 1 - dist1
                
                r = int(rgb_colors[0][0] * dist2 + rgb_colors[1][0] * dist1)
                g = int(rgb_colors[0][1] * dist2 + rgb_colors[1][1] * dist1)
                b = int(rgb_colors[0][2] * dist2 + rgb_colors[1][2] * dist1)
                pixels[x, y] = (r, g, b, 255)
    else:
        # Three-color gradient: top-left, top-right, bottom
        for y in range(height):
            for x in range(width):
                # Calculate barycentric coordinates
                w1 = (1 - x / width) * (1 - y / height)
                w2 = (x / width) * (1 - y / height)
                w3 = y / height
                
                r = int(
                    rgb_colors[0][0] * w1
                    + rgb_colors[1][0] * w2
                    + rgb_colors[2][0] * w3
                )
                g = int(
                    rgb_colors[0][1] * w1
                    + rgb_colors[1][1] * w2
                    + rgb_colors[2][1] * w3
                )
                b = int(
                    rgb_colors[0][2] * w1
                    + rgb_colors[1][2] * w2
                    + rgb_colors[2][2] * w3
                )
                pixels[x, y] = (r, g, b, 255)
    
    return img


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
    # Image dimensions
    cell_size = 90
    header_height = 100
    day_header_height = 50
    padding = 30
    cols = 7
    rows = 6
    legend_item_height = 40
    legend_padding = 15
    legend_cols = 2
    corner_radius = 12

    # Get users first to calculate legend height (exclude hidden users)
    async with async_session_maker() as session:
        users = await get_all_users(session, include_hidden=False)
        num_users = len(users)

    # Legend: 2 columns, calculate rows needed
    legend_rows = (num_users + legend_cols - 1) // legend_cols
    legend_height = (
        legend_rows * legend_item_height + 2 * legend_padding + 50
    )  # Extra space for "Legend" header

    width = cols * cell_size + 2 * padding
    height = (
        header_height
        + day_header_height
        + rows * cell_size
        + 2 * padding
        + legend_height
    )

    # Create dynamic seasonal gradient background
    gradient_colors = get_seasonal_gradient(month)
    bg_img = create_gradient_background(width, height, gradient_colors)
    
    # Apply enhanced blur for glass morphism effect
    bg_img = bg_img.filter(ImageFilter.GaussianBlur(radius=25))
    # Apply multiple blur passes for depth
    bg_img = bg_img.filter(ImageFilter.GaussianBlur(radius=15))
    
    # Enhance brightness and contrast slightly
    enhancer = ImageEnhance.Brightness(bg_img)
    bg_img = enhancer.enhance(1.15)
    enhancer = ImageEnhance.Contrast(bg_img)
    bg_img = enhancer.enhance(1.1)

    # Create multiple glass overlay layers for enhanced glass morphism
    glass_overlay_1 = Image.new("RGBA", (width, height), (255, 255, 255, 20))  # Base layer
    glass_overlay_2 = Image.new("RGBA", (width, height), (255, 255, 255, 10))  # Subtle highlight
    
    # Create main image with background
    img = bg_img.copy()
    
    # Create a transparent layer for calendar content
    calendar_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(calendar_layer)

    # Try to use modern fonts with fallbacks
    font_paths = [
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
    ]
    
    title_font = None
    day_font = None
    number_font = None
    legend_font = None
    legend_title_font = None
    
    for font_path in font_paths:
        try:
            if title_font is None:
                title_font = ImageFont.truetype(font_path, 38)
            if day_font is None:
                day_font = ImageFont.truetype(font_path, 22)
            if number_font is None:
                number_font = ImageFont.truetype(font_path, 28)
            if legend_font is None:
                legend_font = ImageFont.truetype(font_path, 20)
            if legend_title_font is None:
                legend_title_font = ImageFont.truetype(font_path, 24)
            break
        except:
            continue
    
    # Fallback to default fonts
    if title_font is None:
        title_font = ImageFont.load_default()
    if day_font is None:
        day_font = ImageFont.load_default()
    if number_font is None:
        number_font = ImageFont.load_default()
    if legend_font is None:
        legend_font = ImageFont.load_default()
    if legend_title_font is None:
        legend_title_font = ImageFont.load_default()

    # Create users_dict from already loaded users (hidden users already excluded)
    users_dict = {u.user_id: u for u in users}

    # Get shifts data
    async with async_session_maker() as session:
        first_day = date(year, month, 1)
        last_day_num = monthrange(year, month)[1]
        last_day = date(year, month, last_day_num)

        from bot.database.operations import get_shifts_in_range

        shifts = await get_shifts_in_range(session, first_day, last_day)
        shifts_dict = {s.date: s for s in shifts}

    # Draw header with enhanced typography
    month_name_ukr = get_month_name_ukrainian(month)
    header_text = f"{month_name_ukr} {year}"
    if is_history:
        header_text += " (Історія)"

    # Center the header text with enhanced glow effect
    bbox = draw.textbbox((0, 0), header_text, font=title_font)
    text_width = bbox[2] - bbox[0]
    text_x = (width - text_width) // 2
    text_y = padding + 10
    
    # Draw text with glow
    draw_text_with_glow(
        draw,
        header_text,
        (text_x, text_y),
        title_font,
        (255, 255, 255, 255),
        (0, 0, 0, 200),
        glow_radius=4,
    )

    # Draw day headers with enhanced glass effect
    y_start = header_height + padding
    for i, day_abbr in enumerate(UKRAINIAN_DAYS):
        x = padding + i * cell_size
        y = y_start
        
        # Draw rounded header cell with enhanced glass effect
        draw_rounded_rectangle(
            draw,
            (x, y, x + cell_size, y + day_header_height),
            radius=8,
            fill=(255, 255, 255, 40),  # More visible glass
            outline=(255, 255, 255, 150),
            width=2,
        )
        
        # Add glass highlight
        highlight_y = y + 2
        draw.rectangle(
            [x + 2, highlight_y, x + cell_size - 2, highlight_y + 6],
            fill=(255, 255, 255, 60),
        )
        
        # Center text with glow
        bbox = draw.textbbox((0, 0), day_abbr, font=day_font)
        text_width = bbox[2] - bbox[0]
        text_x_pos = x + (cell_size - text_width) // 2
        text_y_pos = y + (day_header_height - (bbox[3] - bbox[1])) // 2
        
        draw_text_with_glow(
            draw,
            day_abbr,
            (text_x_pos, text_y_pos),
            day_font,
            (255, 255, 255, 240),
            (0, 0, 0, 120),
            glow_radius=2,
        )

    # Draw calendar grid with enhanced cells
    first_weekday = first_day.weekday()  # 0=Monday
    today = date.today()
    y_start += day_header_height

    day_num = 1
    for row in range(rows):
        for col in range(cols):
            x = padding + col * cell_size
            y = y_start + row * cell_size

            if row == 0 and col < first_weekday:
                # Empty cell before month starts - subtle pattern
                draw_rounded_rectangle(
                    draw,
                    (x, y, x + cell_size, y + cell_size),
                    radius=corner_radius,
                    fill=(255, 255, 255, 15),
                    outline=(255, 255, 255, 40),
                    width=1,
                )
                # Add subtle diagonal pattern
                for i in range(0, cell_size, 8):
                    draw.line(
                        [(x + i, y), (x, y + i)],
                        fill=(255, 255, 255, 10),
                        width=1,
                    )
                continue

            if day_num > last_day_num:
                # Empty cell after month ends - subtle pattern
                draw_rounded_rectangle(
                    draw,
                    (x, y, x + cell_size, y + cell_size),
                    radius=corner_radius,
                    fill=(255, 255, 255, 15),
                    outline=(255, 255, 255, 40),
                    width=1,
                )
                # Add subtle diagonal pattern
                for i in range(0, cell_size, 8):
                    draw.line(
                        [(x + i, y), (x, y + i)],
                        fill=(255, 255, 255, 10),
                        width=1,
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

            # Create cell background with enhanced color blending
            if colors:
                # Create gradient blend for multiple colors
                if len(colors) > 1:
                    color_gradient = blend_colors_gradient(colors, cell_size, cell_size)
                    # Apply saturation boost
                    enhancer = ImageEnhance.Color(color_gradient)
                    color_gradient = enhancer.enhance(1.2)
                    # Make semi-transparent (~85% opacity)
                    alpha = color_gradient.split()[3]
                    # Adjust alpha channel using point() method
                    alpha = alpha.point(lambda p: int(p * 0.85))
                    color_gradient.putalpha(alpha)
                    
                    # Paste gradient onto calendar layer
                    calendar_layer.paste(color_gradient, (x, y), color_gradient)
                    bg_rgb = hex_to_rgb(colors[0])  # For text color calculation
                else:
                    bg_rgb = hex_to_rgb(colors[0])
                    # Enhance saturation
                    r, g, b = bg_rgb
                    # Boost saturation
                    max_val = max(r, g, b)
                    if max_val > 0:
                        r = min(255, int(r * 1.15))
                        g = min(255, int(g * 1.15))
                        b = min(255, int(b * 1.15))
                    bg_rgb = (r, g, b)
                    bg_color = bg_rgb + (215,)  # Semi-transparent with glass effect
                    
                    # Draw rounded cell
                    draw_rounded_rectangle(
                        draw,
                        (x, y, x + cell_size, y + cell_size),
                        radius=corner_radius,
                        fill=bg_color,
                        outline=(255, 255, 255, 150),
                        width=2,
                    )
            else:
                # Empty cell - subtle glass effect
                bg_rgb = (200, 200, 200)
                bg_color = (255, 255, 255, 50)
                draw_rounded_rectangle(
                    draw,
                    (x, y, x + cell_size, y + cell_size),
                    radius=corner_radius,
                    fill=bg_color,
                    outline=(255, 255, 255, 60),
                    width=1,
                )

            # Add enhanced glass highlights and shadows
            if colors:
                # Top highlight
                highlight_y = y + 2
                draw.rectangle(
                    [x + 3, highlight_y, x + cell_size - 3, highlight_y + 8],
                    fill=(255, 255, 255, 50),
                )
                
                # Bottom shadow for depth
                shadow_y = y + cell_size - 4
                draw.rectangle(
                    [x + 3, shadow_y, x + cell_size - 3, y + cell_size - 1],
                    fill=(0, 0, 0, 30),
                )
                
                # Left highlight
                draw.rectangle(
                    [x + 2, y + 3, x + 6, y + cell_size - 3],
                    fill=(255, 255, 255, 40),
                )

            # Enhanced "today" highlight with glow effect
            if current_date == today and not is_history:
                # Multiple glow layers for pulsing effect
                glow_colors = [
                    (0, 255, 100, 180),  # Outer glow
                    (0, 255, 120, 140),  # Mid glow
                    (0, 255, 140, 100),  # Inner glow
                ]
                
                for i, glow_color in enumerate(glow_colors):
                    offset = 2 + i * 2
                    draw_rounded_rectangle(
                        draw,
                        (
                            x - offset,
                            y - offset,
                            x + cell_size + offset,
                            y + cell_size + offset,
                        ),
                        radius=corner_radius + offset,
                        fill=None,
                        outline=glow_color,
                        width=3 - i,
                    )
                
                # Inner highlight ring
                draw_rounded_rectangle(
                    draw,
                    (x + 4, y + 4, x + cell_size - 4, y + cell_size - 4),
                    radius=corner_radius - 2,
                    fill=None,
                    outline=(0, 255, 150, 200),
                    width=2,
                )

            # Draw day number with enhanced typography
            day_str = str(day_num)
            bbox = draw.textbbox((0, 0), day_str, font=number_font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            text_x_pos = x + (cell_size - text_width) // 2
            text_y_pos = y + (cell_size - text_height) // 2

            # Determine text color based on background brightness
            if colors:
                brightness = sum(bg_rgb) / 3
                if brightness > 140:
                    text_color = (20, 20, 20, 255)
                    glow_color = (255, 255, 255, 180)
                else:
                    text_color = (255, 255, 255, 255)
                    glow_color = (0, 0, 0, 180)
            else:
                text_color = (255, 255, 255, 255)
                glow_color = (0, 0, 0, 150)

            # Draw text with glow
            draw_text_with_glow(
                draw,
                day_str,
                (text_x_pos, text_y_pos),
                number_font,
                text_color,
                glow_color,
                glow_radius=3,
            )

            # Draw user indicators (enhanced dots for multiple users)
            if len(colors) > 1:
                dot_size = 7
                dot_spacing = 10
                start_x = x + cell_size - 12
                start_y = y + 8
                for i, color in enumerate(colors[:3]):  # Max 3 dots
                    dot_rgb = hex_to_rgb(color)
                    # Enhance dot color
                    dot_rgb = tuple(min(255, int(c * 1.2)) for c in dot_rgb)
                    dot_color = dot_rgb + (240,)
                    dot_y = start_y + i * dot_spacing
                    
                    # Draw dot with glow
                    draw.ellipse(
                        [
                            start_x - dot_size,
                            dot_y,
                            start_x,
                            dot_y + dot_size,
                        ],
                        fill=dot_color,
                        outline=(255, 255, 255, 200),
                        width=2,
                    )
                    # Add inner highlight
                    draw.ellipse(
                        [
                            start_x - dot_size + 2,
                            dot_y + 2,
                            start_x - 2,
                            dot_y + dot_size - 2,
                        ],
                        fill=(255, 255, 255, 100),
                    )

            day_num += 1

    # Draw enhanced legend with modern card design
    legend_y_start = (
        header_height + day_header_height + rows * cell_size + 2 * padding + 20
    )
    legend_x_start = padding

    # Draw legend title with enhanced typography
    legend_title = "Легенда:"
    bbox = draw.textbbox((0, 0), legend_title, font=legend_title_font)
    text_x_pos = legend_x_start
    text_y_pos = legend_y_start
    
    draw_text_with_glow(
        draw,
        legend_title,
        (text_x_pos, text_y_pos),
        legend_title_font,
        (255, 255, 255, 255),
        (0, 0, 0, 180),
        glow_radius=3,
    )
    legend_y_start += 40

    # Draw legend items with modern card design
    legend_item_width = (width - 2 * padding - 10) // legend_cols
    for idx, user in enumerate(users):
        col = idx % legend_cols
        row = idx // legend_cols

        card_x = legend_x_start + col * (legend_item_width + 10)
        card_y = legend_y_start + row * (legend_item_height + 8)

        # Draw glass morphism card background
        draw_rounded_rectangle(
            draw,
            (
                card_x,
                card_y,
                card_x + legend_item_width,
                card_y + legend_item_height,
            ),
            radius=10,
            fill=(255, 255, 255, 30),
            outline=(255, 255, 255, 100),
            width=2,
        )
        
        # Add card highlight
        draw.rectangle(
            [card_x + 2, card_y + 2, card_x + legend_item_width - 2, card_y + 6],
            fill=(255, 255, 255, 40),
        )

        # Draw enhanced color swatch
        color_box_size = 28
        color_x = card_x + 12
        color_y = card_y + (legend_item_height - color_box_size) // 2

        if user.color_code:
            color_rgb = hex_to_rgb(user.color_code)
            # Enhance saturation
            color_rgb = tuple(min(255, int(c * 1.15)) for c in color_rgb)
            color_with_alpha = color_rgb + (240,)
        else:
            color_rgb = (128, 128, 128)
            color_with_alpha = color_rgb + (240,)

        # Draw rounded color box with gradient effect
        draw_rounded_rectangle(
            draw,
            (
                color_x,
                color_y,
                color_x + color_box_size,
                color_y + color_box_size,
            ),
            radius=6,
            fill=color_with_alpha,
            outline=(255, 255, 255, 220),
            width=2,
        )
        
        # Add highlight to color box
        draw.rectangle(
            [
                color_x + 2,
                color_y + 2,
                color_x + color_box_size - 2,
                color_y + 6,
            ],
            fill=(255, 255, 255, 80),
        )

        # Draw user name with enhanced typography
        name_text = user.name
        text_x_pos = color_x + color_box_size + 12
        text_y_pos = card_y + (legend_item_height - 20) // 2

        # Truncate name if too long
        max_width = legend_item_width - color_box_size - 30
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

        # Draw text with glow
        draw_text_with_glow(
            draw,
            name_text,
            (text_x_pos, text_y_pos),
            legend_font,
            (255, 255, 255, 255),
            (0, 0, 0, 150),
            glow_radius=2,
        )

    # Composite all layers: background -> glass overlays -> calendar content
    # Start with background (convert to RGBA for compositing)
    final_img = bg_img.convert("RGBA")
    
    # Apply glass overlays
    final_img = Image.alpha_composite(final_img, glass_overlay_1)
    final_img = Image.alpha_composite(final_img, glass_overlay_2)
    
    # Add calendar content layer
    final_img = Image.alpha_composite(final_img, calendar_layer)
    
    # Convert back to RGB for final output
    rgb_img = Image.new("RGB", (width, height), (0, 0, 0))
    rgb_img.paste(final_img, mask=final_img.split()[3])
    final_img = rgb_img

    # Convert to bytes
    img_buffer = io.BytesIO()
    final_img.save(img_buffer, format="PNG", optimize=True)
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
