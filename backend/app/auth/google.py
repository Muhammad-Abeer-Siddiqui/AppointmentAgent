"""Google OAuth2 integration for Google Calendar sync."""

import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleRequest
from googleapiclient.discovery import build

from app.core.config import settings
from app.database import get_db_session
from app.auth import get_current_user
from app.database.models import User, ExternalIntegration

router = APIRouter(prefix="/auth/google", tags=["Google Calendar"])

# Google OAuth2 configuration
GOOGLE_AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
GOOGLE_CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar"


def get_google_oauth_url(state: str) -> str:
    """Generate Google OAuth2 authorization URL."""
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": GOOGLE_CALENDAR_SCOPE,
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }

    query_string = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{GOOGLE_AUTH_ENDPOINT}?{query_string}"


def exchange_code_for_tokens(code: str) -> dict:
    """Exchange authorization code for access and refresh tokens."""
    import requests

    data = {
        "code": code,
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "grant_type": "authorization_code",
    }

    response = requests.post(GOOGLE_TOKEN_ENDPOINT, data=data)
    response.raise_for_status()
    return response.json()


def refresh_access_token(refresh_token: str) -> dict:
    """Refresh an expired access token."""
    import requests

    data = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }

    response = requests.post(GOOGLE_TOKEN_ENDPOINT, data=data)
    response.raise_for_status()
    return response.json()


def get_valid_credentials(user: User, db: Session) -> Optional[Credentials]:
    """Get valid Google credentials for a user, refreshing if needed."""
    integration = db.query(ExternalIntegration).filter(
        ExternalIntegration.user_id == user.id,
        ExternalIntegration.provider == "google_calendar",
        ExternalIntegration.is_active == True,
    ).first()

    if not integration:
        return None

    config = integration.config
    token_expiry = datetime.fromisoformat(config.get("token_expiry", "2000-01-01T00:00:00Z"))

    if token_expiry <= datetime.utcnow():
        try:
            new_tokens = refresh_access_token(config["refresh_token"])
            config["access_token"] = new_tokens["access_token"]
            if "expires_in" in new_tokens:
                config["token_expiry"] = (
                    datetime.utcnow() + timedelta(seconds=new_tokens["expires_in"])
                ).isoformat() + "Z"
            integration.config = config
            db.commit()
        except Exception as e:
            print(f"Failed to refresh Google token: {e}")
            return None

    credentials = Credentials(
        token=config.get("access_token"),
        refresh_token=config.get("refresh_token"),
        token_uri=GOOGLE_TOKEN_ENDPOINT,
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
    )

    return credentials


@router.get("/login")
async def google_login(
    current_user: User = Depends(get_current_user),
):
    """Initiate Google OAuth2 flow."""
    state = secrets.token_urlsafe(32)
    state_with_user = f"{state}:{current_user.id}"
    auth_url = get_google_oauth_url(state_with_user)
    return {"auth_url": auth_url, "state": state_with_user}


@router.get("/callback")
async def google_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db_session),
):
    """Handle Google OAuth2 callback."""
    parts = state.split(":")
    if len(parts) != 2:
        raise HTTPException(status_code=400, detail="Invalid state parameter")

    state_token, user_id_str = parts

    try:
        user_id = int(user_id_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID in state")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        token_data = exchange_code_for_tokens(code)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to exchange code: {str(e)}")

    credentials = Credentials(
        token=token_data["access_token"],
        refresh_token=token_data.get("refresh_token"),
    )

    try:
        service = build("calendar", "v3", credentials=credentials)
        calendar_list = service.calendarList().list().execute()
        primary_calendar = None
        for cal in calendar_list.get("items", []):
            if cal.get("primary"):
                primary_calendar = cal["id"]
                break
    except Exception as e:
        print(f"Failed to fetch calendar list: {e}")
        primary_calendar = "primary"

    integration = db.query(ExternalIntegration).filter(
        ExternalIntegration.user_id == user.id,
        ExternalIntegration.provider == "google_calendar",
    ).first()

    config = {
        "access_token": token_data["access_token"],
        "refresh_token": token_data.get("refresh_token", ""),
        "token_expiry": (
            datetime.utcnow() + timedelta(seconds=token_data.get("expires_in", 3600))
        ).isoformat() + "Z",
        "calendar_id": primary_calendar,
        "last_sync": None,
    }

    if integration:
        integration.config = config
        integration.is_active = True
    else:
        integration = ExternalIntegration(
            user_id=user.id,
            provider="google_calendar",
            config=config,
            is_active=True,
        )
        db.add(integration)

    db.commit()

    return RedirectResponse(
        url=f"{settings.FRONTEND_URL}/dashboard/settings?google=connected",
        status_code=302,
    )


@router.get("/status")
async def google_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Get Google Calendar connection status."""
    integration = db.query(ExternalIntegration).filter(
        ExternalIntegration.user_id == current_user.id,
        ExternalIntegration.provider == "google_calendar",
        ExternalIntegration.is_active == True,
    ).first()

    if not integration:
        return {"connected": False}

    config = integration.config
    return {
        "connected": True,
        "calendar_id": config.get("calendar_id"),
        "last_sync": config.get("last_sync"),
    }


@router.delete("/disconnect")
async def google_disconnect(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Disconnect Google Calendar integration."""
    integration = db.query(ExternalIntegration).filter(
        ExternalIntegration.user_id == current_user.id,
        ExternalIntegration.provider == "google_calendar",
    ).first()

    if integration:
        db.delete(integration)
        db.commit()

    return {"message": "Google Calendar disconnected"}
