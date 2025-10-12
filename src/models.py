"""Data models for schedule assignments."""

from datetime import date, datetime
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
        # Import here to avoid circular dependency
        from .user_manager import user_manager

        mask = user_manager.name_to_mask(people)
        return cls(day=day, mask=mask, note=note)

    def get_people_names(self) -> list[str]:
        """Get list of assigned people names in Ukrainian."""
        # Import here to avoid circular dependency
        from .user_manager import user_manager

        return user_manager.mask_to_names(self.mask)

    def get_color(self) -> str:
        """Get color for this assignment based on bitmask."""
        # Import here to avoid circular dependency
        from .user_manager import user_manager

        return user_manager.get_color_for_mask(self.mask)


class UserConfig(SQLModel, table=True):
    """
    User configuration for customizable names and colors.

    This allows admins to manage users dynamically instead of hardcoding.
    Each user has a bit position (0-7) for the bitmask system.
    """

    __tablename__ = "user_configs"

    id: Optional[int] = Field(default=None, primary_key=True)
    bit_position: int = Field(index=True, unique=True)  # 0-7 for bitmask
    name_uk: str = Field(index=True)  # Ukrainian name (e.g., "Діана")
    name_en: str = Field(index=True)  # English name for matching (e.g., "diana")
    emoji: str = Field(default="🔵")  # Emoji when working alone
    is_active: bool = Field(default=True)  # Active users show in lists
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @classmethod
    def create_default_users(cls) -> list["UserConfig"]:
        """Create default user configurations."""
        return [
            cls(
                bit_position=0,
                name_uk="Діана",
                name_en="diana",
                emoji="🔵",
                is_active=True,
            ),
            cls(
                bit_position=1,
                name_uk="Дана",
                name_en="dana",
                emoji="🟣",
                is_active=True,
            ),
            cls(
                bit_position=2,
                name_uk="Женя",
                name_en="zhenya",
                emoji="🟢",
                is_active=True,
            ),
        ]


class CombinationColor(SQLModel, table=True):
    """
    Custom colors for user combinations.

    Allows admins to set specific colors when multiple people work together.
    """

    __tablename__ = "combination_colors"

    id: Optional[int] = Field(default=None, primary_key=True)
    mask: int = Field(index=True, unique=True)  # Bitmask combination
    emoji: str = Field(default="⚫")  # Emoji for combination
    label_uk: str = Field(default="")  # Ukrainian label (e.g., "Діана+Женя")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    @classmethod
    def create_default_combinations(cls) -> list["CombinationColor"]:
        """Create default combination emojis."""
        return [
            cls(mask=3, emoji="🔴", label_uk="Дана+Діана"),  # 0b011
            cls(mask=5, emoji="🟠", label_uk="Діана+Женя"),  # 0b101
            cls(mask=6, emoji="🟡", label_uk="Дана+Женя"),  # 0b110
        ]


class ChangeNotification(SQLModel, table=True):
    """
    Track schedule changes for notifications.

    Stores who made changes and when, for audit trail and notifications.
    """

    __tablename__ = "change_notifications"

    id: Optional[int] = Field(default=None, primary_key=True)
    change_date: date = Field(index=True)  # Which day was modified
    old_mask: int = Field(default=0)  # Previous assignment mask
    new_mask: int = Field(default=0)  # New assignment mask
    changed_by: int = Field(index=True)  # Telegram user ID who made the change
    changed_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    notified: bool = Field(default=False)  # Whether notification was sent

    def get_change_description(self) -> str:
        """Get human-readable description of the change."""
        # This will be implemented using the dynamic user config
        # For now, return a basic description
        if self.old_mask == 0 and self.new_mask > 0:
            return "Додано призначення"
        elif self.old_mask > 0 and self.new_mask == 0:
            return "Видалено призначення"
        elif self.old_mask != self.new_mask:
            return "Змінено призначення"
        else:
            return "Без змін"


class ChangeRequest(SQLModel, table=True):
    """
    Change requests from non-admin users requiring approval.

    When a regular user tries to modify the schedule, it creates a pending
    request that admins can approve or deny.
    """

    __tablename__ = "change_requests"

    id: Optional[int] = Field(default=None, primary_key=True)
    request_type: str = Field(index=True)  # "assign_day", "assign_days", "assign_bulk"
    requested_by: int = Field(index=True)  # Telegram user ID who made the request
    requested_by_name: str = Field(default="")  # User's display name
    requested_at: datetime = Field(default_factory=datetime.utcnow, index=True)

    # Request data (stored as JSON-compatible fields)
    days: str = Field(default="[]")  # JSON array of days, e.g., "[7, 8, 20]"
    people: str = Field(default="[]")  # JSON array of people, e.g., '["diana", "dana"]'
    pattern: str = Field(default="")  # Pattern for bulk assignment
    year: int = Field(default=0)
    month: int = Field(default=0)
    note: str = Field(default="")

    # Status
    status: str = Field(
        default="pending", index=True
    )  # "pending", "approved", "denied"
    reviewed_by: Optional[int] = Field(default=None)  # Admin who reviewed
    reviewed_at: Optional[datetime] = Field(default=None)
    review_note: str = Field(default="")  # Optional note from admin

    def get_description(self) -> str:
        """Get human-readable description of the request."""
        import json

        people_list = json.loads(self.people)
        people_text = ", ".join(people_list)

        if self.request_type == "assign_day":
            days_list = json.loads(self.days)
            if days_list:
                return f"{people_text} на {days_list[0]} число"
            return f"{people_text}"
        elif self.request_type == "assign_days":
            days_list = json.loads(self.days)
            days_text = ", ".join(map(str, days_list))
            return f"{people_text} на {days_text}"
        elif self.request_type == "assign_bulk":
            pattern_names = {
                "all_sundays": "всі неділі",
                "all_saturdays": "всі суботи",
                "all_weekends": "всі вихідні",
                "all_weekdays": "всі будні",
                "whole_month": "весь місяць",
            }
            pattern_text = pattern_names.get(self.pattern, self.pattern)
            return f"{people_text} на {pattern_text}"
        return "зміна розкладу"


class UserApproval(SQLModel, table=True):
    """
    Track new users who need admin approval before using the bot.

    When a new user starts the bot, they are added here as 'pending'.
    Admins can approve or deny access.
    """

    __tablename__ = "user_approvals"

    id: Optional[int] = Field(default=None, primary_key=True)
    telegram_id: int = Field(index=True, unique=True)
    telegram_username: str = Field(default="")
    telegram_first_name: str = Field(default="")
    telegram_last_name: str = Field(default="")
    full_name: str = Field(default="")  # Combined name for display

    # Status
    status: str = Field(
        default="pending", index=True
    )  # "pending", "approved", "denied"
    requested_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    reviewed_by: Optional[int] = Field(default=None)  # Admin who reviewed
    reviewed_at: Optional[datetime] = Field(default=None)
    review_note: str = Field(default="")  # Optional note from admin

    # Notifications
    notified_admins: bool = Field(default=False)  # Whether admins were notified
    notified_user: bool = Field(default=False)  # Whether user was notified of decision
