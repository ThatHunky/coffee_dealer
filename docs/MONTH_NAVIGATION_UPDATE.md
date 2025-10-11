# Month Navigation & Emoji Legend Update

## Summary
Updated the Coffee Dealer bot to include month history navigation (12 months max) and replaced color codes with emojis in the legend.

## Changes Made

### 1. Month Navigation (12-month history)

#### Modified Files:
- `src/bot.py`

#### Changes:
- **Added import**: `from dateutil.relativedelta import relativedelta`
- **New function**: `get_month_navigation_keyboard(year: int, month: int)` - Creates inline keyboard with:
  - "◀️ Попередній" button to go to previous month
  - Current month display (centered, non-clickable)
  - "Наступний ▶️" button to go to next month
  - Limit indicator when reaching 12-month history limit
  
- **Updated function**: `send_calendar()` - Now includes navigation keyboard with each calendar
  
- **New callback handler**: `callback_month_navigation()` - Handles month navigation:
  - Validates that selected month is within 12-month history
  - Renders new calendar image
  - Updates message with new month data
  - Prevents navigation beyond 12 months in the past

#### Behavior:
- Users can navigate between months using inline buttons
- Maximum history: 12 months from today
- When user reaches the 12-month limit, the "Previous" button shows "⏹️" and displays a message
- Navigation persists across calendar views

### 2. Emoji Legend System

#### Modified Files:
- `src/user_manager.py`
- `src/image_render.py`

#### Changes in `user_manager.py`:

**New constants:**
```python
DEFAULT_EMOJIS = {
    0: "🔵",  # Diana - Blue circle
    1: "🟣",  # Dana - Purple circle
    2: "🟢",  # Zhenya - Green circle
    # ... expandable for more users
}

COMBINATION_EMOJIS = {
    3: "🔴",   # Diana + Dana - Red
    5: "🩷",   # Diana + Zhenya - Pink  
    6: "🟡",   # Dana + Zhenya - Yellow
    7: "🌈",   # All three - Rainbow
}
```

**New method:**
- `get_emoji_for_mask(mask: int) -> str` - Returns appropriate emoji for user mask

**Updated method:**
- `get_all_colors_legend()` - Now returns `list[tuple[emoji, label]]` instead of `list[tuple[color, label]]`

#### Changes in `image_render.py`:

**Legend rendering:**
- Replaced color box drawing with emoji text
- Emojis now appear instead of colored squares
- Improved spacing to accommodate emoji characters
- Uses larger font (24pt) for emojis for better visibility

### 3. Dependencies

#### Modified Files:
- `requirements.txt`

#### Added:
- `python-dateutil>=2.8.0` - Required for `relativedelta` calculations

## Usage Examples

### Month Navigation:
1. User sends "📅 Показати місяць" or "покажи жовтень"
2. Bot displays calendar with navigation buttons below
3. User clicks "◀️ Попередній" or "Наступний ▶️"
4. Calendar updates to selected month
5. If user tries to go beyond 12 months, they see a limit message

### Emoji Legend:
Calendar now shows legend like:
```
Легенда:
🔵 Діана    🟣 Дана    🟢 Женя
🔴 Дана+Діана    🩷 Діана+Женя    🟡 Дана+Женя
```

Instead of color boxes, emojis are used for better visual clarity and mobile compatibility.

## Benefits

1. **Improved Navigation**: Users can easily browse past and future months without typing
2. **Better UX**: Inline buttons provide intuitive interface
3. **Visual Clarity**: Emojis are more recognizable and work better on all devices
4. **Mobile-Friendly**: Emojis display consistently across platforms
5. **Memory Management**: 12-month limit prevents excessive data loading
6. **Accessibility**: Emojis are easier to distinguish than color codes

## Technical Notes

- Calendar images are regenerated on each navigation action
- Navigation state is maintained through callback data format: `month_YYYY_MM`
- Emoji rendering uses Unicode, ensuring cross-platform compatibility
- The system is extensible - more emojis can be added for additional users or combinations

## Testing Recommendations

1. Test navigation between current month and 12 months ago
2. Verify limit behavior when trying to go beyond 12 months
3. Test emoji rendering on different devices (mobile/desktop)
4. Verify calendar updates correctly when navigating
5. Check that emoji legend displays correctly for all user combinations
