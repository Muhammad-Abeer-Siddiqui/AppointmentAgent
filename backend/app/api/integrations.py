"""Integration routes for Google Calendar and other external services."""

from fastapi import APIRouter, Depends, HTTPException, Body, Request
from sqlalchemy.orm import Session

from app.database import get_db_session
from app.auth import get_current_user
from app.database.models import User
from app.services.sync_service import SyncService
from app.schemas.profile import SyncDirectionRequest


router = APIRouter(prefix="/integrations", tags=["Integrations"])


@router.post("/sync", status_code=200)
async def sync_integration(
    body: SyncDirectionRequest,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """Trigger two-way sync with Google Calendar.

    Args:
        direction: One of "app_to_google", "google_to_app", "two_way"
    """
    direction = body.direction
    sync_service = SyncService(current_user, db)

    if direction == "app_to_google":
        result = await sync_service.sync_app_to_google()
    elif direction == "google_to_app":
        result = await sync_service.sync_google_to_app()
    elif direction == "two_way":
        result = await sync_service.sync_two_way()
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid sync direction: {direction}. Must be one of: app_to_google, google_to_app, two_way",
        )

    return result


@router.get("/status", status_code=200)
async def integration_status(
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """Get Google Calendar integration status."""
    from app.services.sync_service import is_google_connected

    return {
        "google_connected": is_google_connected(current_user.id, db),
    }