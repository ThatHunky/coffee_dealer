# Interactive User Assignment Feature

## 📋 Overview

Added an easy-to-use, button-based interface for assigning users to dates in the Coffee Dealer bot. This feature allows admins to visually select dates and toggle user assignments without typing commands.

## ✨ Features

### 1. Calendar-Style Date Selection
- Visual month calendar with all days displayed
- Shows existing assignments with emojis on dates
- Month navigation with previous/next buttons
- Week layout (Monday-Sunday) for easy navigation

### 2. Interactive User Toggle
- Checkboxes for each active user
- Visual feedback with ✅ (selected) and ⬜ (unselected)
- User emojis displayed for quick identification
- Shows current assignment for the selected date

### 3. Session Management
- Maintains assignment state during the process
- Allows going back to change date selection
- Cancel option to abort the operation
- Auto-cleanup after save or cancel

## 🎯 How to Use

### Starting an Assignment

1. Use the `/assign` command (admin only)
2. A calendar for the current month appears with inline buttons

### Selecting a Date

1. Click on any date number in the calendar
2. Dates with existing assignments show emojis
3. Use ◀️ and ▶️ buttons to navigate months
4. Click ❌ to cancel at any time

### Selecting Users

1. After selecting a date, a user selection screen appears
2. Current assignment is shown at the top
3. Click on user names to toggle selection:
   - ⬜ = not selected
   - ✅ = selected
4. Use action buttons:
   - 🔙 **Назад**: Return to date selection
   - ✅ **Зберегти**: Save the assignment
   - 🗑️ **Очистити**: Clear all assignments for this date

### Saving

1. Click ✅ **Зберегти** to save the assignment
2. Confirmation message is shown
3. Calendar is automatically updated and displayed
4. Change notifications are sent to configured users

## 📁 Files Modified

### `src/bot.py`
- Added `assignment_sessions` dictionary for session state management
- Added `/assign` command handler
- Added `send_date_selection_keyboard()` function for calendar display
- Added `send_user_selection_keyboard()` function for user selection
- Added callback handlers:
  - `callback_assign_month()` - Month navigation
  - `callback_assign_date()` - Date selection
  - `callback_assign_toggle()` - User toggle
  - `callback_assign_save()` - Save assignment
  - `callback_assign_clear()` - Clear assignment
  - `callback_assign_back()` - Back to date selection
  - `callback_assign_cancel()` - Cancel session
  - `callback_day_ignore()` - Ignore header/empty clicks
- Updated admin commands to include `/assign`

## 🔧 Technical Details

### Session State Structure
```python
assignment_sessions[user_id] = {
    "year": int,           # Selected year
    "month": int,          # Selected month
    "day": int | None,     # Selected day (None during date selection)
    "selected_users": set  # Set of selected user names (lowercase)
}
```

### Callback Data Format
- **Month navigation**: `assign_month_YYYY_MM`
- **Date selection**: `assign_date_YYYY_MM_DD`
- **User toggle**: `assign_toggle_USERNAME`
- **Save**: `assign_save_YYYY_MM_DD`
- **Clear**: `assign_clear_YYYY_MM_DD`
- **Back**: `assign_back_to_date`
- **Cancel**: `assign_cancel`
- **Ignore**: `day_header`, `day_empty`

### Calendar Layout
- 7-column layout matching week structure
- Header row with weekday names (Пн-Нд)
- Empty cells for alignment before month start
- Day buttons with emoji indicators
- Navigation row at bottom

## 📝 Examples

### Example 1: Assign Single User
1. Admin types `/assign`
2. Calendar appears
3. Admin clicks on "15" (15th day)
4. User selection appears
5. Admin clicks "🔵 Діана" (toggles to ✅)
6. Admin clicks ✅ **Зберегти**
7. Success message: "✅ Призначено на 15.10.2025: Діана"

### Example 2: Assign Multiple Users
1. Admin types `/assign`
2. Selects date "20"
3. Toggles multiple users: Діана ✅, Дана ✅
4. Clicks ✅ **Зберегти**
5. Success message: "✅ Призначено на 20.10.2025: Діана, Дана"

### Example 3: Clear Assignment
1. Admin types `/assign`
2. Selects date with existing assignment
3. Clicks 🗑️ **Очистити**
4. Success message: "✅ Очищено призначення на 15.10.2025"

### Example 4: Navigate Months
1. Admin types `/assign`
2. Clicks "Наступний ▶️"
3. Calendar for next month appears
4. Clicks "◀️ Попередній" to go back
5. Selects desired date

## 🎨 UI Elements

### Date Calendar
```
📅 Оберіть дату для призначення:
Жовтень 2025

Пн Вт Ср Чт Пт Сб Нд
       1  2  3  4  5
 6  7  8  9 10 11 12
13 14 15🔵16 17 18 19
20 21 22 23 24 25 26
27 28 29 30 31

◀️ Попередній   ❌ Скасувати   Наступний ▶️
```

### User Selection
```
👥 Оберіть працівників для 15.10.2025:

Поточне призначення: Діана

Натисніть на ім'я, щоб додати/прибрати:

✅ 🔵 Діана
⬜ 🟣 Дана
⬜ 🟢 Женя

🔙 Назад   ✅ Зберегти   🗑️ Очистити
```

## 🔐 Security & Permissions

- **Admin only**: Only users with admin privileges can use `/assign`
- **Session isolation**: Each user has their own separate session
- **Auto-cleanup**: Sessions are cleared after save/cancel
- **Validation**: All dates and users are validated before saving

## 📊 Logging

All assignment operations are logged with appropriate levels:
- `INFO`: Successful assignments, session start/end
- `ERROR`: Failed operations with full stack trace
- `DEBUG`: Session state changes (if debug enabled)

## 🆚 Comparison with Text Commands

### Before (Text Command)
```
Admin: постав Діану на 15 жовтня
Bot: ✅ Призначено...
```
**Pros**: Fast for power users, natural language
**Cons**: Requires typing, prone to typos, less visual

### After (Interactive Buttons)
```
Admin: /assign
Bot: [Calendar appears]
Admin: [Clicks date]
Bot: [User selection appears]
Admin: [Toggles users, clicks save]
Bot: ✅ Призначено...
```
**Pros**: Visual, intuitive, no typing, less error-prone
**Cons**: More clicks for simple operations

## 🔄 Integration

The new button-based system works alongside existing text-based commands:
- `/assign` - Interactive button-based assignment (**NEW**)
- Natural language - "постав Діану на 15 жовтня"
- `/adduser`, `/edituser` - User management

Both systems use the same underlying `Assignment` and `repo` infrastructure, ensuring consistency.

## ✅ Benefits

1. **User-Friendly**: No need to remember command syntax
2. **Visual Feedback**: See calendar and current assignments
3. **Error Prevention**: Valid dates and users only
4. **Intuitive**: Familiar calendar interface
5. **Multi-User**: Easy to select multiple users
6. **Flexible**: Can go back and change selections
7. **Safe**: Confirmation before saving

## 🚀 Future Enhancements (Ideas)

- Bulk assignment mode (select multiple dates)
- Quick templates (e.g., "All weekends to Diana")
- Assignment preview before saving
- Copy assignments from previous month
- Date range selection
- Notes support in interactive mode

## 📚 Related Documentation

- **Admin Guide**: `docs/ADMIN_GUIDE.md`
- **User Management**: `docs/USER_MANAGEMENT_FEATURE.md`
- **Month Navigation**: `docs/MONTH_NAVIGATION_UPDATE.md`

---

**Implementation Date**: October 2025
**Version**: 1.0
**Status**: ✅ Active
