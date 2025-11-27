"""Database CRUD operations"""

from datetime import date, datetime, timedelta
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from sqlalchemy.orm import selectinload

from .models import User, Shift, Request, async_session_maker


# User operations
async def get_user(session: AsyncSession, user_id: int) -> Optional[User]:
    """Get user by ID"""
    result = await session.execute(select(User).where(User.user_id == user_id))
    return result.scalar_one_or_none()


async def get_next_negative_user_id(session: AsyncSession) -> int:
    """Get the next available negative user_id for users without Telegram IDs"""
    # Get all negative user_ids (placeholders for non-Telegram users)
    result = await session.execute(
        select(User.user_id).where(User.user_id < 0).order_by(User.user_id)
    )
    negative_ids = [row[0] for row in result.all()]

    if not negative_ids:
        # Start from -1 if no negative IDs exist
        return -1

    # Find the next available negative ID (start from -1 and go down)
    next_id = -1
    while next_id in negative_ids:
        next_id -= 1

    return next_id


async def create_user(
    session: AsyncSession,
    user_id: int,
    name: str,
    username: Optional[str] = None,
    color_code: Optional[str] = None,
    is_admin: bool = False,
    is_allowed: bool = False,
    is_hidden: bool = False,
) -> User:
    """Create a new user"""
    user = User(
        user_id=user_id,
        username=username,
        name=name,
        color_code=color_code,
        is_admin=is_admin,
        is_allowed=is_allowed,
        is_hidden=is_hidden,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def update_user(
    session: AsyncSession,
    user_id: int,
    name: Optional[str] = None,
    username: Optional[str] = None,
    color_code: Optional[str] = None,
    is_admin: Optional[bool] = None,
    is_allowed: Optional[bool] = None,
    is_hidden: Optional[bool] = None,
) -> Optional[User]:
    """Update user"""
    user = await get_user(session, user_id)
    if not user:
        return None

    if name is not None:
        user.name = name
    if username is not None:
        user.username = username
    if color_code is not None:
        user.color_code = color_code
    if is_admin is not None:
        user.is_admin = is_admin
    if is_allowed is not None:
        user.is_allowed = is_allowed
    if is_hidden is not None:
        user.is_hidden = is_hidden

    await session.commit()
    await session.refresh(user)
    return user


async def get_all_users(
    session: AsyncSession, include_hidden: bool = False
) -> List[User]:
    """Get all users, optionally including hidden ones"""
    query = select(User).order_by(User.name)
    if not include_hidden:
        query = query.where(User.is_hidden == False)
    result = await session.execute(query)
    return list(result.scalars().all())


async def get_allowed_users(session: AsyncSession) -> List[User]:
    """Get all allowed users"""
    result = await session.execute(select(User).where(User.is_allowed == True))
    return list(result.scalars().all())


async def get_admins(session: AsyncSession) -> List[User]:
    """Get all admin users"""
    result = await session.execute(select(User).where(User.is_admin == True))
    return list(result.scalars().all())


# Shift operations
async def get_shift(session: AsyncSession, shift_date: date) -> Optional[Shift]:
    """Get shift by date"""
    result = await session.execute(select(Shift).where(Shift.date == shift_date))
    return result.scalar_one_or_none()


async def create_or_update_shift(
    session: AsyncSession, shift_date: date, user_ids: List[int]
) -> Shift:
    """Create or update shift"""
    shift = await get_shift(session, shift_date)
    if shift:
        shift.user_ids = user_ids
        shift.updated_at = datetime.utcnow()
    else:
        shift = Shift(date=shift_date, user_ids=user_ids)
        session.add(shift)

    await session.commit()
    await session.refresh(shift)
    return shift


async def get_shifts_in_range(
    session: AsyncSession, start_date: date, end_date: date
) -> List[Shift]:
    """Get shifts in date range"""
    result = await session.execute(
        select(Shift).where(Shift.date >= start_date, Shift.date <= end_date)
    )
    return list(result.scalars().all())


async def delete_shift(session: AsyncSession, shift_date: date) -> bool:
    """Delete shift"""
    shift = await get_shift(session, shift_date)
    if shift:
        await session.delete(shift)
        await session.commit()
        return True
    return False


async def cleanup_old_shifts(session: AsyncSession, max_age_years: int = 1) -> int:
    """
    Delete shifts older than specified years.

    Args:
        session: Database session
        max_age_years: Maximum age in years (default: 1)

    Returns:
        Number of shifts deleted
    """
    cutoff_date = date.today() - timedelta(days=max_age_years * 365)

    # Find all shifts older than cutoff date
    result = await session.execute(select(Shift).where(Shift.date < cutoff_date))
    old_shifts = result.scalars().all()

    if old_shifts:
        count = len(old_shifts)
        for shift in old_shifts:
            await session.delete(shift)
        await session.commit()
        return count

    return 0


# Request operations
async def create_request(
    session: AsyncSession,
    user_id: int,
    message: str,
    parsed_intent: Optional[dict] = None,
) -> Request:
    """Create a new request"""
    request = Request(
        user_id=user_id, message=message, parsed_intent=parsed_intent, status="pending"
    )
    session.add(request)
    await session.commit()
    await session.refresh(request)
    return request


async def get_request(session: AsyncSession, request_id: int) -> Optional[Request]:
    """Get request by ID"""
    result = await session.execute(select(Request).where(Request.id == request_id))
    return result.scalar_one_or_none()


async def update_request_status(
    session: AsyncSession, request_id: int, status: str
) -> Optional[Request]:
    """Update request status"""
    request = await get_request(session, request_id)
    if request:
        request.status = status
        await session.commit()
        await session.refresh(request)
    return request


async def get_pending_requests(session: AsyncSession) -> List[Request]:
    """Get all pending requests"""
    result = await session.execute(
        select(Request)
        .where(Request.status == "pending")
        .order_by(Request.created_at.desc())
    )
    return list(result.scalars().all())
