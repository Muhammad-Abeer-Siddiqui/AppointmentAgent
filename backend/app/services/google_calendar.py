"""Google Calendar service for two-way sync (async)."""

import asyncio
from datetime import datetime
from typing import Optional, List, Dict, Any
from functools import partial

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request as GoogleRequest
from sqlalchemy.orm import Session

from app.database.models import User, ExternalIntegration


class GoogleCalendarService:
    """Service for interacting with Google Calendar API."""

    def __init__(self, user: User, db: Session):
        """Initialize service with user and database session."""
        self.user = user
        self.db = db
        self.credentials = self._get_credentials()
        self.service = None

        if self.credentials:
            self.service = build("calendar", "v3", credentials=self.credentials)

    def _get_credentials(self) -> Optional[Credentials]:
        """Get valid Google OAuth2 credentials for the user."""
        integration = self.db.query(ExternalIntegration).filter(
            ExternalIntegration.user_id == self.user.id,
            ExternalIntegration.provider == "google_calendar",
            ExternalIntegration.is_active == True,
        ).first()

        if not integration:
            return None

        config = integration.config

        # Check if token is expired
        from datetime import timedelta
        token_expiry = datetime.fromisoformat(
            config.get("token_expiry", "2000-01-01T00:00:00Z").replace("Z", "+00:00")
        )

        # If token is expired, refresh it
        if token_expiry <= datetime.now(token_expiry.tzinfo):
            try:
                from app.auth.google import refresh_access_token
                new_tokens = refresh_access_token(config["refresh_token"])
                config["access_token"] = new_tokens["access_token"]
                if "expires_in" in new_tokens:
                    config["token_expiry"] = (
                        datetime.utcnow() + timedelta(seconds=new_tokens["expires_in"])
                    ).isoformat() + "Z"
                integration.config = config
                self.db.commit()
            except Exception as e:
                print(f"Failed to refresh Google token: {e}")
                return None

        credentials = Credentials(
            token=config.get("access_token"),
            refresh_token=config.get("refresh_token"),
            token_uri="https://oauth2.googleapis.com/token",
        )

        return credentials

    def is_connected(self) -> bool:
        """Check if user has connected Google Calendar."""
        return self.service is not None

    def list_calendars(self) -> List[Dict[str, Any]]:
        """List user's Google Calendars."""
        if not self.service:
            return []

        try:
            calendar_list = self.service.calendarList().list().execute()
            return calendar_list.get("items", [])
        except Exception as e:
            print(f"Failed to list calendars: {e}")
            return []

    def get_events(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Get events from Google Calendar."""
        if not self.service:
            return []

        # Get calendar ID from integration
        integration = self.db.query(ExternalIntegration).filter(
            ExternalIntegration.user_id == self.user.id,
            ExternalIntegration.provider == "google_calendar",
            ExternalIntegration.is_active == True,
        ).first()

        calendar_id = integration.config.get("calendar_id", "primary") if integration else "primary"

        try:
            # Build time parameters
            params = {"calendarId": calendar_id, "singleEvents": True, "orderBy": "startTime"}

            if start_time:
                params["timeMin"] = start_time.isoformat() + "Z" if start_time.tzinfo is None else start_time.isoformat()
            if end_time:
                params["timeMax"] = end_time.isoformat() + "Z" if end_time.tzinfo is None else end_time.isoformat()

            events_result = self.service.events().list(**params).execute()
            events = events_result.get("items", [])

            return [self._event_to_dict(event) for event in events]
        except Exception as e:
            print(f"Failed to get events: {e}")
            return []

    def create_event(self, event_data: Dict[str, Any]) -> Optional[str]:
        """Create an event in Google Calendar.

        Args:
            event_data: Dict with keys: title, description, start_time, end_time

        Returns:
            Google Calendar event ID if successful, None otherwise
        """
        if not self.service:
            return None

        # Get calendar ID
        integration = self.db.query(ExternalIntegration).filter(
            ExternalIntegration.user_id == self.user.id,
            ExternalIntegration.provider == "google_calendar",
            ExternalIntegration.is_active == True,
        ).first()

        calendar_id = integration.config.get("calendar_id", "primary") if integration else "primary"

        # Build event body
        event_body = {
            "summary": event_data.get("title", "Untitled"),
            "description": event_data.get("description", ""),
            "start": {
                "dateTime": event_data["start_time"],
                "timeZone": event_data.get("timezone", "UTC"),
            },
            "end": {
                "dateTime": event_data["end_time"],
                "timeZone": event_data.get("timezone", "UTC"),
            },
        }

        # Add attendees if provided
        if "attendees" in event_data and event_data["attendees"]:
            event_body["attendees"] = [
                {"email": email} for email in event_data["attendees"]
            ]

        try:
            event = self.service.events().insert(
                calendarId=calendar_id,
                body=event_body,
            ).execute()

            return event.get("id")
        except Exception as e:
            print(f"Failed to create event: {e}")
            return None

    def update_event(
        self,
        google_event_id: str,
        event_data: Dict[str, Any],
    ) -> bool:
        """Update an event in Google Calendar.

        Args:
            google_event_id: Google Calendar event ID
            event_data: Dict with keys: title, description, start_time, end_time

        Returns:
            True if successful, False otherwise
        """
        if not self.service:
            return False

        # Get calendar ID
        integration = self.db.query(ExternalIntegration).filter(
            ExternalIntegration.user_id == self.user.id,
            ExternalIntegration.provider == "google_calendar",
            ExternalIntegration.is_active == True,
        ).first()

        calendar_id = integration.config.get("calendar_id", "primary") if integration else "primary"

        # Build event body
        event_body = {}
        if "title" in event_data:
            event_body["summary"] = event_data["title"]
        if "description" in event_data:
            event_body["description"] = event_data["description"]
        if "start_time" in event_data:
            event_body["start"] = {
                "dateTime": event_data["start_time"],
                "timeZone": event_data.get("timezone", "UTC"),
            }
        if "end_time" in event_data:
            event_body["end"] = {
                "dateTime": event_data["end_time"],
                "timeZone": event_data.get("timezone", "UTC"),
            }

        try:
            self.service.events().update(
                calendarId=calendar_id,
                eventId=google_event_id,
                body=event_body,
            ).execute()

            return True
        except Exception as e:
            print(f"Failed to update event: {e}")
            return False

    def delete_event(self, google_event_id: str) -> bool:
        """Delete an event from Google Calendar.

        Args:
            google_event_id: Google Calendar event ID

        Returns:
            True if successful, False otherwise
        """
        if not self.service:
            return False

        # Get calendar ID
        integration = self.db.query(ExternalIntegration).filter(
            ExternalIntegration.user_id == self.user.id,
            ExternalIntegration.provider == "google_calendar",
            ExternalIntegration.is_active == True,
        ).first()

        calendar_id = integration.config.get("calendar_id", "primary") if integration else "primary"

        try:
            self.service.events().delete(
                calendarId=calendar_id,
                eventId=google_event_id,
            ).execute()

            return True
        except Exception as e:
            print(f"Failed to delete event: {e}")
            return False

    def _event_to_dict(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Convert a Google Calendar event to a dictionary."""
        start = event.get("start", {})
        end = event.get("end", {})

        return {
            "id": event.get("id"),
            "google_event_id": event.get("id"),
            "title": event.get("summary", "Untitled"),
            "description": event.get("description", ""),
            "start_time": start.get("dateTime", start.get("date")),
            "end_time": end.get("dateTime", end.get("date")),
            "location": event.get("location", ""),
            "attendees": [
                attendee.get("email")
                for attendee in event.get("attendees", [])
            ],
            "status": event.get("status", "confirmed"),
            "html_link": event.get("htmlLink"),
        }


# Async wrapper functions
async def async_list_calendars(service: "GoogleCalendarService") -> List[Dict[str, Any]]:
    """Async wrapper for list_calendars."""
    return await asyncio.to_thread(service.list_calendars)


async def async_get_events(
    service: "GoogleCalendarService",
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    """Async wrapper for get_events."""
    return await asyncio.to_thread(service.get_events, start_time, end_time)


async def async_create_event(
    service: "GoogleCalendarService",
    event_data: Dict[str, Any],
) -> Optional[str]:
    """Async wrapper for create_event."""
    return await asyncio.to_thread(service.create_event, event_data)


async def async_update_event(
    service: "GoogleCalendarService",
    google_event_id: str,
    event_data: Dict[str, Any],
) -> bool:
    """Async wrapper for update_event."""
    return await asyncio.to_thread(service.update_event, google_event_id, event_data)


async def async_delete_event(
    service: "GoogleCalendarService",
    google_event_id: str,
) -> bool:
    """Async wrapper for delete_event."""
    return await asyncio.to_thread(service.delete_event, google_event_id)
