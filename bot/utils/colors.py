"""Color mapping and display utilities"""

from typing import Optional, List, Dict
import re


# Color name to hex mapping
COLOR_MAP = {
    "yellow": "#FFD700", "жовтий": "#FFD700", "💛": "#FFD700",
    "pink": "#FF69B4", "рожевий": "#FF69B4", "🩷": "#FF69B4", "персиковий": "#FFB6C1",
    "blue": "#00CED1", "голубий": "#00CED1", "синій": "#00CED1", "💙": "#00CED1",  # Added "синій"
    "purple": "#9370DB", "фіолетовий": "#9370DB", "💜": "#9370DB",
    "green": "#32CD32", "зелений": "#32CD32", "💚": "#32CD32",
    "orange": "#FFA500", "оранжевий": "#FFA500",
    "teal": "#20B2AA",
    "lightblue": "#87CEEB",
    "lightgreen": "#90EE90",
    "darkorange": "#FF8C00",
}


# Emoji mapping for display
EMOJI_MAP = {
    "#FFD700": "💛",  # Yellow
    "#FF69B4": "🩷",  # Pink
    "#FFB6C1": "🩷",  # Peach (use pink emoji)
    "#00CED1": "💙",  # Blue/Teal
    "#9370DB": "💜",  # Purple
    "#32CD32": "💚",  # Green
    "#FFA500": "🧡",  # Orange
    "#20B2AA": "💙",  # Teal (use blue)
    "#87CEEB": "💙",  # Light blue
    "#90EE90": "💚",  # Light green
    "#FF8C00": "🧡",  # Dark orange
}


def parse_color(color_input: str) -> Optional[str]:
    """
    Parse color input (hex, name, or emoji) to hex code.
    
    Args:
        color_input: Color as hex (#FFD700), name (yellow), or emoji (💛)
    
    Returns:
        Hex color code or None if invalid
    """
    color_input = color_input.strip().lower()
    
    # Check if it's already a hex code
    if re.match(r"^#[0-9A-Fa-f]{6}$", color_input):
        return color_input.upper()
    
    # Check color map
    if color_input in COLOR_MAP:
        return COLOR_MAP[color_input]
    
    # Check case-insensitive
    for key, value in COLOR_MAP.items():
        if key.lower() == color_input:
            return value
    
    return None


def get_color_emoji(hex_color: Optional[str]) -> str:
    """
    Get emoji representation for a hex color.
    
    Args:
        hex_color: Hex color code
    
    Returns:
        Emoji string or empty string if no color
    """
    if not hex_color:
        return "⚪"
    
    hex_color = hex_color.upper()
    return EMOJI_MAP.get(hex_color, "⚪")


def get_combined_color_emoji(hex_colors: List[str]) -> str:
    """
    Get combined emoji for multiple colors (shared shifts).
    
    Args:
        hex_colors: List of hex color codes
    
    Returns:
        Combined emoji string
    """
    if not hex_colors:
        return "⚪"
    
    if len(hex_colors) == 1:
        return get_color_emoji(hex_colors[0])
    
    # For multiple colors, combine emojis
    emojis = [get_color_emoji(c) for c in hex_colors if c]
    return "".join(emojis[:3])  # Limit to 3 emojis max


def get_default_colors() -> List[str]:
    """Get list of default color hex codes"""
    return [
        "#FFD700",  # Yellow
        "#FF69B4",  # Pink
        "#00CED1",  # Blue
        "#9370DB",  # Purple
        "#32CD32",  # Green
        "#FFA500",  # Orange
    ]


def assign_color_to_user(user_index: int, existing_colors: List[str]) -> str:
    """
    Assign a color to a user based on index, avoiding duplicates.
    
    Args:
        user_index: Index of user (0-based)
        existing_colors: List of already used colors
    
    Returns:
        Hex color code
    """
    default_colors = get_default_colors()
    
    # Try to assign from defaults first
    for color in default_colors:
        if color not in existing_colors:
            return color
    
    # If all defaults are used, cycle through them
    return default_colors[user_index % len(default_colors)]

