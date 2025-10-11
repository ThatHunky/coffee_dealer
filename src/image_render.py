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

        # Emoji font - use Symbola or DejaVu for better emoji support
        # These fonts can render emoji glyphs (monochrome but visible)
        emoji_font_paths = [
            Path("/usr/share/fonts/truetype/ancient-scripts/Symbola_hint.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            Path("/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"),
            Path("/System/Library/Fonts/Apple Color Emoji.ttc"),
            Path("C:/Windows/Fonts/seguiemj.ttf"),
        ]

        self.emoji_font_path = None
        for path in emoji_font_paths:
            if path.exists():
                self.emoji_font_path = path
                logger.info(f"Using emoji font: {path}")
                break

        # Fallback to body font if no emoji font found
        if self.emoji_font_path is None:
            self.emoji_font_path = self.body_font_path
            logger.warning("No emoji font found, using body font as fallback")

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

        # Load fonts with proper Cyrillic support
        try:
            title_font = ImageFont.truetype(str(self.title_font_path), 48)
            header_font = ImageFont.truetype(str(self.header_font_path), 24)
            day_font = ImageFont.truetype(str(self.body_font_path), 20)
            small_font = ImageFont.truetype(str(self.body_font_path), 14)
        except Exception as e:
            # Fallback to default font if custom fonts not available
            print(f"Warning: Could not load custom fonts: {e}")
            title_font = ImageFont.load_default()
            header_font = ImageFont.load_default()
            day_font = ImageFont.load_default()
            small_font = ImageFont.load_default()

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
                    # Draw emoji using emoji font
                    emoji = assignment.get_color()  # Now returns emoji
                    try:
                        # Use dedicated emoji font for proper rendering
                        emoji_font = ImageFont.truetype(str(self.emoji_font_path), 32)
                    except Exception as e:
                        # Fallback to body font if emoji font not available
                        try:
                            emoji_font = ImageFont.truetype(
                                str(self.body_font_path), 32
                            )
                        except Exception:
                            emoji_font = day_font

                    # Draw emoji (without embedded_color for better compatibility)
                    draw.text(
                        (x + cell_width - 45, y + 8),
                        emoji,
                        fill=self.TEXT_COLOR,
                        font=emoji_font,
                    )

                    # Draw names
                    names = assignment.get_people_names()
                    names_text = ", ".join(names)
                    draw.text(
                        (x + 10, y + 45),
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
            # Draw emoji instead of color box using emoji font
            try:
                # Use dedicated emoji font for proper rendering
                emoji_font = ImageFont.truetype(str(self.emoji_font_path), 28)
            except Exception:
                # Fallback to body font
                try:
                    emoji_font = ImageFont.truetype(str(self.body_font_path), 28)
                except Exception:
                    emoji_font = small_font

            # Draw emoji (without embedded_color for better compatibility)
            draw.text(
                (legend_x, legend_y),
                emoji,
                fill=self.TEXT_COLOR,
                font=emoji_font,
            )

            # Draw label
            draw.text(
                (legend_x + 35, legend_y + 5),
                label,
                fill=self.TEXT_COLOR,
                font=small_font,
            )

            legend_x += 200
            if legend_x > self.WIDTH - 200:
                legend_x = self.MARGIN
                legend_y += 40

        # Save to BytesIO
        output = BytesIO()
        img.save(output, format="PNG")
        output.seek(0)

        return output


# Global renderer instance
renderer = CalendarRenderer()
