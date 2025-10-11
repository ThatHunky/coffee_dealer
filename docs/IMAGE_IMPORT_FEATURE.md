# 📸 Image Import Feature

## Overview

The Coffee Dealer bot now supports **automatic schedule extraction from calendar images** using Google Gemini Vision AI. Admins can simply upload a photo of a calendar, and the bot will intelligently recognize the schedule and import all assignments.

## 🎯 What It Does

- **Analyzes calendar images** using Gemini Vision (gemini-2.0-flash-exp)
- **Recognizes color-coded assignments** (blue, purple, green, red, pink, yellow, rainbow)
- **Extracts month, year, and all day assignments**
- **Provides a preview and confirmation** before importing
- **Bulk imports** all recognized assignments into the database

## 🖼️ Supported Calendar Formats

The feature works with calendar images that have:

- **Month name and year** clearly visible (Ukrainian month names supported)
- **Color-coded day circles** indicating worker assignments
- **Standard calendar grid layout** (days 1-31)

### Color Legend Recognition

The AI recognizes these color patterns:

| Color | Person(s) | Emoji |
|-------|-----------|-------|
| 🔵 Blue (Синій) | Diana | 🔵 |
| 🟣 Purple (Фіолетовий) | Dana | 🟣 |
| 🟢 Green (Зелений) | Zhenya | 🟢 |
| 🔴 Red/Brown (Червоний) | Diana + Dana | 🔴 |
| 🩷 Pink (Рожевий) | Diana + Zhenya | 🩷 |
| 🟡 Yellow (Жовтий) | Dana + Zhenya | 🟡 |
| 🌈 Multi-color | All three | 🌈 |

**White/empty days** are skipped (no assignment).

## 📋 How To Use

### For Admins

1. **Take or receive a photo** of the schedule calendar
2. **Send the photo** to the bot (as a regular image message)
3. **Wait for analysis** (5-15 seconds)
4. **Review the extracted schedule** - bot shows:
   - Month and year
   - Total assignments found
   - Breakdown by person
5. **Confirm or cancel** using inline buttons:
   - ✅ "Так, зберегти" - imports all assignments
   - ❌ "Скасувати" - cancels import

### Example Workflow

```
Admin: [Uploads calendar photo]
Bot: 🔍 Аналізую календар...

Bot: 📅 Знайдено розклад: Жовтень 2025

Знайдено 25 призначень:

Діана 🔵: 1, 2, 6, 7, 15, 20, 22, 29, 31
Дана 🟣: 9, 11, 13, 14, 16, 21, 23, 27, 28, 30
Женя 🟢: 3, 8, 10, 17, 24

✅ Зберегти ці призначення?

[✅ Так, зберегти] [❌ Скасувати]

Admin: [Clicks ✅ Так, зберегти]

Bot: ✅ Імпортовано 25 призначень для Жовтень 2025
```

## 🔒 Permissions

- **Admin-only feature**: Only users in `ADMIN_IDS` can upload schedule images
- **Regular users** who upload photos will receive:
  ```
  ❌ Лише адміністратори можуть імпортувати розклади з зображень.
  ```

## 🛠️ Technical Implementation

### Files Modified

1. **`src/intents.py`**
   - Added `parse_schedule_image` action to `NLCommand`
   - Added `DayAssignment` model for individual day assignments
   - Added `ScheduleFromImage` Pydantic model for structured extraction

2. **`src/nlp.py`**
   - Added `parse_schedule_from_image()` async function
   - Implemented Gemini Vision integration with custom prompts
   - Handles image bytes → JSON structured data conversion
   - Error handling with Ukrainian error messages

3. **`src/bot.py`**
   - Added `pending_schedule_imports` dict for confirmation flow
   - Added `@router.message(F.photo)` handler for photo uploads
   - Added `handle_confirm_import()` callback for confirmation
   - Added `handle_cancel_import()` callback for cancellation
   - Updated help text to mention image import feature

