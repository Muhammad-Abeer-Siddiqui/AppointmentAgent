"""Authentication routes for the AI Appointment Scheduling Agent."""

from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import validate_string_input
from app.database import get_db_session
from app.auth import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
    get_current_user_from_refresh,
)
from app.database.models import User

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    name: str = Body(...),
    email: str = Body(...),
    password: str = Body(...),
    db: Session = Depends(get_db_session),
):
    """Register a new user account."""
    # Validate inputs
    name = validate_string_input(name, "name", 100)
    email = validate_string_input(email, "email", 254)
    if not email or "@" not in email:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid email format",
        )
    if len(password) < 8:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password must be at least 8 characters",
        )

    # Check if user already exists
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Create new user
    user = User(
        name=name,
        email=email,
        password_hash=get_password_hash(password),
        timezone="UTC",  # Default, user can update
        locale="en",  # Default
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    # Create access token
    access_token = create_access_token(data={"sub": str(user.id)})

    return {
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "timezone": user.timezone,
            "locale": user.locale,
        },
        "access_token": access_token,
        "token_type": "bearer",
    }


@router.post("/login", status_code=status.HTTP_200_OK)
async def login(
    email: str = Body(...),
    password: str = Body(...),
    db: Session = Depends(get_db_session),
):
    """Login user and return access/refresh tokens."""
    email = validate_string_input(email, "email", 254)
    password = validate_string_input(password, "password", 128)

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create tokens
    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = create_refresh_token(data={"sub": str(user.id)})

    return {
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "timezone": user.timezone,
            "locale": user.locale,
        },
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


@router.post("/refresh", status_code=status.HTTP_200_OK)
async def refresh_tokens(
    refresh_token: str = Body(...),
    db: Session = Depends(get_db_session),
):
    """Refresh access token using refresh token."""
    user = await get_current_user_from_refresh(refresh_token, db)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    access_token = create_access_token(data={"sub": str(user.id)})
    return {
        "access_token": access_token,
        "token_type": "bearer",
    }


@router.post("/logout")
async def logout(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Logout user (invalidate session)."""
    # In a real implementation, we might revoke the token
    # For now, just acknowledge logout
    return {"message": "Successfully logged out"}