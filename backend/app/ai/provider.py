"""AI Provider abstraction layer for the Appointment Scheduling Agent.

Handles communication with the Gemini API through function calling / tool use.
The LLM never determines availability directly - it always calls validated backend tools.
"""

import os
from typing import Dict, Any, List, Optional, Callable
from abc import ABC, abstractmethod

from google import genai

from app.core.config import settings


class AIProvider(ABC):
    """Abstract base class for AI providers."""

    @abstractmethod
    def generate_content(
        self,
        prompt: str,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[str] = None,
    ) -> Any:
        """Generate content using the AI model.

        Args:
            prompt: The user prompt/message
            tools: List of tool definitions for function calling
            tool_choice: Control tool calling behavior ("auto", "none", or specific function name)

        Returns:
            AI response containing text and/or tool calls
        """
        pass


class GeminiProvider(AIProvider):
    """Gemini API provider with function calling support.

    Features:
    - Structured tool definitions for scheduling operations
    - Tool result handling and retry logic
    - Conversation state management
    - Confirmation policy enforcement
    """

    def __init__(self, model_name: str = None):
        """Initialize the Gemini provider.

        Args:
            model_name: Gemini model name (default from GEMINI_MODEL env var or gemini-1.5-flash)
        """
        if model_name is None:
            model_name = os.environ.get("GEMINI_MODEL", "gemini-1.5-flash")
        self.api_key = os.environ.get("GEMINI_API_KEY", settings.GEMINI_API_KEY)
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not configured")

        # Create httpx client with SSL bypass for development
        import httpx
        http_client = None
        if settings.DEBUG:
            http_client = httpx.Client(verify=False)

        client_kwargs = {"api_key": self.api_key}
        if http_client:
            client_kwargs["http_options"] = genai.types.HttpOptions(httpx_client=http_client)

        self.client = genai.Client(**client_kwargs)
        self.model_name = model_name

    def generate_content(
        self,
        prompt: str,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[str] = None,
    ) -> Any:
        """Generate content with optional tool support.

        Args:
            prompt: The user prompt/message
            tools: List of tool definitions for function calling
            tool_choice: "auto" (default), "none", or specific function name

        Returns:
            GenerativeModel response with potential tool calls
        """
        config = genai.types.GenerateContentConfig(
            temperature=0.2,  # Low temperature for deterministic scheduling
            top_p=0.95,
            top_k=40,
            max_output_tokens=2048,
        )

        if tools:
            # Add tool definitions to the config
            config.tools = tools
            # Set tool choice if specified
            if tool_choice:
                mode_map = {
                    "auto": genai.types.FunctionCallingConfigMode.AUTO,
                    "none": genai.types.FunctionCallingConfigMode.NONE,
                }
                config.tool_config = genai.types.ToolConfig(
                    function_calling_config=genai.types.FunctionCallingConfig(
                        mode=mode_map.get(tool_choice, genai.types.FunctionCallingConfigMode.AUTO),
                    )
                )

        last_error = None
        for attempt in range(3):
            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=config,
                )
                return response
            except Exception as e:
                last_error = e
                import time
                time.sleep(2 ** attempt)

        raise last_error

    def get_tool_definitions(self) -> List[genai.types.Tool]:
        """Get all scheduling tool definitions for Gemini.

        Returns:
            List of genai.types.Tool objects for Gemini function calling
        """
        tools = [
            genai.types.Tool(function_declarations=[
                genai.types.FunctionDeclaration(
                    name="search_availability",
                    description="Search for available time slots given constraints",
                    parameters=genai.types.Schema(
                        type=genai.types.Type.OBJECT,
                        properties={
                            "duration_minutes": genai.types.Schema(
                                type=genai.types.Type.INTEGER,
                                description="Required duration in minutes",
                            ),
                            "start_date": genai.types.Schema(
                                type=genai.types.Type.STRING,
                                description="Start date ISO, e.g. '2026-09-09'",
                            ),
                            "end_date": genai.types.Schema(
                                type=genai.types.Type.STRING,
                                description="End date ISO, e.g. '2026-09-15'",
                            ),
                            "user_tz": genai.types.Schema(
                                type=genai.types.Type.STRING,
                                description="User's IANA timezone, e.g. 'America/Toronto'",
                            ),
                        },
                        required=["duration_minutes", "start_date", "end_date", "user_tz"],
                    ),
                ),
                genai.types.FunctionDeclaration(
                    name="create_appointment",
                    description="Create a new appointment with conflict detection",
                    parameters=genai.types.Schema(
                        type=genai.types.Type.OBJECT,
                        properties={
                            "title": genai.types.Schema(
                                type=genai.types.Type.STRING,
                                description="Appointment title",
                            ),
                            "description": genai.types.Schema(
                                type=genai.types.Type.STRING,
                                description="Appointment description",
                            ),
                            "start_time": genai.types.Schema(
                                type=genai.types.Type.STRING,
                                description="ISO format datetime start",
                            ),
                            "end_time": genai.types.Schema(
                                type=genai.types.Type.STRING,
                                description="ISO format datetime end",
                            ),
                            "duration_minutes": genai.types.Schema(
                                type=genai.types.Type.INTEGER,
                                description="Duration in minutes",
                            ),
                        },
                        required=["title", "start_time", "end_time", "duration_minutes"],
                    ),
                ),
                genai.types.FunctionDeclaration(
                    name="multi_person_availability",
                    description="Find slots available for multiple attendees",
                    parameters=genai.types.Schema(
                        type=genai.types.Type.OBJECT,
                        properties={
                            "attendee_ids": genai.types.Schema(
                                type=genai.types.Type.ARRAY,
                                items=genai.types.Schema(type=genai.types.Type.INTEGER),
                                description="List of user IDs to find common availability for",
                            ),
                            "duration_minutes": genai.types.Schema(
                                type=genai.types.Type.INTEGER,
                                description="Required duration in minutes",
                            ),
                            "start_date": genai.types.Schema(
                                type=genai.types.Type.STRING,
                                description="Start date ISO, e.g. '2026-09-09'",
                            ),
                            "end_date": genai.types.Schema(
                                type=genai.types.Type.STRING,
                                description="End date ISO, e.g. '2026-09-15'",
                            ),
                            "user_tz": genai.types.Schema(
                                type=genai.types.Type.STRING,
                                description="Primary user's IANA timezone",
                            ),
                        },
                        required=["attendee_ids", "duration_minutes", "start_date", "end_date", "user_tz"],
                    ),
                ),
                genai.types.FunctionDeclaration(
                    name="update_appointment",
                    description="Update an existing appointment",
                    parameters=genai.types.Schema(
                        type=genai.types.Type.OBJECT,
                        properties={
                            "appointment_id": genai.types.Schema(
                                type=genai.types.Type.INTEGER,
                                description="Appointment ID to update",
                            ),
                            "title": genai.types.Schema(
                                type=genai.types.Type.STRING,
                                description="New appointment title",
                            ),
                            "description": genai.types.Schema(
                                type=genai.types.Type.STRING,
                                description="New appointment description",
                            ),
                            "start_time": genai.types.Schema(
                                type=genai.types.Type.STRING,
                                description="New ISO format datetime start",
                            ),
                            "end_time": genai.types.Schema(
                                type=genai.types.Type.STRING,
                                description="New ISO format datetime end",
                            ),
                        },
                        required=["appointment_id"],
                    ),
                ),
                genai.types.FunctionDeclaration(
                    name="cancel_appointment",
                    description="Cancel an existing appointment",
                    parameters=genai.types.Schema(
                        type=genai.types.Type.OBJECT,
                        properties={
                            "appointment_id": genai.types.Schema(
                                type=genai.types.Type.INTEGER,
                                description="Appointment ID to cancel",
                            ),
                            "confirm": genai.types.Schema(
                                type=genai.types.Type.BOOLEAN,
                                description="Confirm the cancellation",
                            ),
                        },
                        required=["appointment_id", "confirm"],
                    ),
                ),
                genai.types.FunctionDeclaration(
                    name="get_user_profile",
                    description="Get authenticated user's profile and preferences",
                    parameters=genai.types.Schema(
                        type=genai.types.Type.OBJECT,
                        properties={
                            "user_id": genai.types.Schema(
                                type=genai.types.Type.INTEGER,
                                description="User ID",
                            ),
                        },
                    ),
                ),
                genai.types.FunctionDeclaration(
                    name="set_user_preferences",
                    description="Update user scheduling preferences",
                    parameters=genai.types.Schema(
                        type=genai.types.Type.OBJECT,
                        properties={
                            "preferred_earliest_time": genai.types.Schema(
                                type=genai.types.Type.STRING,
                                description="Preferred earliest time HH:MM",
                            ),
                            "preferred_latest_time": genai.types.Schema(
                                type=genai.types.Type.STRING,
                                description="Preferred latest time HH:MM",
                            ),
                            "avoid_lunch": genai.types.Schema(
                                type=genai.types.Type.BOOLEAN,
                                description="Whether to avoid lunch hours",
                            ),
                            "min_break_minutes": genai.types.Schema(
                                type=genai.types.Type.INTEGER,
                                description="Minimum break minutes between appointments",
                            ),
                            "preferred_duration_minutes": genai.types.Schema(
                                type=genai.types.Type.INTEGER,
                                description="Preferred appointment duration in minutes",
                            ),
                        },
                    ),
                ),
                genai.types.FunctionDeclaration(
                    name="get_calendar",
                    description="Get user's calendar appointments",
                    parameters=genai.types.Schema(
                        type=genai.types.Type.OBJECT,
                        properties={
                            "start_date": genai.types.Schema(
                                type=genai.types.Type.STRING,
                                description="Start date ISO, e.g. '2026-09-09'",
                            ),
                            "end_date": genai.types.Schema(
                                type=genai.types.Type.STRING,
                                description="End date ISO, e.g. '2026-09-15'",
                            ),
                        },
                    ),
                ),
                genai.types.FunctionDeclaration(
                    name="confirm_action",
                    description="Get user confirmation for destructive actions",
                    parameters=genai.types.Schema(
                        type=genai.types.Type.OBJECT,
                        properties={
                            "action": genai.types.Schema(
                                type=genai.types.Type.STRING,
                                description="Description of the action being confirmed",
                            ),
                            "details": genai.types.Schema(
                                type=genai.types.Type.STRING,
                                description="Details of the action",
                            ),
                        },
                        required=["action", "details"],
                    ),
                ),
                genai.types.FunctionDeclaration(
                    name="sync_to_google_calendar",
                    description="Sync appointments to Google Calendar (requires Google Calendar connection)",
                    parameters=genai.types.Schema(
                        type=genai.types.Type.OBJECT,
                        properties={},
                    ),
                ),
                genai.types.FunctionDeclaration(
                    name="sync_from_google_calendar",
                    description="Sync events from Google Calendar to app (requires Google Calendar connection)",
                    parameters=genai.types.Schema(
                        type=genai.types.Type.OBJECT,
                        properties={},
                    ),
                ),
                genai.types.FunctionDeclaration(
                    name="create_recurring_appointment",
                    description="Create a recurring series of appointments (daily, weekly, or monthly)",
                    parameters=genai.types.Schema(
                        type=genai.types.Type.OBJECT,
                        properties={
                            "title": genai.types.Schema(
                                type=genai.types.Type.STRING,
                                description="Appointment title for all occurrences",
                            ),
                            "description": genai.types.Schema(
                                type=genai.types.Type.STRING,
                                description="Appointment description",
                            ),
                            "start_time": genai.types.Schema(
                                type=genai.types.Type.STRING,
                                description="ISO format datetime of first occurrence",
                            ),
                            "duration_minutes": genai.types.Schema(
                                type=genai.types.Type.INTEGER,
                                description="Duration of each occurrence in minutes",
                            ),
                            "recurrence_rule": genai.types.Schema(
                                type=genai.types.Type.STRING,
                                description="Recurrence pattern: daily, weekly, or monthly",
                            ),
                            "recurrence_end_date": genai.types.Schema(
                                type=genai.types.Type.STRING,
                                description="ISO format date when recurrence ends, e.g. 2026-12-31",
                            ),
                            "interval": genai.types.Schema(
                                type=genai.types.Type.INTEGER,
                                description="Interval between occurrences (default 1). E.g., 2 for every other week",
                            ),
                        },
                        required=["start_time", "duration_minutes", "recurrence_rule", "recurrence_end_date"],
                    ),
                ),
                genai.types.FunctionDeclaration(
                    name="cancel_recurring_series",
                    description="Cancel all appointments in a recurring series",
                    parameters=genai.types.Schema(
                        type=genai.types.Type.OBJECT,
                        properties={
                            "series_id": genai.types.Schema(
                                type=genai.types.Type.STRING,
                                description="Series ID of the recurring appointments to cancel",
                            ),
                            "confirm": genai.types.Schema(
                                type=genai.types.Type.BOOLEAN,
                                description="Confirm the cancellation",
                            ),
                        },
                        required=["series_id", "confirm"],
                    ),
                ),
            ]),
        ]
        return tools

    def create_system_prompt(self) -> str:
        """Create the system prompt that guides the AI agent behavior.

        The system prompt enforces the pattern:
        LLM -> validated tools -> backend -> database -> result -> LLM -> User Response

        Returns:
        System prompt string
        """
        return """You are the AI Scheduling Agent for an appointment scheduling application.

        CORE PRINCIPLE: The LLM never determines availability directly.
        ALWAYS use the provided tools to search for slots, create appointments,
        and check conflicts. The backend handles all scheduling logic, conflict
        detection, and database operations.

        You have access to the following tools:
        - search_availability: Find available time slots
        - create_appointment: Create a new appointment (validated)
        - multi_person_availability: Find slots for multiple people
        - update_appointment: Modify an existing appointment
        - cancel_appointment: Cancel an appointment (requires confirmation)
        - get_user_profile: Get user profile and preferences
        - set_user_preferences: Update user scheduling preferences
        - get_calendar: Get user's calendar appointments
        - confirm_action: Get user confirmation for destructive actions
        - create_recurring_appointment: Create a recurring series of appointments
        - cancel_recurring_series: Cancel all appointments in a recurring series

        TOOL USAGE PATTERN:
        1. User gives you a scheduling request (e.g., "Find me a 30-min slot next week")
        2. You call the appropriate tool(s) with the right parameters
        3. The backend validates everything and returns results
        4. You present the results to the user naturally
        5. If the user confirms, you call create_appointment

        RULES:
        - NEVER bypass the backend tools to determine availability yourself
        - ALWAYS validate user intent before destructive actions (cancellation, rescheduling)
        - Use confirmed_action tool before canceling or rescheduling appointments
        - Present results in a user-friendly, natural way
        - Ask for clarification when requests are ambiguous
        - Respect user preferences (timezone, working hours, lunch avoidance, etc.)
        - When presenting slots, explain WHY each was recommended using the "reasons" field

        CONFIRMATION PATTERN:
        - For destructive actions (cancel, reschedule), ALWAYS use the confirm_action tool first
        - Present the action details to the user and wait for explicit confirmation
        - Only proceed with the actual operation after confirmation

        CONFLICT RECOVERY:
        - When create_appointment returns a conflict (success: false), ASK the user:
        * "That time was just taken. Would you like me to find another slot?"
        - If user says yes, search for alternative slots with the same constraints
        - Present alternatives and let the user choose
        - NEVER auto-book without user confirmation

        SLOT PRESENTATION:
        - When presenting slots, include the "reasons" field to explain why each slot was recommended
        - Examples: "Within your preferred time window", "Morning slot", "Avoids lunch hour"
        - Help users understand why certain times are better matches

        WHEN SEARCH RETURNS NO SLOTS:
        - DO NOT give up or say "I've processed your request" without actually doing anything
        - ALWAYS try alternative approaches:
        * Try shorter duration (e.g., if 8 hours fails, try 4 hours, then 2 hours, then 1 hour)
        * Try broader time windows (e.g., "after 6 PM" instead of "after 10 PM", or "tomorrow" instead of "tomorrow after 10 PM")
        * Try different dates (next day, next week, etc.)
        * Try multiple shorter sessions instead of one long session
        - After trying alternatives, if still no slots, ASK the user:
        * "Would you like me to try a shorter duration?"
        * "Would a different day work better?"
        * "What's the minimum duration you need?"
        - NEVER just say "I've processed your request" without actually doing something

        WHEN SLOTS ARE FOUND:
        - Present the top 3 options clearly with times, scores, and reasons
        - Ask which slot the user prefers
        - When user selects a slot, IMMEDIATELY call create_appointment
        - Confirm the booking with details

        RESPOND naturally to the user. Use tools when scheduling is needed. Ask for clarification when unsure. NEVER give up without trying alternatives first."""

    def parse_tool_call(self, response: Any) -> Optional[Dict[str, Any]]:
        """Parse a tool call from the AI response.

        Args:
            response: The Gemini response object

        Returns:
            Tool call dict if present, None otherwise
        """
        if hasattr(response, "tool_calls") and response.tool_calls:
            return response.tool_calls[0]

        if hasattr(response, "candidates") and response.candidates:
            candidate = response.candidates[0]
            if hasattr(candidate, "content") and hasattr(candidate.content, "parts"):
                for part in candidate.content.parts:
                    if hasattr(part, "function_call"):
                        return {
                            "name": part.function_call.name,
                            "arguments": part.function_call.args,
                        }

        return None

    def extract_tool_arguments(self, tool_call: Dict[str, Any]) -> Dict[str, Any]:
        """Extract and validate arguments from a tool call.

        Args:
            tool_call: The raw tool call from the AI

        Returns:
            Cleaned tool arguments
        """
        name = tool_call.get("name", "")
        args = tool_call.get("arguments", {})

        # Ensure required fields based on tool name
        if name == "search_availability":
            defaults = {
                "duration_minutes": args.get("duration_minutes", 60),
                "start_date": args.get("start_date", datetime.utcnow().strftime("%Y-%m-%d")),
                "end_date": args.get("end_date", (datetime.utcnow() + timedelta(days=7)).strftime("%Y-%m-%d")),
                "user_tz": args.get("user_tz", "UTC"),
            }
            return defaults

        if name == "create_appointment":
            # Will be validated by backend
            return args

        if name == "multi_person_availability":
            defaults = {
                "duration_minutes": args.get("duration_minutes", 60),
                "start_date": args.get("start_date", datetime.utcnow().strftime("%Y-%m-%d")),
                "end_date": args.get("end_date", (datetime.utcnow() + timedelta(days=7)).strftime("%Y-%m-%d")),
                "user_tz": args.get("user_tz", "UTC"),
            }
            # Ensure attendee_ids is present
            defaults["attendee_ids"] = args.get("attendee_ids", [])
            return defaults

        if name in ("update_appointment", "cancel_appointment"):
            return args

        if name == "get_user_profile":
            return {"user_id": args.get("user_id", 1)}

        if name == "set_user_preferences":
            return args

        if name == "get_calendar":
            defaults = {
                "start_date": args.get("start_date", datetime.utcnow().strftime("%Y-%m-%d")),
                "end_date": args.get("end_date", (datetime.utcnow() + timedelta(days=7)).strftime("%Y-%m-%d")),
            }
            return defaults

        if name == "confirm_action":
            return args

        return args

    async def process_tool_result(
        self,
        tool_name: str,
        tool_result: Any,
    ) -> str:
        """Process a tool result and return a human-readable summary.

        Args:
            tool_name: Name of the tool that was called
            tool_result: The result returned from the tool

        Returns:
            Human-readable summary of the tool result
        """
        if tool_name == "search_availability":
            slots = tool_result.get("slots", [])
            duration = tool_result.get("duration_minutes", 60)
            if not slots:
                return f"I couldn't find any available {duration}-minute slots. Would you like to try a different duration or time range?"

            # Present top 3 slots
            summary = f"I found {len(slots)} available {duration}-minute slots:\n"
            for i, slot in enumerate(slots[:3]):
                start = slot.get("start", "")
                end = slot.get("end", "")
                score = slot.get("score", 50)
                summary += f"{i + 1}. {start} - {end} (score: {score}/100)\n"
            summary += "\nWhich slot would you like, or would you like me to show more options?"

            return summary

        if tool_name == "create_appointment":
            appointment = tool_result
            return f"[OK] Appointment created: {appointment.get('title', 'Untitled')} on {appointment.get('start', '')} for {appointment.get('duration_minutes', 0)} minutes"

        if tool_name == "multi_person_availability":
            slots = tool_result.get("slots", [])
            if not slots:
                return "I couldn't find any slots available for all attendees. Would you like to adjust the time range or duration?"
            summary = f"Found {len(slots)} common available slots:\n"
            for i, slot in enumerate(slots[:3]):
                start = slot.get("start", "")
                end = slot.get("end", "")
                summary += f"{i + 1}. {start} - {end}\n"
            summary += "\nWhich slot works best?"

            return summary

        if tool_name == "cancel_appointment":
            return f"[OK] Appointment {tool_result.get('id', '')} has been cancelled."

        if tool_name == "update_appointment":
            return f"[OK] Appointment {tool_result.get('id', '')} updated: {tool_result.get('title', '')}"

        if tool_name == "get_user_profile":
            user = tool_result
            return f"Profile: {user.get('name', 'Unknown')} ({user.get('email', 'unknown@example.com')}), timezone: {user.get('timezone', 'UTC')}"

        if tool_name == "set_user_preferences":
            return "[OK] Preferences updated successfully."

        if tool_name == "get_calendar":
            appointments = tool_result.get("appointments", [])
            if not appointments:
                return "No appointments found in your calendar."

            summary = f"You have {len(appointments)} appointment{'s' if len(appointments) > 1 else ''}:\n"
            for appt in appointments[:5]:
                start = appt.get("start_time", "")
                end = appt.get("end_time", "")
                title = appt.get("title", "Untitled")
                summary += f"- {title}: {start} - {end}\n"
            return summary

        if tool_name == "confirm_action":
            action = tool_result.get("action", "")
            details = tool_result.get("details", "")
            return f"Confirmation requested: {action}\nDetails: {details}"

        if tool_name == "sync_to_google_calendar":
            success = tool_result.get("success", False)
            message = tool_result.get("message", "")
            errors = tool_result.get("errors", [])
            if success:
                return f"[OK] {message}"
            else:
                error_msg = tool_result.get("error", "Sync failed")
                return f"[FAIL] Failed to sync to Google Calendar: {error_msg}"

        if tool_name == "sync_from_google_calendar":
            success = tool_result.get("success", False)
            message = tool_result.get("message", "")
            if success:
                return f"[OK] {message}"
            else:
                error_msg = tool_result.get("error", "Sync failed")
                return f"[FAIL] Failed to sync from Google Calendar: {error_msg}"

        return str(tool_result)