### Gemini Vision Configuration

```python
types.GenerateContentConfig(
    system_instruction=image_instruction,  # Detailed Ukrainian prompt
    response_mime_type="application/json",
    response_schema=ScheduleFromImage,     # Pydantic schema
    temperature=0.1,                        # Deterministic output
)
```

### Data Flow

```
Photo Upload
    ↓
Download Image (Bot API)
    ↓
Gemini Vision Analysis (15s timeout)
    ↓
JSON Response → ScheduleFromImage
    ↓
Store in pending_schedule_imports[user_id]
    ↓
Show Preview + Confirmation Buttons
    ↓
[User Confirms]
    ↓
Loop through assignments:
    - Create Assignment.from_people()
    - repo.upsert() each day
    ↓
Clear pending import
    ↓
Show success message with count
```

## 🧪 Testing Scenarios

### Valid Cases
- ✅ Calendar with Ukrainian month name (Жовтень)
- ✅ Single-color days (one person per day)
- ✅ Multi-color days (combinations)
- ✅ Mixed assignments throughout month
- ✅ Partial month (only some days assigned)

### Edge Cases
- ⚠️ **Empty calendar** (no colored days) → Shows warning
- ⚠️ **Invalid dates** (e.g., day 32) → Skips with error message
- ⚠️ **Unrecognized colors** → Best-effort mapping
- ⚠️ **Blurry/low quality** → Error message to retry
- ⚠️ **Non-calendar image** → Error or empty result

### Error Handling
- **Timeout (15s)**: "Час очікування відповіді від AI минув. Спробуйте ще раз."
- **JSON decode error**: "Не вдалось розпізнати календар. Спробуйте інше зображення."
- **General exception**: "Помилка аналізу зображення: {error}"

## 📊 Logging

All image processing events are logged:

```python
logger.info(f"Admin {user_id} uploaded schedule image, file_id={photo.file_id}")
logger.debug(f"Downloaded image: {len(image_data)} bytes")
logger.info(f"Extracted schedule for {month}/{year}: {count} assignments")
logger.info(f"Imported from image: {date} -> {people}")
logger.info(f"Admin {user_id} imported schedule: {month} {year} ({count} days)")
```

Errors logged with `exc_info=True` for full traceback.

## 🔄 Dependencies

No new dependencies required! Uses existing:
- `google-genai>=0.1.0` (already installed for NLP)
- Gemini 2.0 Flash Exp model (supports vision)
- `aiogram>=3.15.0` (for photo handling)

## 🎨 UI/UX Features

- **Progress indicator**: "🔍 Аналізую календар..." while processing
- **Visual summary**: Emoji-enhanced breakdown by person
- **Clear confirmation**: Two-button inline keyboard
- **Success feedback**: Shows count of imported assignments
- **Error messages**: All in Ukrainian with actionable guidance

## 🚀 Future Enhancements

Potential improvements:

1. **Multi-month support**: Import several months at once
2. **Conflict detection**: Warn if overwriting existing assignments
3. **Undo feature**: Rollback last import
4. **Export to image**: Generate calendar image from DB
5. **OCR fallback**: Non-AI text extraction for simple calendars
6. **Template learning**: Improve recognition from user feedback

## 📚 Related Documentation

- [NLP Guide](./LOGGING_GUIDE.md) - General Gemini integration
- [Admin Guide](./ADMIN_GUIDE.md) - Admin commands overview
- [User Management](./USER_MANAGEMENT_SUMMARY.md) - User permissions

## ✅ Summary

The image import feature dramatically simplifies schedule management by allowing admins to:
- Upload a calendar photo instead of manual data entry
- Leverage AI to extract all assignments automatically
- Review before confirming to prevent errors
- Save hours of tedious schedule input

**Perfect for:** Importing monthly schedules from paper calendars, screenshots, or photos sent by managers.
