"""Calendar image renderer with Ukrainian locale."""

import calendar
from datetime import date, timedelta
from io import BytesIO
from typing import Optional

from babel.dates import format_date
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

        # Try to load a font, fallback to default
        try:
            title_font = ImageFont.truetype("arial.ttf", 48)
            header_font = ImageFont.truetype("arial.ttf", 24)
            day_font = ImageFont.truetype("arial.ttf", 20)
            small_font = ImageFont.truetype("arial.ttf", 14)
        except:
            # Fallback to default font
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

                # Draw cell background
                if assignment:
                    color = assignment.get_color()
                    draw.rectangle(
                        [x + 2, y + 2, x + cell_width - 2, y + cell_height - 2],
                        fill=color,
                        outline=self.GRID_COLOR,
                    )
                else:
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

                # Draw names if assigned
                if assignment:
                    names = assignment.get_people_names()
                    names_text = ", ".join(names)
                    draw.text(
                        (x + 10, y + 35),
                        names_text,
                        fill=self.TEXT_COLOR,
                        font=small_font,
                    )

        # Draw legend
        legend_y = self.HEIGHT - self.MARGIN - 120
        draw.text(
            (self.MARGIN, legend_y - 25),
            "Легенда:",
            fill=self.HEADER_COLOR,
            font=header_font,
        )

        legends = [
            ("#4A90E2", "Діана"),
            ("#9B59B6", "Дана"),
            ("#27AE60", "Женя"),
            ("#E91E63", "Діана+Женя"),
            ("#F39C12", "Дана+Женя"),
            ("#E74C3C", "Дана+Діана"),
        ]

        legend_x = self.MARGIN
        for color, label in legends:
            # Draw color box
            draw.rectangle(
                [legend_x, legend_y, legend_x + 30, legend_y + 30],
                fill=color,
                outline=self.GRID_COLOR,
            )

            # Draw label
            draw.text(
                (legend_x + 40, legend_y + 5),
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
