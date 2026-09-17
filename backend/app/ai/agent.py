"""AI Agent for the Appointment Scheduling Agent.

Orchestrates the tool-calling loop:
User -> LLM -> Tool Call -> Backend Validation -> Database -> Result -> LLM -> User Response
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
from sqlalchemy.orm import Session

from app.ai.provider import GeminiProvider
from app.ai.tools import execute_tool
from app.database.models import User, ConversationSession, ConversationMessage


class SchedulingAgent:
    """Orchestrates AI interactions and tool execution.

    This agent:
    1. Receives user messages
    2. Calls the LLM with tool definitions and conversation history
    3. Executes any tool calls through validated backend functions
    4. Sends tool results back to LLM for natural language response (multi-turn)
    5. Stores conversation in database
    6. Returns the final response to the user

    The LLM NEVER determines availability directly - it always uses tools.
    """

    MAX_TOOL_ITERATIONS = 6

    def __init__(self, provider: Optional[GeminiProvider] = None):
        """Initialize the scheduling agent.

        Args:
            provider: AI provider instance (default: GeminiProvider)
        """
        self.provider = provider or GeminiProvider()
        self.system_prompt = self.provider.create_system_prompt()

    async def _get_or_create_session(self, user_id: int, db: Session) -> ConversationSession:
        """Get the active session for a user or create a new one."""
        session = db.query(ConversationSession).filter(
            ConversationSession.user_id == user_id
        ).order_by(ConversationSession.last_activity.desc()).first()

        if not session:
            import uuid
            session = ConversationSession(
                user_id=user_id,
                session_key=str(uuid.uuid4()),
                context={}
            )
            db.add(session)
            db.commit()
            db.refresh(session)

        return session

    async def _load_conversation_history(self, user_id: int, db: Session, limit: int = 20) -> List[Dict[str, Any]]:
        """Load recent conversation history from database."""
        session = db.query(ConversationSession).filter(
            ConversationSession.user_id == user_id
        ).order_by(ConversationSession.last_activity.desc()).first()

        if not session:
            return []

        messages = db.query(ConversationMessage).filter(
            ConversationMessage.session_id == session.id
        ).order_by(ConversationMessage.created_at.desc()).limit(limit).all()

        # Reverse to get chronological order
        messages.reverse()

        history = []
        for msg in messages:
            history.append({
                "role": msg.role,
                "content": msg.content,
                "tool_calls": msg.tool_calls if msg.tool_calls else None,
            })
        return history

    def _format_history_for_llm(self, history: List[Dict[str, Any]]) -> str:
        """Format conversation history for inclusion in LLM prompt."""
        if not history:
            return ""

        lines = ["Previous conversation:"]
        for msg in history:
            role = msg["role"]
            content = msg["content"]
            if role == "user":
                lines.append(f"User: {content}")
            elif role == "assistant":
                lines.append(f"Assistant: {content}")
                if msg.get("tool_calls"):
                    for tc in msg["tool_calls"]:
                        lines.append(f"  [Tool: {tc['name']} with args {tc['arguments']}]")
        lines.append("---")
        return "\n".join(lines)

    async def _save_message(
        self,
        session: ConversationSession,
        role: str,
        content: str,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        db: Session = None,
    ):
        """Save a message to the conversation history."""
        message = ConversationMessage(
            session_id=session.id,
            role=role,
            content=content,
            tool_calls=tool_calls or {}
        )
        db.add(message)
        session.last_activity = datetime.utcnow()
        db.commit()

    def _build_prompt(
        self,
        user: User,
        message: str,
        history_text: str,
    ) -> str:
        """Build the complete prompt for the LLM."""
        return f"""{self.system_prompt}

Current time: {datetime.utcnow().isoformat()} UTC
User: {user.name} (ID: {user.id})
Timezone: {user.timezone or 'UTC'}

{history_text}

User message: {message}

