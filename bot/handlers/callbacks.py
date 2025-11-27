"""Callback query handlers for inline buttons"""

from datetime import date
from aiogram import Router, F, types
from aiogram.types import CallbackQuery
from aiogram.exceptions import TelegramBadRequest
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.database.operations import (
    get_shift,
    create_or_update_shift,
    delete_shift,
    get_user,
    get_request,
    update_request_status,
    delete_shifts_for_month,
    async_session_maker,
)
from bot.services.calendar import (
    build_calendar_keyboard,
    build_day_user_selection_keyboard,
    get_calendar_text,
    generate_calendar_image,
    build_calendar_image_keyboard,
    get_month_name_ukrainian,
)
from bot.services.notifications import notify_user_of_request_status
from bot.services.undo import undo_service
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
                reply_markup=keyboard,
            )
        else:
            await callback.message.delete()
            await callback.message.answer_photo(
                image, caption=text, reply_markup=keyboard
            )
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
                reply_markup=keyboard,
            )
        else:
            await callback.message.delete()
            await callback.message.answer_photo(
                image, caption=text, reply_markup=keyboard
            )
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
        await callback.answer(
            "❌ Тільки адміністратори можуть редагувати календар.", show_alert=True
        )
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
                await callback.message.answer_photo(
                    image, caption=text, reply_markup=keyboard
                )
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
    text = (
        f"📅 {current_date.strftime('%d.%m.%Y')}\n\nОберіть користувачів для цього дня:"
    )

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("toggle_user_"))
async def callback_toggle_user(callback: CallbackQuery):
    """Handle user toggle for a day"""
    if not is_admin(callback.from_user.id):
        await callback.answer(
            "❌ Тільки адміністратори можуть змінювати зміни.", show_alert=True
        )
        return

    data = callback.data.split("_")
    year = int(data[2])
    month = int(data[3])
    day = int(data[4])
    user_id = int(data[5])

    current_date = date(year, month, day)

    async with async_session_maker() as session:
        shift = await get_shift(session, current_date)
        previous_user_ids = list(shift.user_ids) if shift else []

        # Store previous state for undo
        undo_action_id = undo_service.create_undo_action(
            action_type="toggle_user",
            previous_state={
                "date": current_date.isoformat(),
                "user_ids": previous_user_ids.copy(),
                "year": year,
                "month": month,
                "day": day,
            },
        )

        # Toggle user
        if user_id in previous_user_ids:
            current_user_ids = [uid for uid in previous_user_ids if uid != user_id]
        else:
            current_user_ids = previous_user_ids + [user_id]

        # Update shift
        if current_user_ids:
            await create_or_update_shift(session, current_date, current_user_ids)
        else:
            await delete_shift(session, current_date)

    # Refresh the selection keyboard with undo button
    keyboard = await build_day_user_selection_keyboard(
        year, month, day, undo_action_id=undo_action_id
    )
    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer("✅ Оновлено")


@router.callback_query(F.data.startswith("clear_day_"))
async def callback_clear_day(callback: CallbackQuery):
    """Handle clear day button"""
    if not is_admin(callback.from_user.id):
        await callback.answer(
            "❌ Тільки адміністратори можуть змінювати зміни.", show_alert=True
        )
        return

    data = callback.data.split("_")
    year = int(data[2])
    month = int(data[3])
    day = int(data[4])

    current_date = date(year, month, day)

    async with async_session_maker() as session:
        shift = await get_shift(session, current_date)
        previous_user_ids = list(shift.user_ids) if shift else []

        # Store previous state for undo
        undo_action_id = undo_service.create_undo_action(
            action_type="clear_day",
            previous_state={
                "date": current_date.isoformat(),
                "user_ids": previous_user_ids.copy(),
                "year": year,
                "month": month,
                "day": day,
            },
        )

        await delete_shift(session, current_date)

    # Refresh the selection keyboard with undo button
    keyboard = await build_day_user_selection_keyboard(
        year, month, day, undo_action_id=undo_action_id
    )
    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer("✅ День очищено")


