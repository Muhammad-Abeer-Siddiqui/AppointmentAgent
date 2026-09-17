"""Chat API endpoint for AI agent interaction.

This module provides the main chat interface where users can send messages
and receive AI-powered responses with tool calling for scheduling operations.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime

from app.database import get_db_session
from app.database.models import User
from app.auth import get_current_user
from app.ai.agent import SchedulingAgent


# Initialize the agent
agent = SchedulingAgent()


class ChatMessage(BaseModel):
    """Chat message request."""
    message: str
    conversation_history: Optional[List[Dict[str, str]]] = None


class ToolCall(BaseModel):
    """Tool call information."""
    name: str
    arguments: Dict[str, Any]
    result: Any


class ChatResponse(BaseModel):
    """Chat response."""
    response: str
    tool_calls: Optional[List[ToolCall]] = None
    timestamp: str


router = APIRouter(prefix="/agent/chat", tags=["Agent Chat"])


@router.post("", response_model=ChatResponse)
async def chat_with_agent(
    chat_message: ChatMessage,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Send a message to the AI scheduling agent.

    The agent will:
    1. Understand the user's intent
    2. Call appropriate tools to get scheduling information
    3. Execute any booking/modification operations through validated backend
    4. Return a natural language response

    The AI NEVER determines availability directly - it always uses tools.
    """
    try:
        # Process the message through the agent
        result = await agent.process_message(
            message=chat_message.message,
            user_id=current_user.id,
            db=db,
            conversation_history=chat_message.conversation_history,
        )

        return ChatResponse(
            response=result.get("response", "I couldn't process your request."),
            tool_calls=result.get("tool_calls") if result.get("tool_calls") else None,
            timestamp=result.get("timestamp", datetime.utcnow().isoformat()),
        )

    except Exception as e:
        print(f"Chat endpoint error: {e}")
        raise HTTPException(
            status_code=500,
            detail="An error occurred processing your request. Please try again."
        )


@router.post("/suggestion")
async def get_suggestion(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Get a proactive suggestion based on the user's schedule.

    The agent analyzes the user's calendar and provides helpful suggestions
    like upcoming meetings or empty calendar slots.
    """
    try:
        suggestion = await agent.get_suggestion(
            user_id=current_user.id,
            db=db,
        )

        return {
            "suggestion": suggestion,
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        print(f"Suggestion endpoint error: {e}")
        return {
            "suggestion": "",
            "timestamp": datetime.utcnow().isoformat(),
        }


@router.post("/clear-history")
async def clear_conversation_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Clear the conversation history for this session.

    This resets the conversation context, starting a fresh session.
    """
    await agent.clear_conversation_history(current_user.id, db)

    return {
        "message": "Conversation history cleared",
        "timestamp": datetime.utcnow().isoformat(),
    }