Use the appropriate tools to help with this scheduling request. Remember:
- Always use tools to search availability, create appointments, etc.
- Never make assumptions about availability
- Validate all operations through the backend tools
- If you need to confirm a destructive action, use the confirm_action tool"""

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
            conversation_history: Optional conversation history for context (if not provided, loads from DB)

        Returns:
            Response dict with 'response' text and optional 'tool_calls' list
        """
        # Get user
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return {
                "response": "I'm sorry, I couldn't find your account. Please log in again.",
                "error": "User not found",
                "user_id": user_id,
                "timestamp": datetime.utcnow().isoformat(),
            }

        # Get or create session
        session = await self._get_or_create_session(user_id, db)

        # Load history if not provided
        if conversation_history is None:
            conversation_history = await self._load_conversation_history(user_id, db)

        # Save user message
        await self._save_message(session, "user", message, db=db)

        # Format history for LLM
        history_text = self._format_history_for_llm(conversation_history)

        # Build prompt
        prompt = self._build_prompt(user, message, history_text)

        # Multi-turn tool calling loop
        all_tool_calls = []
        final_response = ""

        try:
            for iteration in range(self.MAX_TOOL_ITERATIONS):
                # Get AI response
                response = self.provider.generate_content(
                    prompt=prompt,
                    tools=self.provider.get_tool_definitions(),
                    tool_choice="auto",
                )

                # Parse response text
                response_text = ""
                if hasattr(response, "text") and response.text:
                    response_text = response.text
                elif hasattr(response, "candidates") and response.candidates:
                    candidate = response.candidates[0]
                    if hasattr(candidate, "content") and hasattr(candidate.content, "parts"):
                        for part in candidate.content.parts:
                            if hasattr(part, "text") and part.text:
                                response_text += part.text

                # Parse function calls
                function_calls = []
                if hasattr(response, "function_calls") and response.function_calls:
                    function_calls = response.function_calls
                elif hasattr(response, "candidates") and response.candidates:
                    candidate = response.candidates[0]
                    if hasattr(candidate, "content") and hasattr(candidate.content, "parts"):
                        for part in candidate.content.parts:
                            if hasattr(part, "function_call") and part.function_call:
                                function_calls.append({
                                    "name": part.function_call.name,
                                    "args": dict(part.function_call.args) if part.function_call.args else {},
                                })

                if not function_calls:
                    # No tool calls - this is the final response
                    final_response = response_text
                    break

