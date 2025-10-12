"""Calendar image renderer with Ukrainian locale."""

import calendar
import os
from datetime import date, timedelta
from io import BytesIO
from pathlib import Path
from typing import Optional

from babel.dates import format_date
from loguru import logger
from PIL import Image, ImageDraw, ImageFont
from pilmoji import Pilmoji

from .models import Assignment
from .repo import repo


class CalendarRenderer:
    """Renders monthly calendar as PNG image with Ukrainian text."""

    # Image dimensions
    WIDTH = 1200
    HEIGHT = 1000
    MARGIN = 40

    # Colors
    BG_COLOR = "#FFFFFF"
    TEXT_COLOR = "#333333"
    HEADER_COLOR = "#2C3E50"
    GRID_COLOR = "#BDC3C7"
    TODAY_BORDER = "#E74C3C"

    def __init__(self):
        """Initialize renderer."""
        # Set Monday as first day of week
        calendar.setfirstweekday(calendar.MONDAY)

        # Get font paths
        self.font_dir = Path(__file__).parent.parent / "fonts"
        self.title_font_path = self.font_dir / "Roboto-Bold.ttf"
        self.header_font_path = self.font_dir / "Roboto-Medium.ttf"
        self.body_font_path = self.font_dir / "Roboto-Regular.ttf"

        # Emoji font path preference (Pilmoji can handle color emoji fonts)
        emoji_font_paths = [
            Path("/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"),
            Path("/System/Library/Fonts/Apple Color Emoji.ttc"),
            Path("C:/Windows/Fonts/seguiemj.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            Path("/usr/share/fonts/truetype/ancient-scripts/Symbola_hint.ttf"),
        ]

        self.emoji_font_path = None
        for path in emoji_font_paths:
            if path.exists():
                self.emoji_font_path = path
                logger.info(f"Using emoji font: {path}")
                break

        if self.emoji_font_path is None:
            logger.warning("No emoji font found; Pilmoji will use default fallback")

    def render(
        self, year: int, month: int, assignments: Optional[list[Assignment]] = None
    ) -> BytesIO:
        """
        Render calendar for the given month.

        Args:
            year: Year (e.g., 2024)
            month: Month (1-12)
            assignments: Optional list of assignments (fetched if not provided)

        Returns:
            BytesIO containing PNG image
        """
        if assignments is None:
            assignments = repo.get_month(year, month)

        # Create assignment lookup
        assignment_map = {a.day: a for a in assignments}

        # Create image
        img = Image.new("RGB", (self.WIDTH, self.HEIGHT), self.BG_COLOR)
        draw = ImageDraw.Draw(img)
        pilmoji = Pilmoji(img)

        # Load fonts with proper Cyrillic support
        # Try custom Roboto fonts first, then fallback to DejaVu Sans (has Cyrillic)
        fallback_font_paths = [
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
            Path("/System/Library/Fonts/Helvetica.ttc"),
            Path("C:/Windows/Fonts/arial.ttf"),
        ]

        # Find a fallback font with Cyrillic support
        fallback_font = None
        for fpath in fallback_font_paths:
            if fpath.exists():
                fallback_font = fpath
                logger.info(f"Found fallback font: {fpath}")
                break

        try:
            # Try Roboto fonts for text
            if self.title_font_path.exists():
                title_font = ImageFont.truetype(str(self.title_font_path), 48)
            else:
                title_font = (
                    ImageFont.truetype(str(fallback_font), 48)
                    if fallback_font
                    else ImageFont.load_default()
                )
                logger.warning(f"Title font not found, using fallback")

            if self.header_font_path.exists():
                header_font = ImageFont.truetype(str(self.header_font_path), 24)
            else:
                header_font = (
                    ImageFont.truetype(str(fallback_font), 24)
                    if fallback_font
                    else ImageFont.load_default()
                )
                logger.warning(f"Header font not found, using fallback")

            if self.body_font_path.exists():
                day_font = ImageFont.truetype(str(self.body_font_path), 20)
                small_font = ImageFont.truetype(str(self.body_font_path), 14)
            else:
                day_font = (
                    ImageFont.truetype(str(fallback_font), 20)
                    if fallback_font
                    else ImageFont.load_default()
                )
                small_font = (
                    ImageFont.truetype(str(fallback_font), 14)
                    if fallback_font
                    else ImageFont.load_default()
                )
                logger.warning(f"Body font not found, using fallback")

            # Emoji font: NotoColorEmoji is a bitmap font with fixed sizes (16, 24, 32, 48, 64, 72, 96, 109, 128)
            # Use closest supported sizes: 48 for cells, 32 for legend
            if self.emoji_font_path:
                try:
                    emoji_cell_font = ImageFont.truetype(str(self.emoji_font_path), 48)
                    emoji_legend_font = ImageFont.truetype(
                        str(self.emoji_font_path), 32
                    )
                except Exception as e:
                    logger.warning(f"Could not load emoji font with bitmap sizes: {e}")
                    # Fallback to text font for emoji
                    emoji_cell_font = ImageFont.truetype(
                        str(
                            self.body_font_path
                            if self.body_font_path.exists()
                            else fallback_font
                        ),
                        48,
                    )
                    emoji_legend_font = ImageFont.truetype(
                        str(
                            self.body_font_path
                            if self.body_font_path.exists()
                            else fallback_font
                        ),
                        32,
                    )
            else:
                # If no emoji font, use Roboto/fallback for emoji too
                emoji_cell_font = ImageFont.truetype(
                    str(
                        self.body_font_path
                        if self.body_font_path.exists()
                        else fallback_font
                    ),
                    48,
                )
                emoji_legend_font = ImageFont.truetype(
                    str(
                        self.body_font_path
                        if self.body_font_path.exists()
                        else fallback_font
                    ),
                    32,
                )

        except Exception as e:
            # Last resort: use fallback font or default
            logger.error(f"Error loading fonts: {e}", exc_info=True)
            if fallback_font:
                title_font = ImageFont.truetype(str(fallback_font), 48)
                header_font = ImageFont.truetype(str(fallback_font), 24)
                day_font = ImageFont.truetype(str(fallback_font), 20)
                small_font = ImageFont.truetype(str(fallback_font), 14)
                emoji_cell_font = ImageFont.truetype(str(fallback_font), 48)
                emoji_legend_font = ImageFont.truetype(str(fallback_font), 32)
            else:
                title_font = ImageFont.load_default()
                header_font = ImageFont.load_default()
                day_font = ImageFont.load_default()
                small_font = ImageFont.load_default()
                emoji_cell_font = day_font
                emoji_legend_font = small_font

        # Draw title (month name in Ukrainian)
        month_name = format_date(date(year, month, 1), "LLLL yyyy", locale="uk")
        month_name = month_name.capitalize()

        title_bbox = draw.textbbox((0, 0), month_name, font=title_font)
        title_width = title_bbox[2] - title_bbox[0]
        title_x = (self.WIDTH - title_width) // 2
        draw.text(
            (title_x, self.MARGIN), month_name, fill=self.HEADER_COLOR, font=title_font
        )

        # Calculate grid dimensions
        grid_top = self.MARGIN + 80
        grid_height = self.HEIGHT - grid_top - self.MARGIN - 150  # Space for legend
        cell_width = (self.WIDTH - 2 * self.MARGIN) // 7
        cell_height = grid_height // 6

        # Draw day headers (Mon-Sun in Ukrainian)
        day_names = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"]
        for i, day_name in enumerate(day_names):
            x = self.MARGIN + i * cell_width + cell_width // 2
            y = grid_top

            bbox = draw.textbbox((0, 0), day_name, font=header_font)
            text_width = bbox[2] - bbox[0]
            draw.text(
                (x - text_width // 2, y),
                day_name,
                fill=self.HEADER_COLOR,
                font=header_font,
            )

        # Get calendar for month
        cal = calendar.monthcalendar(year, month)

        # Draw calendar grid
        grid_start = grid_top + 40
        today = date.today()

        for week_idx, week in enumerate(cal):
            for day_idx, day_num in enumerate(week):
                if day_num == 0:
                    continue

                current_date = date(year, month, day_num)
                x = self.MARGIN + day_idx * cell_width
                y = grid_start + week_idx * cell_height

                # Get assignment for this day
                assignment = assignment_map.get(current_date)

                # Draw cell border
                draw.rectangle(
                    [x, y, x + cell_width, y + cell_height], outline=self.GRID_COLOR
                )

                # Highlight today
                if current_date == today:
                    draw.rectangle(
                        [x, y, x + cell_width, y + cell_height],
                        outline=self.TODAY_BORDER,
                        width=3,
                    )

                # Draw day number
                day_text = str(day_num)
                bbox = draw.textbbox((0, 0), day_text, font=day_font)
                text_width = bbox[2] - bbox[0]
                draw.text(
                    (x + 10, y + 10), day_text, fill=self.TEXT_COLOR, font=day_font
                )

                # Draw emoji and names if assigned
                if assignment:
                    # Draw emoji using Pilmoji (color emoji support)
                    emoji = assignment.get_color()
                    # Center the emoji horizontally in the cell, near the top, with more vertical space
                    emoji_x = x + (cell_width // 2)
                    emoji_y = y + 18  # move emoji a bit lower for balance
                    pilmoji.text(
                        (
                            emoji_x - 24,
                            emoji_y,
                        ),  # 24 = half of font size 48 for centering
                        emoji,
                        fill=self.TEXT_COLOR,
                        font=emoji_cell_font,
                    )

                    # Draw names, further below emoji for clarity
                    names = assignment.get_people_names()
                    names_text = ", ".join(names)
                    name_y = emoji_y + 48  # 48px below emoji top
                    draw.text(
                        (x + 10, name_y),
                        names_text,
                        fill=self.TEXT_COLOR,
                        font=small_font,
                    )

        # Draw legend (dynamic from user config with emojis)
        from .user_manager import user_manager

        legend_y = self.HEIGHT - self.MARGIN - 120
        draw.text(
            (self.MARGIN, legend_y - 25),
            "Легенда:",
            fill=self.HEADER_COLOR,
            font=header_font,
        )

        # Get dynamic legend from user manager (now returns emojis instead of colors)
        legends = user_manager.get_all_colors_legend()

        legend_x = self.MARGIN
        for emoji, label in legends:
            # Use Pilmoji for legend emojis too, larger font
            pilmoji.text(
                (legend_x, legend_y - 2),  # slightly higher for better alignment
                emoji,
                fill=self.TEXT_COLOR,
                font=emoji_legend_font,
            )

            # Draw label, more spacing from emoji, vertically centered
            draw.text(
                (legend_x + 62, legend_y + 10),
                label,
                fill=self.TEXT_COLOR,
                font=small_font,
            )

            legend_x += 270
            if legend_x > self.WIDTH - 270:
                legend_x = self.MARGIN
                legend_y += 60

        # Save to BytesIO
        output = BytesIO()
        img.save(output, format="PNG")
        output.seek(0)

        return output


# Global renderer instance
renderer = CalendarRenderer()
