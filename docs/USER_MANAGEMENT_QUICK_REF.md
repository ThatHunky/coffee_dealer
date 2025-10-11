# User Management Feature - Quick Reference

## 🎯 What's New?

Three new admin commands for managing users without database access:

| Command | Description | Example |
|---------|-------------|---------|
| `/edituser` | Edit user details | `/edituser diana - - #FF5733` |
| `/removeuser` | Deactivate user | `/removeuser zhenya` |
| `/activateuser` | Reactivate user | `/activateuser zhenya` |

## 📝 Quick Usage

### Edit a User

Change only what you need (use `-` to skip):

```bash
# Change only color
/edituser diana - - #FF6B9D

# Change only name
/edituser 0 Діанка dianochka -

# Change everything
/edituser 1 Дана dana #AA55FF
```

### Deactivate/Reactivate

For temporary removal (vacation, leave):

```bash
# Deactivate
/removeuser ivan

# Reactivate later
/activateuser ivan
```

### Find Users

Check who's active/inactive:

```bash
/users
```

Output:
```
✅ = Active
❌ = Inactive
```

## 🔍 Key Features

- ✅ **Flexible Lookup** - Find by position (0-7) or name
- ✅ **Partial Updates** - Use `-` to skip fields
- ✅ **Soft Delete** - Deactivate without losing data
- ✅ **History Preserved** - All assignments stay in database
- ✅ **Easy Reactivation** - One command to restore

## 📚 Documentation

- **Full Guide**: [`USER_MANAGEMENT_FEATURE.md`](./USER_MANAGEMENT_FEATURE.md)
- **Summary**: [`USER_MANAGEMENT_SUMMARY.md`](./USER_MANAGEMENT_SUMMARY.md)
- **Admin Reference**: [`ADMIN_GUIDE.md`](./ADMIN_GUIDE.md)

## 🚀 Common Scenarios

### Scenario 1: Color Change
```bash
/edituser diana - - #FF0000
```

### Scenario 2: Name Fix
```bash
/edituser 0 Діана diana -
```

### Scenario 3: Vacation Mode
```bash
# Before vacation
/removeuser zhenya

# After vacation (2 weeks later)
/activateuser zhenya
```

### Scenario 4: Seasonal Worker
```bash
# Hire for summer
/adduser 4 Іван ivan #3498DB

# End of season
/removeuser ivan

# Next year
/activateuser ivan
```

## ⚠️ Important Notes

1. **Deactivation ≠ Deletion**
   - User data stays in database
   - Can reactivate anytime
   - History preserved

2. **Admin Only**
   - All commands require admin rights
   - Operations are logged

3. **Active Status**
   - Only active users appear in schedules
   - Inactive users shown with ❌ in `/users`

## 🔐 Security

- ✅ Admin permission check
- ✅ Input validation
- ✅ Comprehensive logging
- ✅ User ID audit trail

## 🎨 Bot Menu

New commands appear in admin menu:
- ✏️ Редагувати користувача
- 🗑️ Деактивувати користувача  
- ✅ Активувати користувача

---

**Version**: 1.0  
**Date**: 2025-10-11  
**Status**: ✅ Production Ready
