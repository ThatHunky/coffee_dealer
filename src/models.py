"""Data models for schedule assignments."""

from datetime import date
from typing import Optional

from sqlmodel import Field, SQLModel


class Assignment(SQLModel, table=True):
    """
    Schedule assignment using bitmask for people.

    Bitmask values:
    - 1 (0b001) = Diana
    - 2 (0b010) = Dana
    - 4 (0b100) = Zhenya

    Combinations:
    - 3 (0b011) = Diana + Dana (red)
    - 5 (0b101) = Diana + Zhenya (pink)
    - 6 (0b110) = Dana + Zhenya (yellow)
    - 7 (0b111) = All three
    """

    __tablename__ = "assignments"

    id: Optional[int] = Field(default=None, primary_key=True)
    day: date = Field(index=True, unique=True)
    mask: int = Field(default=0)  # Bitmask for people
    note: str = Field(default="")

    @property
    def diana(self) -> bool:
        """Check if Diana is assigned."""
        return bool(self.mask & 1)

    @property
    def dana(self) -> bool:
        """Check if Dana is assigned."""
        return bool(self.mask & 2)

    @property
    def zhenya(self) -> bool:
        """Check if Zhenya is assigned."""
        return bool(self.mask & 4)

    @classmethod
    def from_people(cls, day: date, people: list[str], note: str = "") -> "Assignment":
        """Create assignment from list of people names."""
        mask = 0
        for person in people:
            person_lower = person.lower()
            if person_lower in ("diana", "діана"):
                mask |= 1
            elif person_lower in ("dana", "дана"):
                mask |= 2
            elif person_lower in ("zhenya", "женя", "zhenya"):
                mask |= 4

        return cls(day=day, mask=mask, note=note)

    def get_people_names(self) -> list[str]:
        """Get list of assigned people names in Ukrainian."""
        names = []
        if self.diana:
            names.append("Діана")
        if self.dana:
            names.append("Дана")
        if self.zhenya:
            names.append("Женя")
        return names

    def get_color(self) -> str:
        """
        Get color for this assignment based on bitmask.

        Returns RGB hex color:
        - Diana only: blue (#4A90E2)
        - Dana only: purple (#9B59B6)
        - Zhenya only: green (#27AE60)
        - Diana + Zhenya: pink (#E91E63)
        - Dana + Zhenya: yellow (#F39C12)
        - Dana + Diana: red (#E74C3C)
        - All three or none: gray (#95A5A6)
        """
        if self.mask == 1:  # Diana only
            return "#4A90E2"
        elif self.mask == 2:  # Dana only
            return "#9B59B6"
        elif self.mask == 4:  # Zhenya only
            return "#27AE60"
        elif self.mask == 5:  # Diana + Zhenya
            return "#E91E63"
        elif self.mask == 6:  # Dana + Zhenya
            return "#F39C12"
        elif self.mask == 3:  # Dana + Diana
            return "#E74C3C"
        else:  # All three or none
            return "#95A5A6"