# Execute tool calls
                tool_results = []
                for fc in function_calls:
                    if isinstance(fc, dict):
                        tool_name = fc.get("name", "")
                        tool_args = fc.get("args", {})
                    else:
                        tool_name = fc.name if hasattr(fc, "name") else ""
                        tool_args = dict(fc.args) if hasattr(fc, "args") and fc.args else {}

                    # Execute the tool
                    result = await execute_tool(
                        tool_name=tool_name,
                        arguments=tool_args,
                        user_id=user_id,
                        db=db,
                    )

                    tool_call_record = {
                        "name": tool_name,
                        "arguments": tool_args,
                        "result": result,
                    }
                    all_tool_calls.append(tool_call_record)
                    tool_results.append((tool_name, tool_args, result))

                # Handle tool errors (e.g., needs_working_hours)
                for tool_name, tool_args, result in tool_results:
                    if isinstance(result, dict) and result.get("error"):
                        if result.get("needs_working_hours"):
                            # User needs to set up working hours first
                            error_msg = result.get("error", "Please set up your working hours in Settings before searching for available slots.")
                            # Generate a user-friendly response directly instead of continuing the loop
                            final_response = f"I can't search for available slots because you haven't set up your working hours yet. {error_msg} Please go to Settings and configure your working hours first."
                            # Save assistant response and return early
                            await self._save_message(session, "assistant", final_response, all_tool_calls, db=db)
                            return {
                                "response": final_response,
                                "tool_calls": all_tool_calls if all_tool_calls else None,
                                "user_id": user_id,
                                "timestamp": datetime.utcnow().isoformat(),
                            }
                        else:
                            # Other tool errors - log and continue
                            print(f"Tool {tool_name} returned error: {result.get('error')}")

                # Auto-retry with alternative parameters when search_availability returns no slots
                for tool_name, tool_args, result in tool_results:
                    if tool_name == "search_availability" and isinstance(result, dict) and result.get("total_found", 0) == 0 and not result.get("error"):
                        # Try alternative search strategies
                        original_duration = tool_args.get("duration_minutes", 60)
                        original_start = tool_args.get("start_date")
                        original_end = tool_args.get("end_date")
                        user_tz = tool_args.get("user_tz", "UTC")
                        
                        # Strategy 1: Try shorter durations
                        for shorter_duration in [original_duration // 2, original_duration // 4, 60, 30]:
                            if shorter_duration >= 30 and shorter_duration < original_duration:
                                alt_args = {**tool_args, "duration_minutes": shorter_duration}
                                alt_result = await execute_tool("search_availability", alt_args, user_id, db)
                                if alt_result.get("total_found", 0) > 0:
                                    tool_results.append(("search_availability", alt_args, alt_result))
                                    break
                        # Strategy 2: Try broader time window (earlier start)
                        if original_start:
                            try:
                                start_dt = datetime.fromisoformat(original_start)
                                broader_start = (start_dt - timedelta(days=1)).strftime("%Y-%m-%d")
                                alt_args = {**tool_args, "start_date": broader_start}
                                alt_result = await execute_tool("search_availability", alt_args, user_id, db)
                                if alt_result.get("total_found", 0) > 0:
                                    tool_results.append(("search_availability", alt_args, alt_result))
                            except:
                                pass

                        # Strategy 3: Try different dates (extend end date)
                        if original_end:
                            try:
                                end_dt = datetime.fromisoformat(original_end)
                                broader_end = (end_dt + timedelta(days=7)).strftime("%Y-%m-%d")
                                alt_args = {**tool_args, "end_date": broader_end}
                                alt_result = await execute_tool("search_availability", alt_args, user_id, db)
                                if alt_result.get("total_found", 0) > 0:
                                    tool_results.append(("search_availability", alt_args, alt_result))
                            except:
                                pass
                # Build tool results summary for next LLM call
                tool_summaries = []
                for tool_name, tool_args, result in tool_results:
                    summary = await self.provider.process_tool_result(tool_name, result)
                    tool_summaries.append(f"Tool {tool_name} result: {summary}")

                # Add tool results summary for next LLM call
                prompt += "\n\nTool execution results:\n" + "\n".join(tool_summaries)
                prompt += "\n\nBased on these results, provide a natural language response to the user. If more tools are needed, call them. Otherwise, respond naturally."

            # If we exhausted iterations without a final response
            if not final_response:
                final_response = "I've processed your request. Let me know if you need anything else."

            # Save assistant response
            await self._save_message(session, "assistant", final_response, all_tool_calls, db=db)

            return {
                "response": final_response,
                "tool_calls": all_tool_calls if all_tool_calls else None,
                "user_id": user_id,
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            # Log error and return friendly message
            print(f"AI Agent Error: {e}")
            error_str = str(e)
            # Check for specific error types and provide helpful messages
            if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str or "quota" in error_str.lower():
                error_response = "I'm currently experiencing high demand and have reached my request limit. Please try again in a few minutes, or try again tomorrow when my quota resets."
            elif "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                error_response = "I'm currently at my request limit. Please try again in a few minutes or try again tomorrow when my quota resets."
            else:
                error_response = "I'm sorry, I encountered an error processing your request. Please try again."
            await self._save_message(session, "assistant", error_response, all_tool_calls, db=db)
            return {
                "response": error_response,
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

    async def clear_conversation_history(self, user_id: int, db: Session):
        """Clear conversation history for a user (start new session)."""
        # Delete all messages for user's sessions
        sessions = db.query(ConversationSession).filter(
            ConversationSession.user_id == user_id
        ).all()
        for session in sessions:
            db.query(ConversationMessage).filter(
                ConversationMessage.session_id == session.id
            ).delete()
            db.delete(session)
        db.commit()