@router.callback_query(F.data.startswith("approve_request_"))
async def callback_approve_request(callback: CallbackQuery):
    """Handle request approval"""
    if not is_admin(callback.from_user.id):
        await callback.answer(
            "❌ Тільки адміністратори можуть затверджувати запити.", show_alert=True
        )
        return

    request_id = int(callback.data.split("_")[2])

    async with async_session_maker() as session:
        request = await get_request(session, request_id)
        if not request:
            await callback.answer("❌ Запит не знайдено.", show_alert=True)
            return

        if request.status != "pending":
            await callback.answer(
                f"❌ Запит вже оброблено ({request.status}).", show_alert=True
            )
            return

        # Store previous state for undo (before any changes)
        parsed_intent = request.parsed_intent or {}
        action = parsed_intent.get("action")
        dates = parsed_intent.get("dates", [])
        user_ids = parsed_intent.get("user_ids", [])

        previous_states = {}
        if action in ["assign", "unassign"] and dates and user_ids:
            from datetime import datetime as dt

            for date_str in dates:
                try:
                    shift_date = dt.strptime(date_str, "%Y-%m-%d").date()
                    shift = await get_shift(session, shift_date)
                    previous_states[date_str] = list(shift.user_ids) if shift else []
                except Exception as e:
                    print(f"Error getting previous state: {e}")

        # Store undo action
        undo_action_id = undo_service.create_undo_action(
            action_type="approve_request",
            previous_state={
                "request_id": request_id,
                "previous_status": request.status,
                "previous_states": previous_states,
                "action": action,
                "dates": dates,
                "user_ids": user_ids,
            },
        )

        # Update status
        await update_request_status(session, request_id, "approved")

        # Execute the request if possible
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
                        await create_or_update_shift(
                            session, shift_date, current_user_ids
                        )
                    else:
                        await delete_shift(session, shift_date)
                except Exception as e:
                    print(f"Error executing request: {e}")

        # Notify user
        from bot.services.notifications import notify_user_of_request_status

        await notify_user_of_request_status(
            callback.bot, request.user_id, request_id, "approved"
        )

    # Add undo button to message
    builder = InlineKeyboardBuilder()
    builder.button(text="↩️ Скасувати", callback_data=f"undo_{undo_action_id}")

    await callback.answer("✅ Запит затверджено")
    await callback.message.edit_text(
        callback.message.text + "\n\n✅ Затверджено адміністратором",
        reply_markup=builder.as_markup(),
    )


@router.callback_query(F.data.startswith("reject_request_"))
async def callback_reject_request(callback: CallbackQuery):
    """Handle request rejection"""
    if not is_admin(callback.from_user.id):
        await callback.answer(
            "❌ Тільки адміністратори можуть відхиляти запити.", show_alert=True
        )
        return

    request_id = int(callback.data.split("_")[2])

    async with async_session_maker() as session:
        request = await get_request(session, request_id)
        if not request:
            await callback.answer("❌ Запит не знайдено.", show_alert=True)
            return

        if request.status != "pending":
            await callback.answer(
                f"❌ Запит вже оброблено ({request.status}).", show_alert=True
            )
            return

        # Store previous state for undo
        undo_action_id = undo_service.create_undo_action(
            action_type="reject_request",
            previous_state={
                "request_id": request_id,
                "previous_status": request.status,
            },
        )

        await update_request_status(session, request_id, "rejected")

        # Notify user
        await notify_user_of_request_status(
            callback.bot, request.user_id, request_id, "rejected"
        )

    # Add undo button to message
    builder = InlineKeyboardBuilder()
    builder.button(text="↩️ Скасувати", callback_data=f"undo_{undo_action_id}")

    await callback.answer("❌ Запит відхилено")
    await callback.message.edit_text(
        callback.message.text + "\n\n❌ Відхилено адміністратором",
        reply_markup=builder.as_markup(),
    )


@router.callback_query(F.data.startswith("confirm_clear_month_"))
async def callback_confirm_clear_month(callback: CallbackQuery):
    """Handle confirm clear month button"""
    if not is_admin(callback.from_user.id):
        await callback.answer(
            "❌ Тільки адміністратори можуть виконувати цю дію.", show_alert=True
        )
        return

    data = callback.data.split("_")
    year = int(data[3])
    month = int(data[4])

    month_name = get_month_name_ukrainian(month)

    async with async_session_maker() as session:
        # Get shifts before deletion for undo
        from bot.database.operations import get_shifts_in_range
        from calendar import monthrange

        first_day = date(year, month, 1)
        last_day_num = monthrange(year, month)[1]
        last_day = date(year, month, last_day_num)
        shifts = await get_shifts_in_range(session, first_day, last_day)

        # Store previous state for undo
        previous_states = {}
        for shift in shifts:
            previous_states[shift.date.isoformat()] = list(shift.user_ids)

        # Create undo action
        undo_action_id = undo_service.create_undo_action(
            action_type="clear_month",
            previous_state={
                "year": year,
                "month": month,
                "previous_states": previous_states,
            },
        )

        # Delete all shifts for the month
        deleted_shifts = await delete_shifts_for_month(session, year, month)
        deleted_count = len(deleted_shifts)

    # Update message with result and undo button
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()
    builder.button(text="↩️ Скасувати", callback_data=f"undo_{undo_action_id}")

    text = (
        f"✅ <b>Місяць очищено</b>\n\n"
        f"Всі зміни для <b>{month_name} {year}</b> були видалені.\n\n"
        f"📊 Видалено змін: <b>{deleted_count}</b>"
    )

    await callback.message.edit_text(
        text, reply_markup=builder.as_markup(), parse_mode="HTML"
    )
    await callback.answer("✅ Місяць очищено")


@router.callback_query(F.data.startswith("cancel_clear_month_"))
async def callback_cancel_clear_month(callback: CallbackQuery):
    """Handle cancel clear month button"""
    await callback.message.edit_text("❌ Очищення місяця скасовано.")
    await callback.answer("❌ Скасовано")


