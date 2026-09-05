"""AI Agent for the Appointment Scheduling Agent.

Orchestrates the tool-calling loop:
User → LLM → Tool Call → Backend Validation → Database → Result → LLM → User Response
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
from sqlalchemy.orm import Session

from app.ai.provider import GeminiProvider
from app.ai.tools import execute_tool
from app.database.models import User


class SchedulingAgent:
    """Orchestrates AI interactions and tool execution.

    This agent:
    1. Receives user messages
    2. Calls the LLM with tool definitions
    3. Executes any tool calls through validated backend functions
    4. Returns the final response to the user

    The LLM NEVER determines availability directly - it always uses tools.
    """

    def __init__(self, provider: Optional[GeminiProvider] = None):
        """Initialize the scheduling agent.

        Args:
            provider: AI provider instance (default: GeminiProvider)
        """
        self.provider = provider or GeminiProvider()
        self.system_prompt = self.provider.create_system_prompt()

    async def process_message(
        self,
        message: str,
        user_id: int,
        db: Session,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """Process a user message and return a response.

        Args:
            message: User's message text
            user_id: Authenticated user ID
            db: Database session
            conversation_history: Optional conversation history for context

        Returns:
            Response dict with 'response' text and optional 'tool_calls' list
        """
        # Build the conversation context
        user = db.query(User).filter(User.id == user_id).first()
        user_name = user.name if user else "User"

        # Prepare the prompt with context
        prompt = f"""{self.system_prompt}

Current time: {datetime.utcnow().isoformat()} UTC
User: {user_name} (ID: {user_id})
Timezone: {user.timezone or 'UTC'}

User message: {message}

Use the appropriate tools to help with this scheduling request. Remember:
- Always use tools to search availability, create appointments, etc.
- Never make assumptions about availability
- Validate all operations through the backend tools"""

        # Get AI response
        try:
            response = self.provider.generate_content(
                prompt=prompt,
                tools=self.provider.get_tool_definitions(),
                tool_choice="auto",
            )

            # Check for tool calls
            tool_calls = []
            response_text = ""

            # Parse the response
            if hasattr(response, "text"):
                response_text = response.text

            if hasattr(response, "tool_calls") and response.tool_calls:
                # Process each tool call
                for tool_call in response.tool_calls:
                    tool_name = tool_call.name if hasattr(tool_call, "name") else tool_call.get("name", "")
                    tool_args = tool_call.arguments if hasattr(tool_call, "arguments") else tool_call.get("arguments", {})

                    # Execute the tool
                    result = await execute_tool(
                        tool_name=tool_name,
                        arguments=tool_args,
                        user_id=user_id,
                        db=db,
                    )

                    tool_calls.append({
                        "name": tool_name,
                        "arguments": tool_args,
                        "result": result,
                    })

                    # Process result to get human-readable summary
                    summary = await self.provider.process_tool_result(tool_name, result)

                    if not response_text:
                        response_text = summary

            # If we got tool calls, we might want to do another iteration
            # For now, return the first response
            return {
                "response": response_text or "I'm sorry, I couldn't process your request. Please try again.",
                "tool_calls": tool_calls if tool_calls else None,
                "user_id": user_id,
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            # Log error and return friendly message
            print(f"AI Agent Error: {e}")
            return {
                "response": "I'm sorry, I encountered an error processing your request. Please try again.",
                "error": str(e),
                "user_id": user_id,
                "timestamp": datetime.utcnow().isoformat(),
            }

    async def process_tool_response(
        self,
        tool_calls: List[Dict[str, Any]],
        tool_results: List[Dict[str, Any]],
        user_id: int,
        db: Session,
    ) -> str:
        """Process tool results and generate a final response.

        Args:
            tool_calls: Original tool calls
            tool_results: Results from tool execution
            user_id: User ID
            db: Database session

        Returns:
            Final response text
        """
        # Build context with tool results
        context_parts = []
        for tc, tr in zip(tool_calls, tool_results):
            name = tc.get("name", "unknown")
            summary = await self.provider.process_tool_result(name, tr)
            context_parts.append(f"Tool {name} result: {summary}")

        context = "\n".join(context_parts)

        # Get AI to generate a natural language response
        try:
            response = self.provider.generate_content(
                prompt=f"""Based on the tool execution results below, provide a natural language response to the user.
Focus on the results and next steps.

Tool results:
{context}

Generate a helpful, concise response:""",
                tools=None,
                tool_choice="none",
            )

            if hasattr(response, "text"):
                return response.text

            return context

        except Exception as e:
            print(f"AI response generation error: {e}")
            return context

    async def get_suggestion(
        self,
        user_id: int,
        db: Session,
    ) -> str:
        """Get a proactive suggestion based on user's schedule.

        Args:
            user_id: User ID
            db: Database session

        Returns:
            Proactive suggestion text
        """
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return ""

        from datetime import timedelta
        now = datetime.utcnow()

        # Get upcoming appointments in the next 24 hours
        from app.database.models import Appointment
        upcoming = db.query(Appointment).filter(
            Appointment.user_id == user_id,
            Appointment.status == "scheduled",
            Appointment.start_time >= now,
            Appointment.start_time <= now + timedelta(hours=24),
        ).all()

        if upcoming:
            next_appt = upcoming[0]
            hours_until = (next_appt.start_time - now).total_seconds() / 3600
            if hours_until < 2:
                return f"You have {next_appt.title} in {int(hours_until * 60)} minutes."
            else:
                return f"Your next meeting is {next_appt.title} at {next_appt.start_time.strftime('%I:%M %p')}."

        # Suggest scheduling if calendar is empty
        return "Your calendar looks free! Would you like to schedule something?"

    def clear_conversation_history(self):
        """Clear conversation history (for new session)."""
        self.conversation_history = []
