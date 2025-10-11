# Change Request & Notification System Implementation

## ✅ Completed

### 1. **Gemini Timeout Fix** 
- **Problem**: Timeout after 3 seconds was causing "help" fallback responses
- **Solution**: 
  - Increased timeout from 3s to 8s
  - Added retry logic (2 attempts with 0.5s delay between retries)
  - More robust error handling
- **File**: `src/nlp.py` lines 140-162

### 2. **Multi-Day Assignment Support**
- Added support for assigning multiple people to multiple days
- Three assignment types:
  - `assign_day` - single day
  - `assign_days` - specific multiple days (e.g., "7, 8, 20")
  - `assign_bulk` - pattern-based (e.g., "all Sundays")
- **Files**: `src/intents.py`, `src/nlp.py`, `src/bot.py`

### 3. **Database Models for Change Requests**
- Added `ChangeRequest` model in `src/models.py`
- Stores pending change requests from non-admin users
- Fields: request_type, days, people, pattern, status, reviewed_by, etc.
- **File**: `src/models.py` lines 174-227

### 4. **Repository Methods**
- Added methods in `src/repo.py`:
  - `create_change_request()` - create new request
  - `get_pending_requests()` - list pending requests
  - `approve_request()` - approve and apply changes
  - `deny_request()` - deny request
- **File**: `src/repo.py` lines 293-348

## 🚧 TODO - Change Request/Approval System

### What Needs to Be Implemented:

#### 1. **Modify Assignment Handlers** (`src/bot.py`)
Current handlers check `is_admin()` and reject non-admins. Need to:

```python
async def handle_assign_day(message: Message, cmd: NLCommand):
    if is_admin(message.from_user.id):
        # Apply changes directly
        # ... existing code ...
    else:
        # Create change request
        request = ChangeRequest(
            request_type="assign_day",
            requested_by=message.from_user.id,
            requested_by_name=message.from_user.full_name,
            days=json.dumps([cmd.day]),
            people=json.dumps(cmd.people),
            year=cmd.year,
            month=cmd.month
        )
        repo.create_change_request(request)
        # Notify admins
        await send_request_notification(bot, request)
```

Do this for:
- `handle_assign_day()`
- `handle_assign_days()`
- `handle_assign_bulk()`

#### 2. **Inline Keyboard Callbacks**
Add callback handlers for approve/deny buttons:

```python
from aiogram import F
from aiogram.types import CallbackQuery

@router.callback_query(F.data.startswith("approve_"))
async def approve_request_callback(callback: CallbackQuery):
    request_id = int(callback.data.split("_")[1])
    request = repo.get_change_request(request_id)
    
    # Apply the changes
    if request.request_type == "assign_day":
        days = json.loads(request.days)
        people = json.loads(request.people)
        assignment = Assignment.from_people(
            day=date(request.year, request.month, days[0]),
            people=people
        )
        repo.upsert_with_notification(assignment, callback.from_user.id)
    
    # Mark as approved
    repo.approve_request(request_id, callback.from_user.id)
    
    # Notify requester
    await callback.bot.send_message(
        request.requested_by,
        f"✅ Ваш запит схвалено!\n📅 {request.get_description()}"
    )
    
    await callback.answer("Запит схвалено!")

@router.callback_query(F.data.startswith("deny_"))
async def deny_request_callback(callback: CallbackQuery):
    request_id = int(callback.data.split("_")[1])
    request = repo.get_change_request(request_id)
    
    repo.deny_request(request_id, callback.from_user.id, "Відхилено адміністратором")
    
    # Notify requester
    await callback.bot.send_message(
        request.requested_by,
        f"❌ Ваш запит відхилено\n📅 {request.get_description()}"
    )
    
    await callback.answer("Запит відхилено!")
```

