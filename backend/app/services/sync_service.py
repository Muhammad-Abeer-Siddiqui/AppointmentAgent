"""Two-way sync service between app and Google Calendar (async)."""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from sqlalchemy.orm import Session

from app.database.models import User, Appointment, ExternalIntegration
from app.services.google_calendar import (
    GoogleCalendarService,
    async_create_event,
    async_update_event,
    async_delete_event,
    async_get_events,
)


class SyncService:
    """Service for two-way sync between app and Google Calendar."""

    def __init__(self, user: User, db: Session):
        """Initialize sync service."""
        self.user = user
        self.db = db
        self.google_service = GoogleCalendarService(user, db)

    def is_connected(self) -> bool:
        """Check if Google Calendar is connected."""
        return self.google_service.is_connected()

    async def sync_app_to_google(self) -> Dict[str, Any]:
        """Sync local appointments to Google Calendar.

        Pushes all non-synced appointments to Google Calendar.
        """
        if not self.is_connected():
            return {"success": False, "error": "Google Calendar not connected"}

        # Get appointments that haven't been synced
        unsynced = self.db.query(Appointment).filter(
            Appointment.user_id == self.user.id,
            Appointment.status != "cancelled",
            Appointment.google_calendar_event_id == None,
        ).all()

        synced_count = 0
        errors = []

        for appointment in unsynced:
            try:
                # Create event in Google Calendar
                event_data = {
                    "title": appointment.title,
                    "description": appointment.description or "",
                    "start_time": appointment.start_time.isoformat(),
                    "end_time": appointment.end_time.isoformat(),
                    "timezone": self.user.timezone or "UTC",
                }

                google_event_id = await async_create_event(self.google_service, event_data)

                if google_event_id:
                    # Update local appointment with Google event ID
                    appointment.google_calendar_event_id = google_event_id
                    appointment.last_synced_at = datetime.utcnow()
                    synced_count += 1
                else:
                    errors.append(f"Failed to sync appointment {appointment.id}")

            except Exception as e:
                errors.append(f"Error syncing appointment {appointment.id}: {str(e)}")

        # Update last sync time
        self._update_last_sync_time()

        self.db.commit()

        return {
            "success": True,
            "synced_count": synced_count,
            "errors": errors,
        }

    async def sync_google_to_app(self) -> Dict[str, Any]:
        """Sync Google Calendar events to local database.

        Pulls events from Google Calendar and creates/updates local appointments.
        """
        if not self.is_connected():
            return {"success": False, "error": "Google Calendar not connected"}

        # Get events from Google Calendar (last 30 days to 60 days ahead)
        start_time = datetime.utcnow() - timedelta(days=30)
        end_time = datetime.utcnow() + timedelta(days=60)

        google_events = await async_get_events(self.google_service, start_time, end_time)

        # Get existing synced appointments
        existing_appointments = {
            apt.google_calendar_event_id: apt
            for apt in self.db.query(Appointment).filter(
                Appointment.user_id == self.user.id,
                Appointment.google_calendar_event_id != None,
            ).all()
        }

        synced_count = 0
        created_count = 0
        updated_count = 0

        for event in google_events:
            google_event_id = event.get("google_event_id")

            if not google_event_id:
                continue

            # Check if appointment already exists locally
            existing = existing_appointments.get(google_event_id)

            if existing:
                # Check if Google event is newer
                google_updated = event.get("updated")
                if google_updated and google_updated > existing.updated_at.isoformat():
                    # Update local appointment
                    existing.title = event.get("title", existing.title)
                    existing.description = event.get("description", existing.description)
                    existing.start_time = datetime.fromisoformat(event["start_time"])
                    existing.end_time = datetime.fromisoformat(event["end_time"])
                    existing.last_synced_at = datetime.utcnow()
                    updated_count += 1
            else:
                # Create new local appointment from Google event
                try:
                    start_time = datetime.fromisoformat(event["start_time"])
                    end_time = datetime.fromisoformat(event["end_time"])
                    duration = int((end_time - start_time).total_seconds() / 60)

                    appointment = Appointment(
                        user_id=self.user.id,
                        title=event.get("title", "Google Event"),
                        description=event.get("description", ""),
                        start_time=start_time,
                        end_time=end_time,
                        duration_minutes=duration,
                        status="scheduled",
                        google_calendar_event_id=google_event_id,
                        last_synced_at=datetime.utcnow(),
                    )

                    self.db.add(appointment)
                    created_count += 1
                except Exception as e:
                    print(f"Failed to create appointment from Google event: {e}")

        # Update last sync time
        self._update_last_sync_time()

        self.db.commit()

        return {
            "success": True,
            "created_count": created_count,
            "updated_count": updated_count,
            "total_google_events": len(google_events),
        }

    async def sync_two_way(self) -> Dict[str, Any]:
        """Perform two-way sync between app and Google Calendar.

        First pushes local changes to Google, then pulls Google changes to local.
        """
        # First sync app -> Google
        app_to_google_result = await self.sync_app_to_google()

        # Then sync Google -> app
        google_to_app_result = await self.sync_google_to_app()

        return {
            "success": True,
            "app_to_google": app_to_google_result,
            "google_to_app": google_to_app_result,
        }

    def _update_last_sync_time(self):
        """Update the last sync timestamp in ExternalIntegration."""
        integration = self.db.query(ExternalIntegration).filter(
            ExternalIntegration.user_id == self.user.id,
            ExternalIntegration.provider == "google_calendar",
            ExternalIntegration.is_active == True,
        ).first()

        if integration:
            config = integration.config
            config["last_sync"] = datetime.utcnow().isoformat() + "Z"
            integration.config = config

    def get_last_sync_time(self) -> Optional[str]:
        """Get the last sync timestamp."""
        integration = self.db.query(ExternalIntegration).filter(
            ExternalIntegration.user_id == self.user.id,
            ExternalIntegration.provider == "google_calendar",
            ExternalIntegration.is_active == True,
        ).first()

        if integration:
            return integration.config.get("last_sync")
        return None


# Convenience functions for AI tools (now async)
async def sync_user_to_google(user_id: int, db: Session) -> Dict[str, Any]:
    """Sync user's appointments to Google Calendar."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {"success": False, "error": "User not found"}

    sync_service = SyncService(user, db)
    return await sync_service.sync_app_to_google()


async def sync_user_from_google(user_id: int, db: Session) -> Dict[str, Any]:
    """Sync Google Calendar events to user's local database."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {"success": False, "error": "User not found"}

    sync_service = SyncService(user, db)
    return await sync_service.sync_google_to_app()


async def sync_user_two_way(user_id: int, db: Session) -> Dict[str, Any]:
    """Perform two-way sync for user."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {"success": False, "error": "User not found"}

    sync_service = SyncService(user, db)
    return await sync_service.sync_two_way()


def is_google_connected(user_id: int, db: Session) -> bool:
    """Check if user has connected Google Calendar."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return False

    sync_service = SyncService(user, db)
    return sync_service.is_connected()
