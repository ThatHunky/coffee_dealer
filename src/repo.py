"""Repository for schedule assignments."""

from datetime import date, datetime, timedelta
from typing import Optional

from sqlmodel import Session, SQLModel, create_engine, select

from .config import config
from .models import (
    Assignment,
    ChangeNotification,
    ChangeRequest,
    CombinationColor,
    UserApproval,
    UserConfig,
)

# Create engine
engine = create_engine(config.DATABASE_URL, echo=False)


def init_db() -> None:
    """Initialize database tables."""
    SQLModel.metadata.create_all(engine)

    # Initialize default users and combinations if they don't exist
    with Session(engine) as session:
        # Check if users exist
        existing_users = session.exec(select(UserConfig)).first()
        if not existing_users:
            default_users = UserConfig.create_default_users()
            for user in default_users:
                session.add(user)
            session.commit()
            print("✅ Initialized default users")

        # Check if combinations exist
        existing_combos = session.exec(select(CombinationColor)).first()
        if not existing_combos:
            default_combos = CombinationColor.create_default_combinations()
            for combo in default_combos:
                session.add(combo)
            session.commit()
            print("✅ Initialized default color combinations")


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

            old_mask = existing.mask if existing else 0

            if existing:
                existing.mask = assignment.mask
                existing.note = assignment.note
                session.add(existing)
                session.commit()
                session.refresh(existing)
                result = existing
            else:
                session.add(assignment)
                session.commit()
                session.refresh(assignment)
                result = assignment

            return result

    def upsert_with_notification(
        self, assignment: Assignment, changed_by: int
    ) -> tuple[Assignment, ChangeNotification]:
        """Insert or update an assignment and create a change notification."""
        with self._get_session() as session:
            existing = session.exec(
                select(Assignment).where(Assignment.day == assignment.day)
            ).first()

            old_mask = existing.mask if existing else 0

            if existing:
                existing.mask = assignment.mask
                existing.note = assignment.note
                session.add(existing)
                session.commit()
                session.refresh(existing)
                result = existing
            else:
                session.add(assignment)
                session.commit()
                session.refresh(assignment)
                result = assignment

            # Create notification record
            notification = ChangeNotification(
                change_date=assignment.day,
                old_mask=old_mask,
                new_mask=assignment.mask,
                changed_by=changed_by,
            )
            session.add(notification)
            session.commit()
            session.refresh(notification)

            return result, notification

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

    # User configuration methods

    def get_all_users(self, active_only: bool = True) -> list[UserConfig]:
        """Get all user configurations."""
        with self._get_session() as session:
            stmt = select(UserConfig).order_by(UserConfig.bit_position)
            if active_only:
                stmt = stmt.where(UserConfig.is_active == True)
            return list(session.exec(stmt).all())

    def get_user_by_name(self, name: str) -> Optional[UserConfig]:
        """Get user configuration by name (case-insensitive)."""
        name_lower = name.lower()
        with self._get_session() as session:
            stmt = select(UserConfig).where(
                (UserConfig.name_en == name_lower) | (UserConfig.name_uk == name)
            )
            return session.exec(stmt).first()

    def get_user_by_bit(self, bit_position: int) -> Optional[UserConfig]:
        """Get user configuration by bit position."""
        with self._get_session() as session:
            stmt = select(UserConfig).where(UserConfig.bit_position == bit_position)
            return session.exec(stmt).first()

    def upsert_user(self, user: UserConfig) -> UserConfig:
        """Insert or update a user configuration."""
        with self._get_session() as session:
            user.updated_at = datetime.utcnow()
            existing = session.exec(
                select(UserConfig).where(UserConfig.bit_position == user.bit_position)
            ).first()

            if existing:
                existing.name_uk = user.name_uk
                existing.name_en = user.name_en
                existing.emoji = user.emoji
                existing.is_active = user.is_active
                existing.updated_at = user.updated_at
                session.add(existing)
                session.commit()
                session.refresh(existing)
                return existing
            else:
                session.add(user)
                session.commit()
                session.refresh(user)
                return user

    # Combination color methods

    def get_all_combinations(self) -> list[CombinationColor]:
        """Get all combination colors."""
        with self._get_session() as session:
            stmt = select(CombinationColor).order_by(CombinationColor.mask)
            return list(session.exec(stmt).all())

    def get_combination_color(self, mask: int) -> Optional[CombinationColor]:
        """Get combination color by mask."""
        with self._get_session() as session:
            stmt = select(CombinationColor).where(CombinationColor.mask == mask)
            return session.exec(stmt).first()

    def upsert_combination(self, combo: CombinationColor) -> CombinationColor:
        """Insert or update a combination color."""
        with self._get_session() as session:
            existing = session.exec(
                select(CombinationColor).where(CombinationColor.mask == combo.mask)
            ).first()

            if existing:
                existing.emoji = combo.emoji
                existing.label_uk = combo.label_uk
                session.add(existing)
                session.commit()
                session.refresh(existing)
                return existing
            else:
                session.add(combo)
                session.commit()
                session.refresh(combo)
                return combo

    # Notification methods

    def get_pending_notifications(self, limit: int = 10) -> list[ChangeNotification]:
        """Get pending (unsent) notifications."""
        with self._get_session() as session:
            stmt = (
                select(ChangeNotification)
                .where(ChangeNotification.notified == False)
                .order_by(ChangeNotification.changed_at.desc())
                .limit(limit)
            )
            return list(session.exec(stmt).all())

    def mark_notification_sent(self, notification_id: int) -> bool:
        """Mark a notification as sent."""
        with self._get_session() as session:
            notification = session.get(ChangeNotification, notification_id)
            if notification:
                notification.notified = True
                session.add(notification)
                session.commit()
                return True
            return False

    def get_recent_changes(
        self, days: int = 7, limit: int = 20
    ) -> list[ChangeNotification]:
        """Get recent change notifications."""
        since = datetime.utcnow() - timedelta(days=days)
        with self._get_session() as session:
            stmt = (
                select(ChangeNotification)
                .where(ChangeNotification.changed_at >= since)
                .order_by(ChangeNotification.changed_at.desc())
                .limit(limit)
            )
            return list(session.exec(stmt).all())

    # Change Request methods

    def create_change_request(self, request: ChangeRequest) -> ChangeRequest:
        """Create a new change request from a non-admin user."""
        with self._get_session() as session:
            session.add(request)
            session.commit()
            session.refresh(request)
            return request

    def get_pending_requests(self, limit: int = 50) -> list[ChangeRequest]:
        """Get all pending change requests."""
        with self._get_session() as session:
            stmt = (
                select(ChangeRequest)
                .where(ChangeRequest.status == "pending")
                .order_by(ChangeRequest.requested_at.desc())
                .limit(limit)
            )
            return list(session.exec(stmt).all())

    def get_change_request(self, request_id: int) -> Optional[ChangeRequest]:
        """Get a specific change request by ID."""
        with self._get_session() as session:
            return session.get(ChangeRequest, request_id)

    def approve_request(
        self, request_id: int, admin_id: int, note: str = ""
    ) -> Optional[ChangeRequest]:
        """Approve a change request and apply the changes."""
        with self._get_session() as session:
            request = session.get(ChangeRequest, request_id)
            if not request or request.status != "pending":
                return None

            request.status = "approved"
            request.reviewed_by = admin_id
            request.reviewed_at = datetime.utcnow()
            request.review_note = note
            session.add(request)
            session.commit()
            session.refresh(request)
            return request

    def deny_request(
        self, request_id: int, admin_id: int, note: str = ""
    ) -> Optional[ChangeRequest]:
        """Deny a change request."""
        with self._get_session() as session:
            request = session.get(ChangeRequest, request_id)
            if not request or request.status != "pending":
                return None

            request.status = "denied"
            request.reviewed_by = admin_id
            request.reviewed_at = datetime.utcnow()
            request.review_note = note
            session.add(request)
            session.commit()
            session.refresh(request)
            return request

    # User Approval methods

    def create_user_approval(self, approval: UserApproval) -> UserApproval:
        """Create a new user approval request."""
        with self._get_session() as session:
            # Check if user already exists
            existing = session.exec(
                select(UserApproval).where(
                    UserApproval.telegram_id == approval.telegram_id
                )
            ).first()

            if existing:
                return existing

            session.add(approval)
            session.commit()
            session.refresh(approval)
            return approval

    def get_user_approval(self, telegram_id: int) -> Optional[UserApproval]:
        """Get user approval by telegram ID."""
        with self._get_session() as session:
            stmt = select(UserApproval).where(UserApproval.telegram_id == telegram_id)
            return session.exec(stmt).first()

    def get_pending_approvals(self, limit: int = 50) -> list[UserApproval]:
        """Get all pending user approval requests."""
        with self._get_session() as session:
            stmt = (
                select(UserApproval)
                .where(UserApproval.status == "pending")
                .order_by(UserApproval.requested_at)
                .limit(limit)
            )
            return list(session.exec(stmt).all())

    def approve_user(
        self, telegram_id: int, admin_id: int, note: str = ""
    ) -> Optional[UserApproval]:
        """Approve a user."""
        with self._get_session() as session:
            approval = session.exec(
                select(UserApproval).where(UserApproval.telegram_id == telegram_id)
            ).first()

            if not approval or approval.status != "pending":
                return None

            approval.status = "approved"
            approval.reviewed_by = admin_id
            approval.reviewed_at = datetime.utcnow()
            approval.review_note = note
            session.add(approval)
            session.commit()
            session.refresh(approval)
            return approval

    def deny_user(
        self, telegram_id: int, admin_id: int, note: str = ""
    ) -> Optional[UserApproval]:
        """Deny a user."""
        with self._get_session() as session:
            approval = session.exec(
                select(UserApproval).where(UserApproval.telegram_id == telegram_id)
            ).first()

            if not approval or approval.status != "pending":
                return None

            approval.status = "denied"
            approval.reviewed_by = admin_id
            approval.reviewed_at = datetime.utcnow()
            approval.review_note = note
            session.add(approval)
            session.commit()
            session.refresh(approval)
            return approval

    def is_user_approved(self, telegram_id: int) -> bool:
        """Check if user is approved to use the bot."""
        # Admins are always approved
        if telegram_id in config.ADMIN_IDS:
            return True

        with self._get_session() as session:
            approval = session.exec(
                select(UserApproval).where(UserApproval.telegram_id == telegram_id)
            ).first()

            return approval is not None and approval.status == "approved"


# Global repository instance
repo = AssignmentRepository()
