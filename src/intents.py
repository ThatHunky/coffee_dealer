"""Intent models for natural language commands."""

from typing import Literal, Optional

from pydantic import BaseModel, Field

# Person type for assignments
Person = Literal["diana", "dana", "zhenya"]

# Pattern type for bulk assignments
Pattern = Literal[
    "all_sundays", "all_saturdays", "all_weekends", "whole_month", "all_weekdays"
]


class NLCommand(BaseModel):
    """
    Natural language command parsed by Gemini.

    Actions:
    - show_month: Display calendar for a specific month
    - assign_day: Assign people to a specific day
    - assign_bulk: Assign people to multiple days based on a pattern
    - assign_days: Assign people to multiple specific days (list)
    - who_works: Query who works on a specific day
    - parse_schedule_image: Parse schedule from calendar image
    - help: Show help message
    """

    action: Literal[
        "show_month",
        "assign_day",
        "assign_bulk",
        "assign_days",
        "who_works",
        "parse_schedule_image",
        "help",
    ]
    year: Optional[int] = Field(default=None, description="Year (e.g., 2024)")
    month: Optional[int] = Field(default=None, ge=1, le=12, description="Month (1-12)")
    day: Optional[int] = Field(
        default=None, ge=1, le=31, description="Day of month (1-31)"
    )
    days: list[int] = Field(
        default_factory=list,
        description="List of specific days for multi-day assignment (e.g., [25, 26, 27])",
    )
    people: list[Person] = Field(
        default_factory=list, description="List of people to assign"
    )
    pattern: Optional[Pattern] = Field(
        default=None,
        description="Pattern for bulk assignment: all_sundays, all_saturdays, all_weekends, whole_month, all_weekdays",
    )
    note: str = Field(default="", description="Optional note for the assignment")


class DayAssignment(BaseModel):
    """Single day assignment from image parsing."""

    day: int = Field(description="Day number (1-31)")
    people: list[Person] = Field(description="People assigned to this day")


class ScheduleFromImage(BaseModel):
    """
    Schedule data extracted from calendar image.

    The model expects Gemini to analyze the calendar image and extract:
    - Month name and year
    - All assignments (which person/people work on which days)
    """

    month: int = Field(ge=1, le=12, description="Month number (1-12)")
    year: int = Field(description="Year (e.g., 2024)")
    assignments: list[DayAssignment] = Field(
        default_factory=list,
        description="List of day assignments extracted from the image",
    )
