# Architecture

## System Overview

The AI Appointment Scheduling Agent uses a deterministic scheduling engine as the single source of truth for availability. The LLM (Gemini) handles natural language understanding but never determines availability directly — it always delegates to backend tools.

```
User (browser)
    │
    ▼
Next.js Frontend (Vercel)
    │  REST API calls
    ▼
FastAPI Backend (FastAPI Cloud)
    ├── Auth Layer (JWT + refresh tokens)
    ├── API Endpoints (REST)
    ├── AI Agent (Gemini function calling)
    │   ├── 13 validated tools
    │   └── Conversation history (DB-persisted)
    ├── Scheduling Engine (deterministic)
    │   ├── Slot generation from working hours
    │   ├── Conflict detection (UTC-based)
    │   ├── Recurrence expansion
    │   ├── Multi-person availability intersection
    │   └── Preference-aware scoring
    └── PostgreSQL (Supabase)
        ├── Users, Appointments, WorkingHours
        ├── UserPreferences, ExternalIntegrations
        └── ChatSessions, ChatMessages
```

## Core Design Principles

1. **LLM never determines availability** — only the engine does
2. **All tool calls are validated** — input validation, auth checks, conflict detection
3. **Deterministic scoring** — preferences produce reproducible slot rankings
4. **$0 operating cost** — all services use free tiers

## Scheduling Engine

The engine at `backend/app/scheduling/engine.py` is the heart of the system:

### Slot Generation (`generate_available_slots`)
1. Iterate through each day in the date range
2. Look up working hours for the day (ISO weekday convention: 1=Mon, 7=Sun)
3. Generate time slots within working hours, stepping by `duration + buffer`
4. Filter out slots that overlap existing appointments
5. Score remaining slots based on user preferences

### Slot Scoring (`_calculate_slot_score`)
- **Base score**: 50 points
- **Morning preference bonus**: +15 if before 12:00
- **Lunch avoidance penalty**: -20 if overlaps 12:00-13:00
- **Buffer bonus**: +10 if `min_break_minutes` gap from nearest appointment
- **Urgency bonus**: +10 if within 2 days
- Scores rounded to nearest 5, clamped to [5, 100]

### Conflict Detection (`detect_conflict`)
- Converts both new and existing appointment times to UTC
- Checks for overlap: `start < existing.end AND end > existing.start`

### Recurrence (`expand_recurrence`)
- Supports `daily`, `weekly`, `monthly` rules with configurable interval
- Handles month-end overflow (Jan 31 → Feb 28)

## AI Agent

The agent at `backend/app/ai/agent.py` and `provider.py`:
- Uses Google Gemini with function calling
- 13 validated tools that always go through the backend
- Multi-turn conversation loop (max 10 iterations)
- Conversation history persisted in PostgreSQL

### Tool List
1. `search_availability` — Find open slots
2. `create_appointment` — Book with conflict detection + alternatives
3. `update_appointment` — Modify existing
4. `cancel_appointment` — Cancel with confirmation
5. `get_calendar` — List appointments
6. `get_user_profile` — User info
7. `set_user_preferences` — Update preferences
8. `multi_person_availability` — Common slots for multiple users
9. `create_recurring_appointment` — Recurring series
10. `cancel_recurring_series` — Cancel all in series
11. `confirm_action` — Explicit confirmation for destructive ops
12. `sync_to_google_calendar` — Push to Google
13. `sync_from_google_calendar` — Pull from Google

## Security

- **Rate limiting**: 60 req/min, 500 req/hr per IP (in-memory sliding window)
- **Input validation**: String length limits, dangerous pattern detection
- **Security headers**: X-Content-Type-Options, X-Frame-Options, HSTS
- **JWT auth**: Short-lived access tokens (15 min) + refresh tokens (7 days)
- **CORS**: Whitelisted origins only
- **Password hashing**: bcrypt via passlib

## Database Schema

Key tables:
- `users` — id, email, password_hash, name, timezone, locale
- `appointments` — id, user_id, title, start/end times, status, recurrence_rule, series_id
- `working_hours` — day_of_week (ISO 1-7), start/end times, is_off_day
- `user_preferences` — earliest/latest times, avoid_lunch, min_break, preferred_duration
- `chat_sessions` / `chat_messages` — conversation persistence
- `external_integrations` — Google Calendar OAuth tokens

## Frontend

- **App Router** (Next.js 15): `/dashboard`, `/dashboard/calendar`, `/dashboard/chat`, `/dashboard/settings`
- **MonthCalendar**: Visual month grid with appointment dot indicators
- **WeekView**: 7-day time grid with positioned appointment blocks
- **Chat**: AI conversation with tool call indicators and appointment suggestion cards
- **Auth**: JWT stored in localStorage, auto-refresh
