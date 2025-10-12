# Interactive User Editor Feature

## 📋 Overview

Added an easy-to-use, button-based interface for editing users in the Coffee Dealer bot. Admins can now manage users through an intuitive menu system instead of typing complex commands.

## ✨ Features

### 1. Visual User Selection
- List all users with their current status and emojis
- Click any user to edit their details
- Add new users with a step-by-step wizard
- See active/inactive status at a glance

### 2. Field-by-Field Editing
- Edit Ukrainian name
- Edit English name (for command recognition)
- Change emoji
- Toggle active/inactive status
- All with simple button clicks

### 3. New User Wizard
- Guided 3-step process
- Automatically finds next available position
- Validates input at each step
- Easy text input for each field

## 🎯 How to Use

### Editing Existing Users

**Step 1: Start the editor**
```
/editusers
```
A list of all users appears with buttons.

**Step 2: Select a user**
Click on any user button (e.g., "✅ 🔵 Діана")

**Step 3: Choose what to edit**
Options appear:
- 🇺🇦 Змінити ім'я (укр)
- 🇬🇧 Змінити ім'я (англ)
- 🔵 Змінити емодзі
- ❌ Деактивувати користувача (or ✅ Активувати)

**Step 4: Enter new value**
Type the new value in a text message

**Step 5: Done!**
User is updated automatically

### Adding New Users

**Step 1: Start the editor**
```
/editusers
```

**Step 2: Click "➕ Додати нового користувача"**

**Step 3: Follow the wizard**
1. Enter Ukrainian name (e.g., "Марія")
2. Enter English name (e.g., "maria")
3. Enter emoji (e.g., "💗")

**Step 4: Done!**
New user is created and ready to use.

### Activating/Deactivating Users

**Quick Toggle:**
1. `/editusers`
2. Click on user
3. Click "❌ Деактивувати" or "✅ Активувати"
4. Status changes immediately!

## 📱 User Interface

### User List Screen
```
👥 Оберіть користувача для редагування:

✅ 🔵 Діана (позиція 0)
✅ 🟣 Дана (позиція 1)
✅ 🟢 Женя (позиція 2)

[✅ 🔵 Діана]
[✅ 🟣 Дана]
[✅ 🟢 Женя]
[➕ Додати нового користувача]
```

### Edit Menu Screen
```
✏️ Редагування користувача:

📍 Позиція: 0
🇺🇦 Ім'я (укр): Діана
🇬🇧 Ім'я (англ): diana
🔵 Емодзі
📊 Статус: ✅ Активний

Що бажаєте змінити?

[🇺🇦 Змінити ім'я (укр)]
[🇬🇧 Змінити ім'я (англ)]
[🔵 Змінити емодзі]
[❌ Деактивувати користувача]
[🔙 Назад до списку] [❌ Скасувати]
```

### Field Input Screen
```
✏️ Введіть нове українське ім'я:

Поточне значення: Діана

Надішліть нове значення текстовим повідомленням.

[🔙 Назад] [❌ Скасувати]
```

### New User Wizard
```
➕ Додавання нового користувача

📍 Позиція: 3

✏️ Крок 1/3: Введіть українське ім'я
Наприклад: Діана, Марія, Олександр

[❌ Скасувати]

---

✏️ Крок 2/3: Введіть англійське ім'я
(використовується для розпізнавання команд)

Наприклад: diana, maria, alex
(малими літерами, без пробілів)

[❌ Скасувати]

---

✏️ Крок 3/3: Введіть емодзі
(буде відображатися в календарі)

Наприклад: 🔵 🟣 🟢 💗 💙 💚 🧡

[❌ Скасувати]
```

## 📁 Files Modified

### `src/bot.py`
- Added `user_edit_sessions` dictionary for session state management
- Added `/editusers` command handler
- Added `send_user_edit_menu()` helper function
- Added callback handlers:
  - `callback_edituser_select()` - User selection
  - `callback_edituser_field()` - Field selection
  - `callback_edituser_toggle_active()` - Toggle active/inactive
  - `callback_edituser_back_to_menu()` - Back to edit menu
  - `callback_edituser_back_to_list()` - Back to user list
  - `callback_edituser_cancel()` - Cancel editing
  - `callback_edituser_add_new()` - Add new user wizard
- Added `handle_user_edit_input()` message handler for text input
- Updated admin commands to include `/editusers`

## 🔧 Technical Details

### Session State Structure
```python
user_edit_sessions[user_id] = {
    "user": UserConfig,        # Current user being edited
    "bit_position": int,       # User's bit position
    "name_uk": str,            # Ukrainian name
    "name_en": str,            # English name
    "emoji": str,              # User emoji
    "is_active": bool,         # Active status
    "editing_field": str,      # Current field being edited (optional)
    "is_new": bool,            # True if adding new user (optional)
}
```

