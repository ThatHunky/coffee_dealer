"""User management utilities for dynamic user configuration."""

from typing import Optional

from .models import Assignment, CombinationColor, UserConfig
from .repo import repo


class UserManager:
    """Manages dynamic user configurations and color assignments."""

    def __init__(self):
        """Initialize user manager."""
        self._user_cache: dict[str, UserConfig] = {}
        self._combo_cache: dict[int, CombinationColor] = {}
        self._initialized = False

    def _ensure_initialized(self) -> None:
        """Ensure cache is initialized (lazy loading)."""
        if not self._initialized:
            try:
                self._refresh_cache()
                self._initialized = True
            except Exception:
                # Database not ready yet, will retry on next access
                pass

    def _refresh_cache(self) -> None:
        """Refresh user and combination caches from database."""
        users = repo.get_all_users(active_only=False)
        self._user_cache = {u.name_en.lower(): u for u in users}

        combos = repo.get_all_combinations()
        self._combo_cache = {c.mask: c for c in combos}

    def get_user_by_name(self, name: str) -> Optional[UserConfig]:
        """Get user by name (English or Ukrainian)."""
        self._ensure_initialized()

        # Check cache first
        name_lower = name.lower()
        if name_lower in self._user_cache:
            return self._user_cache[name_lower]

        # Check database
        user = repo.get_user_by_name(name)
        if user:
            self._user_cache[user.name_en.lower()] = user
        return user

    def get_active_users(self) -> list[UserConfig]:
        """Get all active users."""
        self._ensure_initialized()
        self._refresh_cache()
        return [u for u in self._user_cache.values() if u.is_active]

    def name_to_mask(self, names: list[str]) -> int:
        """Convert list of names to bitmask."""
        self._ensure_initialized()
        mask = 0
        for name in names:
            user = self.get_user_by_name(name)
            if user:
                mask |= 1 << user.bit_position
        return mask

    def mask_to_names(self, mask: int) -> list[str]:
        """Convert bitmask to list of Ukrainian names."""
        self._ensure_initialized()
        names = []
        for user in sorted(self._user_cache.values(), key=lambda u: u.bit_position):
            if mask & (1 << user.bit_position):
                names.append(user.name_uk)
        return names

    def get_color_for_mask(self, mask: int) -> str:
        """Get emoji for a given mask (solo or combination).

        Note: This method is deprecated. Use get_emoji_for_mask() instead.
        Kept for backwards compatibility.
        """
        return self.get_emoji_for_mask(mask)

    def get_combination_label(self, mask: int) -> str:
        """Get label for a combination."""
        self._ensure_initialized()

        if mask in self._combo_cache:
            return self._combo_cache[mask].label_uk

        # Generate label from names
        names = self.mask_to_names(mask)
        return "+".join(names) if names else "—"

    def get_emoji_for_mask(self, mask: int) -> str:
        """Get emoji for a given mask (solo or combination)."""
        self._ensure_initialized()

        # Check for combination emoji first
        if mask in self._combo_cache:
            return self._normalize_emoji(self._combo_cache[mask].emoji)

        # Check for solo user emoji
        for user in self._user_cache.values():
            if mask == (1 << user.bit_position):
                return self._normalize_emoji(user.emoji)

        # Default emoji for unknown combinations
        return "⚫"

    def _normalize_emoji(self, emoji: str) -> str:
        """Normalize emojis to widely supported, colorful variants.

        - Map unsupported or 'just square' emojis (e.g., ⚫, ◼, ⬛, ▪, ▫, ▫️, ◻️, ◽, ◾, ▫️, etc.) to colored hearts.
        - Keep colored circles and hearts as is.
        """
        # List of 'just square' or generic/unsupported emojis
        square_emojis = {
            "⚫",
            "◼",
            "⬛",
            "▪",
            "▫",
            "◻",
            "◻️",
            "◽",
            "◾",
            "▫️",
            "⬜",
            "⬜️",
            "□",
            "■",
            "▪️",
            "▫️",
        }
        # List of colored hearts to cycle through
        colored_hearts = ["💗", "💙", "💚", "💛", "💜", "🧡", "❤️"]
        mapping = {
            "🟠": "�",  # Orange circle (keep)
            "🟣": "🟣",  # Purple circle (keep)
            "🔵": "🔵",  # Blue circle (keep)
            "🟢": "🟢",  # Green circle (keep)
            "🔴": "🔴",  # Red circle (keep)
            "🟡": "🟡",  # Yellow circle (keep)
            "❤️": "❤️",  # Red heart (keep)
            "💗": "💗",  # Pink heart (keep)
            "💙": "💙",  # Blue heart (keep)
            "💚": "💚",  # Green heart (keep)
            "💛": "💛",  # Yellow heart (keep)
            "💜": "💜",  # Purple heart (keep)
            "🧡": "🧡",  # Orange heart (keep)
        }
        # If it's a known mapping, use it
        if emoji in mapping:
            return mapping[emoji]
        # If it's a square/unsupported, pick a colored heart based on hash
        if emoji in square_emojis or emoji in {"⚫", "⚪"}:
            # Deterministically pick a heart for variety
            idx = abs(hash(emoji)) % len(colored_hearts)
            return colored_hearts[idx]
        # If it's a single char and not in mapping, default to 💗
        if len(emoji) == 1 and not emoji.isalnum():
            return "💗"
        return emoji

    def update_user(
        self,
        bit_position: int,
        name_uk: str,
        name_en: str,
        emoji: str,
        is_active: bool = True,
    ) -> UserConfig:
        """Update or create a user configuration."""
        self._ensure_initialized()
        user = UserConfig(
            bit_position=bit_position,
            name_uk=name_uk,
            name_en=name_en.lower(),
            emoji=emoji,
            is_active=is_active,
        )
        result = repo.upsert_user(user)
        self._refresh_cache()
        return result

    def update_combination(
        self, mask: int, emoji: str, label_uk: str
    ) -> CombinationColor:
        """Update or create a combination emoji."""
        self._ensure_initialized()
        combo = CombinationColor(mask=mask, emoji=emoji, label_uk=label_uk)
        result = repo.upsert_combination(combo)
        self._refresh_cache()
        return result

    def get_all_colors_legend(self) -> list[tuple[str, str]]:
        """Get all emojis and labels for legend display.

        Returns list of (emoji, label) tuples instead of (color, label).
        """
        self._ensure_initialized()
        legend = []

        # Add solo users with their emojis
        for user in sorted(
            [u for u in self._user_cache.values() if u.is_active],
            key=lambda u: u.bit_position,
        ):
            mask = 1 << user.bit_position
            emoji = self.get_emoji_for_mask(mask)
            legend.append((emoji, user.name_uk))

        # Add combinations with their emojis
        for combo in sorted(self._combo_cache.values(), key=lambda c: c.mask):
            if combo.label_uk:
                emoji = self.get_emoji_for_mask(combo.mask)
                legend.append((emoji, combo.label_uk))

        return legend


# Global user manager instance
user_manager = UserManager()
