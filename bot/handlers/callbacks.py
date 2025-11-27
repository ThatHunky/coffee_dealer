"""Callback query handlers for inline buttons"""

from datetime import date
from aiogram import Router, F, types
from aiogram.types import CallbackQuery
from aiogram.exceptions import TelegramBadRequest

from bot.database.operations import (
    get_shift, create_or_update_shift, delete_shift,
    get_user, get_request, update_request_status,
    async_session_maker
)
from bot.services.calendar import (
    build_calendar_keyboard, build_day_user_selection_keyboard,
    get_calendar_text, generate_calendar_image, build_calendar_image_keyboard
)
from bot.services.notifications import notify_user_of_request_status
from bot.middleware.permissions import is_admin

router = Router()


@router.callback_query(F.data.startswith("ignore"))
async def callback_ignore(callback: CallbackQuery):
    """Ignore callback (for empty cells)"""
    await callback.answer()


@router.callback_query(F.data.startswith("calendar_"))
async def callback_calendar(callback: CallbackQuery):
    """Handle calendar navigation"""
    data = callback.data.split("_")
    year = int(data[1])
    month = int(data[2])
    
    # Generate calendar image
    image = await generate_calendar_image(year, month)
    keyboard = build_calendar_image_keyboard(year, month)
    text = get_calendar_text(year, month)
    
    # Edit photo if message has photo, otherwise send new
    try:
        if callback.message.photo:
            await callback.message.edit_media(
                media=types.InputMediaPhoto(media=image, caption=text),
                reply_markup=keyboard
            )
        else:
            await callback.message.delete()
            await callback.message.answer_photo(image, caption=text, reply_markup=keyboard)
    except TelegramBadRequest as e:
        # If edit fails because content is the same, just answer the callback
        # This can happen if user clicks the same month button
        if "not modified" in str(e).lower() or "same" in str(e).lower():
            await callback.answer()
            return
        # For other bad requests, re-raise
        raise
    except Exception as e:
        # For other errors, log and answer
        print(f"Error updating calendar: {e}")
        await callback.answer("⚠️ Помилка оновлення календаря")
        return
    
    await callback.answer()


@router.callback_query(F.data.startswith("history_"))
async def callback_history(callback: CallbackQuery):
    """Handle history calendar navigation"""
    data = callback.data.split("_")
    year = int(data[1])
    month = int(data[2])
    
    # Generate calendar image for history
    image = await generate_calendar_image(year, month, is_history=True)
    keyboard = build_calendar_image_keyboard(year, month, is_history=True)
    text = get_calendar_text(year, month, is_history=True)
    
    # Edit photo if message has photo, otherwise send new
    try:
        if callback.message.photo:
            await callback.message.edit_media(
                media=types.InputMediaPhoto(media=image, caption=text),
                reply_markup=keyboard
            )
        else:
            await callback.message.delete()
            await callback.message.answer_photo(image, caption=text, reply_markup=keyboard)
    except TelegramBadRequest as e:
        # If edit fails because content is the same, just answer the callback
        if "not modified" in str(e).lower() or "same" in str(e).lower():
            await callback.answer()
            return
        raise
    except Exception as e:
        # For other errors, log and answer
        print(f"Error updating history calendar: {e}")
        await callback.answer("⚠️ Помилка оновлення календаря")
        return
    
    await callback.answer()


@router.callback_query(F.data.startswith("edit_calendar_"))
async def callback_edit_calendar(callback: CallbackQuery):
    """Handle edit calendar button - switch to interactive keyboard mode"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Тільки адміністратори можуть редагувати календар.", show_alert=True)
        return
    
    data = callback.data.split("_")
    year = int(data[2])
    month = int(data[3])
    
    # Switch to interactive keyboard mode
    keyboard = await build_calendar_keyboard(year, month)
    text = get_calendar_text(year, month)
    
    # Edit message to show keyboard
    if callback.message.photo:
        await callback.message.delete()
        await callback.message.answer(text, reply_markup=keyboard)
    else:
        await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer("✏️ Режим редагування увімкнено")


@router.callback_query(F.data.startswith("view_calendar_"))
async def callback_view_calendar(callback: CallbackQuery):
    """Handle view calendar button - switch back to image view"""
    data = callback.data.split("_")
    year = int(data[2])
    month = int(data[3])
    
    # Generate calendar image
    image = await generate_calendar_image(year, month)
    keyboard = build_calendar_image_keyboard(year, month)
    text = get_calendar_text(year, month)
    
    # Delete text message and send image
    try:
        await callback.message.delete()
        await callback.message.answer_photo(image, caption=text, reply_markup=keyboard)
    except Exception as e:
        # If delete fails, try to edit instead
        if "message to delete not found" in str(e).lower():
            try:
                await callback.message.edit_text(text, reply_markup=keyboard)
            except:
                # If that also fails, just send new message
                await callback.message.answer_photo(image, caption=text, reply_markup=keyboard)
        else:
            raise
    
    await callback.answer()


@router.callback_query(F.data.startswith("day_"))
async def callback_day(callback: CallbackQuery):
    """Handle day button click - show user selection"""
    data = callback.data.split("_")
    year = int(data[1])
    month = int(data[2])
    day = int(data[3])
    
    keyboard = await build_day_user_selection_keyboard(year, month, day)
    current_date = date(year, month, day)
    text = f"📅 {current_date.strftime('%d.%m.%Y')}\n\nОберіть користувачів для цього дня:"
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("toggle_user_"))
async def callback_toggle_user(callback: CallbackQuery):
    """Handle user toggle for a day"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Тільки адміністратори можуть змінювати зміни.", show_alert=True)
        return
    
    data = callback.data.split("_")
    year = int(data[2])
    month = int(data[3])
    day = int(data[4])
    user_id = int(data[5])
    
    current_date = date(year, month, day)
    
    async with async_session_maker() as session:
        shift = await get_shift(session, current_date)
        current_user_ids = list(shift.user_ids) if shift else []
        
        # Toggle user
        if user_id in current_user_ids:
            current_user_ids.remove(user_id)
        else:
            current_user_ids.append(user_id)
        
        # Update shift
        if current_user_ids:
            await create_or_update_shift(session, current_date, current_user_ids)
        else:
            await delete_shift(session, current_date)
    
    # Refresh the selection keyboard
    keyboard = await build_day_user_selection_keyboard(year, month, day)
    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer("✅ Оновлено")


