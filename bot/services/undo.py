"""Undo service for managing action history and undo operations"""

import uuid
from datetime import datetime, timedelta
from typing import Dict, Optional, Any, List
from dataclasses import dataclass, asdict
from datetime import date


@dataclass
class UndoAction:
    """Represents an action that can be undone"""
    action_id: str
    action_type: str  # "toggle_user", "clear_day", "approve_request", "reject_request"
    previous_state: Dict[str, Any]  # State before the action
    timestamp: datetime
    expires_at: datetime


class UndoService:
    """Service for managing undo operations"""
    
    def __init__(self, ttl_minutes: int = 30):
        """
        Initialize undo service.
        
        Args:
            ttl_minutes: Time-to-live for undo actions in minutes (default: 30)
        """
        self._actions: Dict[str, UndoAction] = {}
        self.ttl_minutes = ttl_minutes
    
    def create_undo_action(
        self,
        action_type: str,
        previous_state: Dict[str, Any],
        ttl_minutes: Optional[int] = None
    ) -> str:
        """
        Create a new undo action.
        
        Args:
            action_type: Type of action (e.g., "toggle_user", "clear_day")
            previous_state: State before the action (e.g., {"date": "2025-01-15", "user_ids": [1, 2]})
            ttl_minutes: Optional custom TTL (uses default if None)
        
        Returns:
            Action ID (string) that can be used for undo
        """
        action_id = str(uuid.uuid4())
        now = datetime.utcnow()
        ttl = ttl_minutes if ttl_minutes is not None else self.ttl_minutes
        
        action = UndoAction(
            action_id=action_id,
            action_type=action_type,
            previous_state=previous_state,
            timestamp=now,
            expires_at=now + timedelta(minutes=ttl)
        )
        
        self._actions[action_id] = action
        return action_id
    
    def get_undo_action(self, action_id: str) -> Optional[UndoAction]:
        """
        Get an undo action by ID.
        
        Args:
            action_id: Action ID
        
        Returns:
            UndoAction if found and not expired, None otherwise
        """
        action = self._actions.get(action_id)
        if not action:
            return None
        
        # Check if expired
        if datetime.utcnow() > action.expires_at:
            del self._actions[action_id]
            return None
        
        return action
    
    def remove_undo_action(self, action_id: str) -> bool:
        """
        Remove an undo action.
        
        Args:
            action_id: Action ID
        
        Returns:
            True if removed, False if not found
        """
        if action_id in self._actions:
            del self._actions[action_id]
            return True
        return False
    
    def cleanup_expired(self):
        """Remove all expired actions"""
        now = datetime.utcnow()
        expired_ids = [
            action_id
            for action_id, action in self._actions.items()
            if now > action.expires_at
        ]
        for action_id in expired_ids:
            del self._actions[action_id]
    
    def get_action_count(self) -> int:
        """Get current number of stored actions"""
        return len(self._actions)


# Global instance
undo_service = UndoService(ttl_minutes=30)

