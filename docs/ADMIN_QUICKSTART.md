# Quick Start: Admin Features

## Installation

The new features are already integrated. Just run the bot as usual:

```bash
python -m src.main
```

The database will automatically:
1. Create new tables (`user_configs`, `combination_colors`, `change_notifications`)
2. Initialize default users (Діана, Дана, Женя)
3. Set up default combination colors

## Basic Admin Tasks

### 1. View Current Users

```
/users
```

This shows all configured users with their colors and bit positions.

### 2. Add a New User

```
/adduser 3 Олена olena #FF69B4
```

This creates a new user:
- **Position**: 3 (next available)
- **Ukrainian name**: Олена
- **English name**: olena (for voice commands)
- **Color**: Pink (#FF69B4)

### 3. Assign the New User

Now you can use natural language:

```
постав Олену на 15 жовтня
```

Or combine users:

```
Олена і Діана на 20 числа
```

### 4. Set Combination Color

When Олена works with Діана (positions 3 and 0):
- Олена (position 3) = 2^3 = 8
- Діана (position 0) = 2^0 = 1
- Combined mask = 8 + 1 = 9

```
/setcombo 9 #FF1493 Олена+Діана
```

### 5. View All Colors

```
/colors
```

Shows the complete color scheme for your team.

### 6. Monitor Changes

```
/changes
```

See what's been modified in the last 7 days.

## Common Scenarios

### Scenario 1: Seasonal Worker

Add a temporary worker for summer months:

```
/adduser 4 Іван ivan #3498DB
```

Use them in assignments:

```
Іван і Женя на червень
```

When they leave, deactivate them:

```
/removeuser ivan
```

When they return next year, reactivate:

```
/activateuser ivan
```

### Scenario 2: Changing Colors

Want to change Діана's color from blue to purple?

```
/edituser diana - - #9B59B6
```

(The dashes mean "don't change name")

### Scenario 3: Fixing a Typo in Name

Accidentally typed "Daina" instead of "Diana"?

```
/edituser 0 Діана diana -
```

### Scenario 4: Temporary Deactivation

Employee on vacation for a month:

```
/removeuser zhenya
```

When they return:

```
/activateuser zhenya
```

### Scenario 2: Changing Colors (Legacy)

Want to change Діана's color from blue to purple?

```
/adduser 0 Діана diana #9B59B6
```

This updates the existing user at position 0.

### Scenario 3: Custom Team Colors

Set a special color when all three work together:

- Діана (0) = 1
- Дана (1) = 2
- Женя (2) = 4
- All = 1 + 2 + 4 = 7

```
/setcombo 7 #FFA500 Повний склад
```

## Notifications

Whenever you make a change, other admins receive:

```
🔔 Зміна в розкладі

📅 Дата: 11.10.2025
👤 Було: Діана
👤 Стало: Діана, Женя
⏰ 14:30:45
```

**Note:** You don't receive notifications for your own changes, only other admins do.

## Troubleshooting

### "User not found" when assigning

Make sure:
1. User is added with `/adduser`
2. English name matches what you type
3. User is active

Check with `/users` to verify.

### Colors not showing

1. Run `/colors` to see current config
2. Request calendar again: `показати жовтень`
3. Check color format is `#RRGGBB`

### No notifications received

1. Check `.env` has correct `ADMIN_IDS`
2. Make sure admin hasn't blocked the bot
3. You won't see notifications for your own changes

## Tips

1. **Use sequential bit positions**: 0, 1, 2, 3... easier to track
2. **Test on future dates**: Try new users on tomorrow's date first
3. **Contrasting colors**: Make sure colors are visually distinct
4. **Document combinations**: Keep a note of which masks mean what
5. **Regular backups**: Back up `schedule.db` regularly

## Color Suggestions

| User Type | Color | Code |
|-----------|-------|------|
| Regular staff | Blue | #4A90E2 |
| Manager | Purple | #9B59B6 |
| Part-time | Green | #27AE60 |
| Trainee | Yellow | #F1C40F |
| Special | Orange | #F39C12 |

| Combination | Color | Code |
|-------------|-------|------|
| Power duo | Pink | #E91E63 |
| Full team | Orange | #FFA500 |
| Emergency | Red | #E74C3C |

## Next Steps

1. Review current users with `/users`
2. Customize colors if needed
3. Add any new team members
4. Set up combination colors for common pairings
5. Monitor changes with `/changes`

For detailed documentation, see `ADMIN_GUIDE.md`.