### Callback Data Format
- **User selection**: `edituser_select_POSITION`
- **Field selection**: `edituser_field_FIELDNAME`
- **Toggle active**: `edituser_toggle_active`
- **Back to menu**: `edituser_back_to_menu`
- **Back to list**: `edituser_back_to_list`
- **Cancel**: `edituser_cancel`
- **Add new**: `edituser_add_new`

### Text Input Handler
The `handle_user_edit_input()` function intercepts text messages when a user is in edit mode:
- Checks if user has an active edit session
- Validates input based on field type
- Updates the session state
- Saves to database when complete
- Returns control after completion

### Auto-Position Assignment
When adding a new user, the system automatically finds the next available position (0-7).

## 📝 Examples

### Example 1: Change User Emoji
```
Admin: /editusers
Bot: [Shows user list]
Admin: [Clicks "✅ 🔵 Діана"]
Bot: [Shows edit menu]
Admin: [Clicks "🔵 Змінити емодзі"]
Bot: "✏️ Введіть новий емодзі:"
Admin: "💙"
Bot: ✅ Поле оновлено!
     📍 Позиція: 0
     🇺🇦 Ім'я: Діана
     🇬🇧 Name: diana
     💙 Емодзі
     📊 Статус: ✅ Активний
```

### Example 2: Add New User
```
Admin: /editusers
Bot: [Shows user list]
Admin: [Clicks "➕ Додати нового користувача"]
Bot: "✏️ Крок 1/3: Введіть українське ім'я"
Admin: "Марія"
Bot: "✏️ Крок 2/3: Введіть англійське ім'я"
Admin: "maria"
Bot: "✏️ Крок 3/3: Введіть емодзі"
Admin: "💗"
Bot: ✅ Нового користувача додано!
     📍 Позиція: 3
     🇺🇦 Ім'я: Марія
     🇬🇧 Name: maria
     💗 Емодзі
     📊 Статус: ✅ Активний
```

### Example 3: Deactivate User
```
Admin: /editusers
Bot: [Shows user list with all users]
Admin: [Clicks "✅ 🟢 Женя"]
Bot: [Shows edit menu]
Admin: [Clicks "❌ Деактивувати користувача"]
Bot: ✅ Користувача деактивовано
     [Edit menu refreshes showing new status]
```

## 🆚 Comparison with Text Commands

### Before (Text Commands)
```
/adduser 3 Марія maria #FF69B4
/edituser maria - - 💗
/removeuser maria
/activateuser maria
```
**Pros**: Fast for power users who know the syntax
**Cons**: Must remember exact format, prone to typos, no visual feedback

### After (Interactive Buttons)
```
/editusers → [visual menu] → [select user] → [choose field] → [type value]
```
**Pros**: Visual, guided, no syntax to remember, validation
**Cons**: More clicks, not as fast for experts

## 🔄 Integration

Both systems work together:
- `/editusers` - Interactive button-based editor (**NEW** ⭐)
- `/edituser <name> <uk> <en> <emoji>` - Text-based quick edit
- `/adduser`, `/removeuser`, `/activateuser` - Still available

All commands use the same `user_manager` and `repo` infrastructure.

## ✅ Benefits

1. **No Syntax to Remember**: Everything is guided with buttons
2. **Visual Feedback**: See all users and their current state
3. **Error Prevention**: Input validation at each step
4. **Intuitive**: Familiar menu-based interface
5. **Step-by-Step**: New user wizard guides through process
6. **Quick Toggle**: One-click activate/deactivate
7. **Safe**: Can cancel at any time

## 🔐 Security & Permissions

- **Admin only**: Only users with admin privileges can use `/editusers`
- **Session isolation**: Each admin has their own separate session
- **Auto-cleanup**: Sessions are cleared after completion or cancel
- **Validation**: All inputs validated before saving
- **Maximum users**: Enforces 8-user limit (bit positions 0-7)

## 📊 Logging

All user edit operations are logged:
- `INFO`: User edited, new user created, status toggled
- `ERROR`: Failed operations with full stack trace
- Includes admin ID and user details for audit trail

## 🚀 Future Enhancements (Ideas)

- Bulk edit multiple users
- Import/export user configurations
- User templates
- Emoji picker interface
- Position reassignment
- User deletion (vs deactivation)

## 📚 Related Documentation

- **Admin Guide**: `docs/ADMIN_GUIDE.md`
- **User Management**: `docs/USER_MANAGEMENT_FEATURE.md`
- **Interactive Assignment**: `docs/INTERACTIVE_ASSIGNMENT_FEATURE.md`

---

**Implementation Date**: October 2025
**Version**: 1.0
**Status**: ✅ Active