#### 3. **Request Notification Function**
```python
async def send_request_notification(bot: Bot, request: ChangeRequest):
    """Send change request to admins for approval."""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    text = (
        f"📬 Новий запит на зміну розкладу\n\n"
        f"👤 Від: {request.requested_by_name}\n"
        f"📝 {request.get_description()}\n"
        f"📅 {request.month}/{request.year}\n"
        f"⏰ {request.requested_at.strftime('%d.%m %H:%M')}"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Схвалити", callback_data=f"approve_{request.id}"),
            InlineKeyboardButton(text="❌ Відхилити", callback_data=f"deny_{request.id}")
        ]
    ])
    
    for admin_id in config.ADMIN_IDS:
        await bot.send_message(admin_id, text, reply_markup=keyboard)
```

#### 4. **Notify ALL Users on Changes**
Modify `send_change_notification()` to notify everyone, not just admins:

```python
async def send_change_notification(bot: Bot, notification: ChangeNotification):
    """Send change notification to ALL users."""
    # Get all subscribed user IDs (you need to track this)
    # For now, just notify admins
    notify_users = set(config.ADMIN_IDS)
    
    # TODO: Add database table for subscribed users
    # subscribed_users = repo.get_subscribed_users()
    # notify_users.update([u.telegram_id for u in subscribed_users])
    
    for user_id in notify_users:
        if user_id != notification.changed_by:
            await bot.send_message(user_id, notification_text)
```

#### 5. **Admin Commands**
Add commands to view/manage requests:

```python
@router.message(Command("requests"))
async def cmd_requests(message: Message):
    """View pending change requests (admin only)."""
    if not is_admin(message.from_user.id):
        await message.answer("🔒 Команда доступна лише адміністраторам.")
        return
    
    requests = repo.get_pending_requests(limit=10)
    if not requests:
        await message.answer("📭 Немає pending запитів.")
        return
    
    for req in requests:
        text = (
            f"📬 Запит #{req.id}\n"
            f"👤 {req.requested_by_name}\n"
            f"📝 {req.get_description()}\n"
            f"⏰ {req.requested_at.strftime('%d.%m %H:%M')}"
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅", callback_data=f"approve_{req.id}"),
                InlineKeyboardButton(text="❌", callback_data=f"deny_{req.id}")
            ]
        ])
        await message.answer(text, reply_markup=keyboard)
```

#### 6. **User Subscription System** (Optional Enhancement)
Create a table to track who wants notifications:

```python
class NotificationSubscription(SQLModel, table=True):
    __tablename__ = "notification_subscriptions"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    telegram_id: int = Field(index=True, unique=True)
    telegram_username: str = Field(default="")
    subscribed_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = Field(default=True)
```

Add `/subscribe` and `/unsubscribe` commands.

## 📝 Implementation Order

1. ✅ Fix Gemini timeout (DONE)
2. ✅ Add ChangeRequest model (DONE)
3. ✅ Add repository methods (DONE)
4. Modify assignment handlers to create requests for non-admins
5. Add inline keyboard callback handlers
6. Add request notification function
7. Modify change notification to notify all users
8. Add `/requests` admin command
9. Test the full workflow
10. (Optional) Add user subscription system

## 🧪 Testing Checklist

- [ ] Admin can assign directly
- [ ] Non-admin creates request
- [ ] Admin receives notification with buttons
- [ ] Admin can approve request
- [ ] Changes are applied on approval
- [ ] Requester is notified of approval
- [ ] Admin can deny request  
- [ ] Requester is notified of denial
- [ ] All users receive notification when schedule changes
- [ ] `/requests` shows pending requests

## 🔧 Files to Modify

1. `src/bot.py` - Main handlers and callbacks
2. `src/repo.py` - Already updated with request methods
3. `src/models.py` - Already has ChangeRequest model
4. `src/nlp.py` - Already fixed timeout

## 💡 Notes

- The ChangeRequest model is generic and works for all three assignment types
- Use `json.dumps()` and `json.loads()` for storing arrays in the database
- The `days` field stores a JSON array even for single-day requests for consistency
- The inline keyboard buttons are automatically attached to requests for quick approval