@router.callback_query(F.data.startswith("undo_"))
async def callback_undo(callback: CallbackQuery):
    """Handle undo action"""
    if not is_admin(callback.from_user.id):
        await callback.answer(
            "❌ Тільки адміністратори можуть скасовувати дії.", show_alert=True
        )
        return

    action_id = callback.data.split("_", 1)[1]
    undo_action = undo_service.get_undo_action(action_id)

    if not undo_action:
        await callback.answer(
            "❌ Дію не знайдено або вона вже недійсна.", show_alert=True
        )
        return

    previous_state = undo_action.previous_state
    action_type = undo_action.action_type

    try:
        if action_type == "toggle_user" or action_type == "clear_day":
            # Restore shift state
            shift_date = date.fromisoformat(previous_state["date"])
            user_ids = previous_state["user_ids"]
            year = previous_state["year"]
            month = previous_state["month"]
            day = previous_state["day"]

            async with async_session_maker() as session:
                if user_ids:
                    await create_or_update_shift(session, shift_date, user_ids)
                else:
                    await delete_shift(session, shift_date)

            # Refresh the selection keyboard (without undo button since we just undid)
            keyboard = await build_day_user_selection_keyboard(year, month, day)
            await callback.message.edit_reply_markup(reply_markup=keyboard)
            await callback.answer("↩️ Дію скасовано")

        elif action_type == "approve_request":
            # Restore request status and shift states
            request_id = previous_state["request_id"]
            previous_status = previous_state["previous_status"]
            previous_states = previous_state.get("previous_states", {})
            action = previous_state.get("action")
            dates = previous_state.get("dates", [])
            user_ids = previous_state.get("user_ids", [])

            async with async_session_maker() as session:
                # Restore request status
                await update_request_status(session, request_id, previous_status)

                # Restore shift states if applicable
                if action in ["assign", "unassign"] and dates and user_ids:
                    from datetime import datetime as dt

                    for date_str in dates:
                        if date_str in previous_states:
                            try:
                                shift_date = dt.strptime(date_str, "%Y-%m-%d").date()
                                prev_user_ids = previous_states[date_str]

                                if prev_user_ids:
                                    await create_or_update_shift(
                                        session, shift_date, prev_user_ids
                                    )
                                else:
                                    await delete_shift(session, shift_date)
                            except Exception as e:
                                print(f"Error restoring shift state: {e}")

            # Update message (restore original buttons)
            text = callback.message.text
            # Remove the approval/rejection line if present
            if "✅ Затверджено адміністратором" in text:
                text = text.replace("\n\n✅ Затверджено адміністратором", "")
            elif "❌ Відхилено адміністратором" in text:
                text = text.replace("\n\n❌ Відхилено адміністратором", "")

            # Restore original approval/rejection buttons
            builder = InlineKeyboardBuilder()
            builder.button(
                text="✅ Затвердити", callback_data=f"approve_request_{request_id}"
            )
            builder.button(
                text="❌ Відхилити", callback_data=f"reject_request_{request_id}"
            )
            builder.adjust(2)

            await callback.message.edit_text(text, reply_markup=builder.as_markup())
            await callback.answer("↩️ Дію скасовано")

        elif action_type == "reject_request":
            # Restore request status
            request_id = previous_state["request_id"]
            previous_status = previous_state["previous_status"]

            async with async_session_maker() as session:
                await update_request_status(session, request_id, previous_status)

            # Update message (restore original buttons)
            text = callback.message.text
            if "❌ Відхилено адміністратором" in text:
                text = text.replace("\n\n❌ Відхилено адміністратором", "")

            # Restore original approval/rejection buttons
            builder = InlineKeyboardBuilder()
            builder.button(
                text="✅ Затвердити", callback_data=f"approve_request_{request_id}"
            )
            builder.button(
                text="❌ Відхилити", callback_data=f"reject_request_{request_id}"
            )
            builder.adjust(2)

            await callback.message.edit_text(text, reply_markup=builder.as_markup())
            await callback.answer("↩️ Дію скасовано")

        elif action_type == "clear_month":
            # Restore all shifts for the month
            year = previous_state["year"]
            month = previous_state["month"]
            previous_states = previous_state.get("previous_states", {})

            month_name = get_month_name_ukrainian(month)

            async with async_session_maker() as session:
                from datetime import datetime as dt

                restored_count = 0

                for date_str, user_ids in previous_states.items():
                    try:
                        shift_date = dt.strptime(date_str, "%Y-%m-%d").date()
                        if user_ids:
                            await create_or_update_shift(session, shift_date, user_ids)
                            restored_count += 1
                    except Exception as e:
                        print(f"Error restoring shift for {date_str}: {e}")

            # Update message
            text = (
                f"↩️ <b>Дію скасовано</b>\n\n"
                f"Всі зміни для <b>{month_name} {year}</b> були відновлені.\n\n"
                f"📊 Відновлено змін: <b>{restored_count}</b>"
            )

            await callback.message.edit_text(text, parse_mode="HTML")
            await callback.answer("↩️ Дію скасовано")

        else:
            await callback.answer("❌ Невідомий тип дії.", show_alert=True)
            return

        # Remove the undo action after successful undo
        undo_service.remove_undo_action(action_id)

    except Exception as e:
        print(f"Error undoing action: {e}")
        await callback.answer("❌ Помилка при скасуванні дії.", show_alert=True)
