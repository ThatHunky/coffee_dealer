# Admin Guide - Coffee Dealer Bot

## Overview

This guide explains the new admin features for managing users, colors, and receiving notifications about schedule changes.

## New Features

### 1. Dynamic User Management

Instead of hardcoding users in the code, admins can now manage users dynamically through bot commands.

### 2. Custom Color Assignments

Admins can set custom colors for individual users and their combinations.

### 3. Change Notifications

When an admin modifies the schedule, all other admins receive automatic notifications about the change.

## Admin Commands

### `/users` - List All Users

Shows all configured users with their:
- Bit position (0-7)
- Ukrainian name
- English name (for matching)
- Color code
- Active/inactive status

**Example:**
```
/users
```

**Output:**
```
👥 Список користувачів:

✅ Позиція 0: Діана (diana)
   🎨 Колір: #4A90E2

✅ Позиція 1: Дана (dana)
   🎨 Колір: #9B59B6

✅ Позиція 2: Женя (zhenya)
   🎨 Колір: #27AE60
```

---

### `/adduser` - Add or Update User

Adds a new user or updates an existing user's configuration.

**Format:**
```
/adduser <bit_position> <name_ukrainian> <name_english> <color>
```

**Parameters:**
- `bit_position`: 0-7 (unique number for bitmask system)
- `name_ukrainian`: Ukrainian name (e.g., Діана)
- `name_english`: English name for matching (e.g., diana)
- `color`: RGB hex color code (e.g., #4A90E2)

**Examples:**
```
/adduser 0 Діана diana #4A90E2
/adduser 3 Марія maria #FF69B4
```

**Response:**
```
✅ Користувача оновлено:
Позиція: 0
Ім'я: Діана (diana)
Колір: #4A90E2
```

---

### `/edituser` - Edit User

Edit an existing user's configuration with support for partial updates.

**Format:**
```
/edituser <position|name> [new_name_uk] [new_name_en] [new_color]
```

**Parameters:**
- `position|name`: User's bit position (0-7) OR current name (diana, dana, etc.)
- `new_name_uk`: New Ukrainian name (or `-` to skip)
- `new_name_en`: New English name (or `-` to skip)
- `new_color`: New RGB hex color (or `-` to skip)

**Examples:**
```
# Change only the color for user at position 0
/edituser 0 - - #FF6B9D

# Change name for user "diana"
/edituser diana Діанка dianochka -

# Update everything for position 1
/edituser 1 Данка danka #AA55FF
```

**Response:**
```
✅ Користувача оновлено:
Позиція: 0
Ім'я: Діана (diana)
Колір: #FF6B9D
Статус: ✅ Активний
```

---

### `/removeuser` - Deactivate User

Deactivates a user without deleting their data or history.

**Format:**
```
/removeuser <position|name>
```

**Parameters:**
- `position|name`: User's bit position (0-7) OR name (diana, dana, etc.)

**Examples:**
```
# Deactivate by position
/removeuser 3

# Deactivate by name
/removeuser ivan
```

**Response:**
```
✅ Користувача деактивовано:
Позиція: 3
Ім'я: Іван (ivan)

⚠️ Користувач більше не буде відображатися в розкладі.
Для повторної активації використовуйте /edituser або /adduser.
```

**Important:**
- User data is NOT deleted
- Historical assignments are preserved
- User won't appear in future schedules
- Can be reactivated at any time

---

### `/activateuser` - Activate User

Reactivates a previously deactivated user.

**Format:**
```
/activateuser <position|name>
```

**Parameters:**
- `position|name`: User's bit position (0-7) OR name

**Examples:**
```
# Activate by position
/activateuser 3

# Activate by name
/activateuser ivan
```

**Response:**
```
✅ Користувача активовано:
Позиція: 3
Ім'я: Іван (ivan)

✅ Користувач тепер буде відображатися в розкладі.
```

---

### `/setcombo` - Set Combination Color

Sets a custom color for when multiple people work together.

**Format:**
```
/setcombo <mask> <color> <label>
```

**Parameters:**
- `mask`: Bitmask value (sum of bit positions, e.g., 1+4=5)
- `color`: RGB hex color code
- `label`: Ukrainian label for the legend

**How to Calculate Mask:**
The mask is the sum of 2^(bit_position) for each user:
- User at position 0: 2^0 = 1
- User at position 1: 2^1 = 2
- User at position 2: 2^2 = 4

**Examples:**
```
# Діана (pos 0) + Женя (pos 2) = 1 + 4 = 5
/setcombo 5 #E91E63 Діана+Женя

# Дана (pos 1) + Діана (pos 0) = 2 + 1 = 3
/setcombo 3 #E74C3C Дана+Діана

# All three = 1 + 2 + 4 = 7
/setcombo 7 #FFA500 Всі разом
```

**Response:**
```
✅ Комбінацію оновлено:
Маска: 5
Назва: Діана+Женя
Колір: #E91E63
```

---

### `/colors` - Show All Colors

Displays all configured colors and combinations.

**Example:**
```
/colors
```

**Output:**
```
🎨 Кольори та комбінації:

#4A90E2 — Діана
#9B59B6 — Дана
#27AE60 — Женя
#E74C3C — Дана+Діана
#E91E63 — Діана+Женя
#F39C12 — Дана+Женя
```

---

### `/changes` - Recent Changes

Shows recent schedule changes in the last 7 days.

**Example:**
```
/changes
```

**Output:**
```
📋 Останні зміни (7 днів):

📅 11.10.2025
   Діана → Діана, Женя
   ⏰ 11.10 14:30

📅 10.10.2025
   — → Дана
   ⏰ 10.10 09:15
```

---

## Change Notifications

When you modify the schedule using natural language or commands, all other admins will automatically receive a notification:

**Example Notification:**
```
🔔 Зміна в розкладі

📅 Дата: 11.10.2025
👤 Було: Діана
👤 Стало: Діана, Женя
⏰ 14:30:45
```

**Features:**
- Sent to all admins except the one who made the change
- Shows the date that was modified
- Shows old and new assignments
- Includes timestamp

---

## Color Picker Guide

Here are some nice color combinations you can use:

### Individual Colors
- **Blue**: `#4A90E2` (professional, calm)
- **Purple**: `#9B59B6` (creative, unique)
- **Green**: `#27AE60` (fresh, energetic)
- **Orange**: `#F39C12` (warm, friendly)
- **Red**: `#E74C3C` (bold, important)
- **Pink**: `#E91E63` (vibrant, fun)
- **Teal**: `#1ABC9C` (modern, balanced)
- **Yellow**: `#F1C40F` (bright, cheerful)

### Combination Colors
- **Pink**: `#E91E63` (for pairs)
- **Orange**: `#F39C12` (for pairs)
- **Red**: `#E74C3C` (for special combinations)
- **Gray**: `#95A5A6` (default/unassigned)

---

## Database Schema

### Tables Created

1. **`user_configs`** - User configuration
   - `id`: Primary key
   - `bit_position`: 0-7 (unique)
   - `name_uk`: Ukrainian name
   - `name_en`: English name
   - `color_solo`: RGB hex color
   - `is_active`: Boolean
   - `created_at`, `updated_at`: Timestamps

2. **`combination_colors`** - Color combinations
   - `id`: Primary key
   - `mask`: Bitmask (unique)
   - `color`: RGB hex color
   - `label_uk`: Ukrainian label
   - `created_at`: Timestamp

3. **`change_notifications`** - Change tracking
   - `id`: Primary key
   - `change_date`: Date modified
   - `old_mask`: Previous assignment
   - `new_mask`: New assignment
   - `changed_by`: Telegram user ID
   - `changed_at`: Timestamp
   - `notified`: Boolean (sent flag)

---

## Tips and Best Practices

1. **Bit Positions**: Keep them sequential (0, 1, 2, 3...) for easier management
2. **Colors**: Use contrasting colors so they're easily distinguishable in the calendar
3. **Names**: Keep English names lowercase for better matching
4. **Combinations**: Set colors for commonly used combinations
5. **Testing**: Test new users/colors on a future date before using on current schedule

---

## Troubleshooting

### User not recognized in natural language
- Make sure the English name is added to the user config
- Try using the exact Ukrainian name
- Check if the user is marked as active

### Colors not showing
- Verify the color code format (#RRGGBB)
- Refresh the calendar by requesting it again
- Check `/colors` to see current configuration

### Notifications not received
- Verify admin IDs in `.env` file
- Check that the admin hasn't blocked the bot
- Look for error logs in the terminal

---

## Migration from Hardcoded System

The system automatically creates default users on first run:
- Position 0: Діана (diana) - Blue
- Position 1: Дана (dana) - Purple
- Position 2: Женя (zhenya) - Green

And default combinations:
- Mask 3: Дана+Діана - Red
- Mask 5: Діана+Женя - Pink
- Mask 6: Дана+Женя - Yellow

Your existing schedule will continue to work without any changes needed.
