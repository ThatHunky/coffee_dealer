"""Repository for schedule assignments."""

from datetime import date, timedelta
from typing import Optional

from sqlmodel import Session, SQLModel, create_engine, select

from .config import config
from .models import Assignment

# Create engine
engine = create_engine(config.DATABASE_URL, echo=False)


def init_db() -> None:
    """Initialize database tables."""
    SQLModel.metadata.create_all(engine)


class AssignmentRepository:
    """Repository for managing schedule assignments."""

    def __init__(self, session: Optional[Session] = None):
        """Initialize repository with optional session."""
        self._session = session

    def _get_session(self) -> Session:
        """Get or create session."""
        if self._session:
            return self._session
        return Session(engine)

    def get_by_day(self, day: date) -> Optional[Assignment]:
        """Get assignment for a specific day."""
        with self._get_session() as session:
            stmt = select(Assignment).where(Assignment.day == day)
            return session.exec(stmt).first()

    def get_month(self, year: int, month: int) -> list[Assignment]:
        """Get all assignments for a specific month."""
        start = date(year, month, 1)
        if month == 12:
            end = date(year + 1, 1, 1)
        else:
            end = date(year, month + 1, 1)

        with self._get_session() as session:
            stmt = (
                select(Assignment)
                .where(Assignment.day >= start)
                .where(Assignment.day < end)
                .order_by(Assignment.day)
            )
            return list(session.exec(stmt).all())

    def upsert(self, assignment: Assignment) -> Assignment:
        """Insert or update an assignment."""
        with self._get_session() as session:
            existing = session.exec(
                select(Assignment).where(Assignment.day == assignment.day)
            ).first()

            if existing:
                existing.mask = assignment.mask
                existing.note = assignment.note
                session.add(existing)
                session.commit()
                session.refresh(existing)
                return existing
            else:
                session.add(assignment)
                session.commit()
                session.refresh(assignment)
                return assignment

    def delete(self, day: date) -> bool:
        """Delete assignment for a specific day."""
        with self._get_session() as session:
            assignment = session.exec(
                select(Assignment).where(Assignment.day == day)
            ).first()

            if assignment:
                session.delete(assignment)
                session.commit()
                return True
            return False

    def get_range(self, start: date, end: date) -> list[Assignment]:
        """Get assignments within a date range (inclusive)."""
        end_inclusive = end + timedelta(days=1)

        with self._get_session() as session:
            stmt = (
                select(Assignment)
                .where(Assignment.day >= start)
                .where(Assignment.day < end_inclusive)
                .order_by(Assignment.day)
            )
            return list(session.exec(stmt).all())


# Global repository instance
repo = AssignmentRepository()
