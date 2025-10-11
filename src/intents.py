"""Intent models for natural language commands."""

from typing import Literal, Optional

from pydantic import BaseModel, Field

# Person type for assignments
Person = Literal["diana", "dana", "zhenya"]


class NLCommand(BaseModel):
    """
    Natural language command parsed by Gemini.

    Actions:
    - show_month: Display calendar for a specific month
    - assign_day: Assign people to a specific day
    - who_works: Query who works on a specific day
    - help: Show help message
    """

    action: Literal["show_month", "assign_day", "who_works", "help"]
    year: Optional[int] = Field(default=None, description="Year (e.g., 2024)")
    month: Optional[int] = Field(default=None, ge=1, le=12, description="Month (1-12)")
    day: Optional[int] = Field(
        default=None, ge=1, le=31, description="Day of month (1-31)"
    )
    people: list[Person] = Field(
        default_factory=list, description="List of people to assign"
    )
    note: str = Field(default="", description="Optional note for the assignment")
