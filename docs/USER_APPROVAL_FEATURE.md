# User Approval Feature

## Overview
This feature implements a user approval system where new users must be approved by administrators before they can use the bot.

## Features

### 1. **New User Registration**
- When a user first uses `/start`, if they're not an admin and haven't been approved:
  - A `UserApproval` record is created with status "pending"
  - All admins receive a notification with approve/deny buttons
  - User sees a message that their request has been sent

### 2. **Admin Approval Workflow**
- Admins receive inline keyboard notifications with two buttons:
  - ✅ Approve - grants user access to the bot
  - ❌ Deny - denies user access
  
- Admins can view pending approvals with `/approvals` command

### 3. **User Status Messages**
- **New users**: "📬 Ваш запит на доступ до бота відправлено адміністраторам..."
- **Pending users**: "⏳ Ваш запит на доступ очікує розгляду адміністраторами..."
- **Denied users**: "❌ На жаль, вам було відмовлено в доступі до бота."
- **Approved users**: See normal welcome message

### 4. **Access Control**
- The `@require_approval` decorator checks if user is approved before executing handlers
- Admins (users in `config.ADMIN_IDS`) are always approved automatically
- Non-approved users cannot interact with the bot (except `/start`)

## Database Model

### UserApproval Table
```python
class UserApproval(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    telegram_id: int = Field(unique=True, index=True)
    telegram_username: str = ""
    telegram_first_name: str = ""
    telegram_last_name: str = ""
    full_name: str = ""
    status: str = "pending"  # pending, approved, denied
    requested_at: datetime = Field(default_factory=datetime.now)
    reviewed_at: Optional[datetime] = None
    reviewed_by: Optional[int] = None
    review_note: Optional[str] = None
```

## Commands

### User Commands
- `/start` - Register for bot access (creates approval request if new user)

### Admin Commands
- `/approvals` - View all pending user approval requests
- Each approval shows:
  - User's full name
  - Telegram ID
  - Username
  - Request timestamp
  - Inline keyboard with Approve/Deny buttons

## Implementation Details

### Bot Handlers

#### cmd_start()
```python
@router.message(CommandStart())
async def cmd_start(message: Message):
    # Check if admin (always approved)
    # Check if existing user and their approval status
    # Create UserApproval for new users
    # Notify admins about new user
    # Show appropriate message based on status
```

#### notify_admins_new_user()
```python
async def notify_admins_new_user(bot: Bot, approval):
    # Create notification message with user details
    # Create inline keyboard with approve/deny buttons
    # Send to all admins in config.ADMIN_IDS
```

#### require_approval() Decorator
```python
def require_approval(handler):
    # Check if user is admin (auto-approved)
    # Check if user is approved via repo.is_user_approved()
    # Block access if not approved
    # Show appropriate error message
```

#### Callback Handlers
```python
@router.callback_query(F.data.startswith("approve_user_"))
async def callback_approve_user(callback: CallbackQuery):
    # Extract user_id from callback data
    # Call repo.approve_user()
    # Update message to show approval
    # Notify user of approval
```

```python
@router.callback_query(F.data.startswith("deny_user_"))
async def callback_deny_user(callback: CallbackQuery):
    # Extract user_id from callback data
    # Call repo.deny_user()
    # Update message to show denial
    # Notify user of denial
```

### Repository Methods

- `create_user_approval(approval: UserApproval)` - Create new approval request
- `get_user_approval(telegram_id: int)` - Get approval by telegram ID
- `get_pending_approvals()` - List all pending approval requests
- `approve_user(telegram_id: int, admin_id: int)` - Approve user access
- `deny_user(telegram_id: int, admin_id: int)` - Deny user access
- `is_user_approved(telegram_id: int)` - Check if user is approved (admins auto-return True)

## User Flow

### New User Flow
1. User sends `/start`
2. Bot checks if user is admin → Yes: show full welcome, No: continue
3. Bot checks if UserApproval exists → No: create one
4. Bot sends notification to all admins
5. Bot tells user to wait for approval
6. Admin clicks ✅ Approve
7. Bot updates approval status to "approved"
8. Bot notifies user they can now use the bot
9. User sends `/start` again and sees welcome message

### Denied User Flow
1. Admin clicks ❌ Deny
2. Bot updates approval status to "denied"
3. Bot notifies user they were denied access
4. User sends `/start` → sees denial message

### Admin Viewing Pending Approvals
1. Admin sends `/approvals`
2. Bot shows list of pending approvals
3. Each approval has inline keyboard
4. Admin can approve/deny from list

## Success Messages

All assignment actions now return explicit success messages:

- **Single day assignment**: "✅ Призначено на DD.MM.YYYY: names"
- **Multiple days assignment**: "✅ Призначення завершено! 📅 Дні: X, Y, Z... 👥 Призначено: names"
- **Bulk assignment**: "✅ Масове призначення виконано! 📊 Кількість днів: X 👥 Призначено: names"
- **User approval**: "✅ Ваш доступ до бота схвалено!"
- **User denial**: "❌ На жаль, вам було відмовлено в доступі до бота."

## Testing

### Test Scenarios

1. **New user registration**:
   - Use test Telegram account
   - Send `/start`
   - Verify approval request created
   - Verify admin receives notification

2. **Admin approval**:
   - As admin, click ✅ Approve button
   - Verify user status updated to "approved"
   - Verify user receives notification
   - As approved user, send `/start` → should see welcome

3. **Admin denial**:
   - Create new user approval
   - As admin, click ❌ Deny button
   - Verify user status updated to "denied"
   - Verify user receives notification
   - As denied user, send `/start` → should see denial message

4. **Admin auto-approval**:
   - Add test user ID to config.ADMIN_IDS
   - Send `/start` as that user
   - Should see admin welcome immediately (no approval needed)

5. **Pending approvals list**:
   - Create multiple pending approval requests
   - As admin, send `/approvals`
   - Verify all pending requests shown with buttons

## Deployment

1. **Database Migration**:
   - The `init_db()` function will automatically create the `user_approvals` table
   - No manual migration needed

2. **Restart Bot**:
   ```bash
   docker-compose restart
   ```

3. **Verify**:
   - Check logs for successful database initialization
   - Test new user registration flow
   - Test admin approval flow

## Configuration

Add admin Telegram IDs to `.env`:
```env
ADMIN_IDS=123456789,987654321
```

These admins will:
- Be automatically approved
- Receive new user approval notifications
- Have access to `/approvals` command
- Be able to approve/deny user requests
