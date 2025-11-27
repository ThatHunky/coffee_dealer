"""SQLAlchemy database models"""

from datetime import datetime, date
from typing import Optional, List
from sqlalchemy import BigInteger, Boolean, String, Date, Text, TIMESTAMP, JSON
from sqlalchemy.ext.asyncio import AsyncAttrs, create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
import os
from dotenv import load_dotenv

load_dotenv()


class Base(AsyncAttrs, DeclarativeBase):
    """Base class for all models"""
    pass


class User(Base):
    """User model"""
    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    color_code: Mapped[Optional[str]] = mapped_column(String(7), nullable=True)  # Hex color
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_allowed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, default=datetime.utcnow, nullable=False)


class Shift(Base):
    """Shift model"""
    __tablename__ = "shifts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, unique=True, nullable=False)
    user_ids: Mapped[List[int]] = mapped_column(JSON, default=[], nullable=False)  # SQLite doesn't support ARRAY, use JSON
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class Request(Base):
    """Request model for user shift change requests"""
    __tablename__ = "requests"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    parsed_intent: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)  # pending/approved/rejected
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, default=datetime.utcnow, nullable=False)


# Database engine and session
# Default to SQLite database file
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///shiftbot.db")

engine = create_async_engine(
    DATABASE_URL,
    echo=False
)

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)


async def init_db():
    """Initialize database tables"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)



