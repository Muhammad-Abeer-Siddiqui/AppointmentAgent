"""Main FastAPI application entry point for the AI Appointment Scheduling Agent."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.database import engine, Base
from app.database.init_db import init_db
from app.auth.routes import router as auth_router
from app.auth.google import router as google_auth_router
from app.api.users import router as users_router
from app.api.calendar import router as calendar_router
from app.api.availability import router as availability_router
from app.api.appointments import router as appointments_router
from app.api.agent import router as agent_router
from app.api.chat import router as chat_router
from app.api.preferences import router as preferences_router
from app.api.integrations import router as integrations_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown events."""
    # Startup: initialize database tables
    logger.info("Starting up - initializing database...")
    init_db()
    logger.info("Database initialized successfully.")
    yield
    # Shutdown: cleanup if needed
    logger.info("Shutting down...")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="AI Appointment Scheduling Agent",
        description="Production-quality AI appointment scheduling agent with zero operating cost",
        version="0.1.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        lifespan=lifespan,
    )

    # Set up CORS using configured allowed origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["*"],
    )

    # Include routers — each router already defines its own prefix
    app.include_router(auth_router)
    app.include_router(google_auth_router)
    app.include_router(users_router)
    app.include_router(calendar_router)
    app.include_router(availability_router)
    app.include_router(appointments_router)
    app.include_router(agent_router)
    app.include_router(chat_router)
    app.include_router(preferences_router)
    app.include_router(integrations_router)

    @app.get("/health", tags=["Health"])
    async def health_check():
        """Health check endpoint."""
        return {
            "status": "healthy",
            "service": "ai-appointment-scheduler",
            "version": "0.1.0",
        }

    @app.get("/", tags=["Root"])
    async def root():
        """Root endpoint with basic info."""
        return {
            "message": "AI Appointment Scheduling Agent",
            "version": "0.1.0",
            "docs": "/api/docs",
        }

    return app


# Create app instance for direct import
app = create_app()