@router.callback_query(F.data.startswith("clear_day_"))
async def callback_clear_day(callback: CallbackQuery):
    """Handle clear day button"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Тільки адміністратори можуть змінювати зміни.", show_alert=True)
        return
    
    data = callback.data.split("_")
    year = int(data[2])
    month = int(data[3])
    day = int(data[4])
    
    current_date = date(year, month, day)
    
    async with async_session_maker() as session:
        await delete_shift(session, current_date)
    
    # Refresh the selection keyboard
    keyboard = await build_day_user_selection_keyboard(year, month, day)
    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer("✅ День очищено")


@router.callback_query(F.data.startswith("approve_request_"))
async def callback_approve_request(callback: CallbackQuery):
    """Handle request approval"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Тільки адміністратори можуть затверджувати запити.", show_alert=True)
        return
    
    request_id = int(callback.data.split("_")[2])
    
    async with async_session_maker() as session:
        request = await get_request(session, request_id)
        if not request:
            await callback.answer("❌ Запит не знайдено.", show_alert=True)
            return
        
        if request.status != "pending":
            await callback.answer(f"❌ Запит вже оброблено ({request.status}).", show_alert=True)
            return
        
        # Update status
        await update_request_status(session, request_id, "approved")
        
        # Execute the request if possible
        parsed_intent = request.parsed_intent or {}
        action = parsed_intent.get("action")
        dates = parsed_intent.get("dates", [])
        user_ids = parsed_intent.get("user_ids", [])
        
        # Simple execution for assign/unassign actions
        if action in ["assign", "unassign"] and dates and user_ids:
            from datetime import datetime as dt
            for date_str in dates:
                try:
                    shift_date = dt.strptime(date_str, "%Y-%m-%d").date()
                    shift = await get_shift(session, shift_date)
                    current_user_ids = list(shift.user_ids) if shift else []
                    
                    if action == "assign":
                        for uid in user_ids:
                            if uid not in current_user_ids:
                                current_user_ids.append(uid)
                    elif action == "unassign":
                        for uid in user_ids:
                            if uid in current_user_ids:
                                current_user_ids.remove(uid)
                    
                    if current_user_ids:
                        await create_or_update_shift(session, shift_date, current_user_ids)
                    else:
                        await delete_shift(session, shift_date)
                except Exception as e:
                    print(f"Error executing request: {e}")
        
        # Notify user
        from bot.services.notifications import notify_user_of_request_status
        await notify_user_of_request_status(
            callback.bot,
            request.user_id,
            request_id,
            "approved"
        )
    
    await callback.answer("✅ Запит затверджено")
    await callback.message.edit_text(
        callback.message.text + "\n\n✅ Затверджено адміністратором"
    )


@router.callback_query(F.data.startswith("reject_request_"))
async def callback_reject_request(callback: CallbackQuery):
    """Handle request rejection"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Тільки адміністратори можуть відхиляти запити.", show_alert=True)
        return
    
    request_id = int(callback.data.split("_")[2])
    
    async with async_session_maker() as session:
        request = await get_request(session, request_id)
        if not request:
            await callback.answer("❌ Запит не знайдено.", show_alert=True)
            return
        
        if request.status != "pending":
            await callback.answer(f"❌ Запит вже оброблено ({request.status}).", show_alert=True)
            return
        
        await update_request_status(session, request_id, "rejected")
        
        # Notify user
        await notify_user_of_request_status(
            callback.bot,
            request.user_id,
            request_id,
            "rejected"
        )
    
    await callback.answer("❌ Запит відхилено")
    await callback.message.edit_text(
        callback.message.text + "\n\n❌ Відхилено адміністратором"
    )

