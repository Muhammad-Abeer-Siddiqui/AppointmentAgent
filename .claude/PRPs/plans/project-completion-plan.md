# Plan: Project Completion - From Current State to Production-Ready

## Summary
The AI Appointment Scheduling Agent has Phases 1-4 functionally complete (foundation, core scheduler, AI agent, chat UI). This plan addresses remaining bugs, quality gaps, and unimplemented features across Phases 5-11 to reach the competition definition of done.

## User Story
As a competition participant, I want a fully functional, polished, production-quality AI scheduling agent that meets ALL completion criteria in the PROJECT_SPEC, so that I can submit a competitive entry.

## Problem → Solution
Current state: Core functionality works (auth, scheduling, AI agent, chat UI, calendar, settings). Multiple bugs exist (hardcoded URLs, duplicate endpoints, missing types), and advanced features (recurring appointments, benchmark, deployment) are missing. → Desired state: All 30+ completion checklist items checked, all bugs fixed, all advanced features implemented, publicly accessible.

## Metadata
- **Complexity**: Large
- **Source PRD**: PROJECT_SPEC.md (Phase 11 - Final Polish)
- **Estimated Files**: ~50 files to modify/create
- **Gemini Quota**: DO NOT call Gemini API during implementation. Manual user testing only.

---

## Current State Assessment

### What's DONE (Phases 1-4)

| Area | Status | Notes |
|------|--------|-------|
| Auth (register/login/JWT) | Done | bcrypt + JWT + refresh tokens |
| Database models (10 tables) | Done | User, Preferences, WorkingHours, Appointments, etc. |
| Scheduling engine | Done | Slot generation, conflict detection, scoring, multi-person |
| Timezone utilities | Done | Full conversion library with DST |
| Gemini AI agent | Done | 11 tools, multi-turn loop, auto-retry |
| Chat API | Done | /agent/chat, /agent/suggestion, /clear-history |
| Chat UI | Done | Messages, tool indicators, slot suggestions, confirmation |
| Calendar page | Done (buggy) | Hardcoded localhost:8000 URL |
| Settings page | Done | Profile, prefs, working hours, Google Calendar sync |
| Google Calendar sync | Done | Two-way sync, OAuth2 flow |
| Integration tests | 20/25 passing | 5 skipped for missing endpoints |

### What's BUGGY (Must Fix)

| Bug | File | Issue |
|-----|------|-------|
| Hardcoded URL | `frontend/src/app/dashboard/calendar/page.tsx:46` | `http://localhost:8000` instead of API client |
| Window global hack | `frontend/src/app/dashboard/chat/page.tsx` | `(window as any).__selectedSlot` instead of React state |
| Duplicate preference endpoints | `backend/app/api/users.py` | Two GET/PATCH /preferences defined, second shadows first |
| Inline availability logic | `backend/app/api/availability.py:75-131` | Duplicates engine logic, should use engine directly |
| Missing `google-genai` in requirements.txt | `backend/requirements.txt` | Package imported but not listed |
| No Google OAuth callback page | Frontend | OAuth redirect has no frontend route to handle it |
| Navigation uses `<a>` tags | `frontend/src/app/dashboard/layout.tsx` | Should use Next.js `<Link>` for SPA navigation |

### What's MISSING (Must Build)

| Feature | Priority | Phase |
|---------|----------|-------|
| `src/types/` directory | High | 5 |
| Recurring appointments | High | 5 |
| Preference memory (agent remembers prefs) | High | 5 |
| Smart slot ranking explanations | Medium | 5 |
| Conflict recovery (agent recovers from stale slots) | Medium | 5 |
| Error boundary component | High | 5 |
| Loading skeletons | Medium | 5 |
| 404 page | Low | 5 |
| Weather API integration | Medium | 6 |
| Holiday calendar | Low | 6 |
| Security audit pass | High | 7 |
| Benchmark suite (100+ scenarios) | High | 9 |
| Public deployment | High | 10 |
| Mobile responsiveness improvements | Medium | 11 |
| Documentation (README, ARCHITECTURE, API, DEPLOYMENT) | High | 11 |

---

## Mandatory Reading

| Priority | File | Why |
|----------|------|-----|
| P0 | `PROJECT_SPEC.md` lines 1784-1855 | Definition of Done checklist |
| P0 | `PLAN.md` lines 492-512 | Completion criteria |
| P1 | `backend/app/ai/agent.py` | Agent loop, tool calling, multi-turn |
| P1 | `backend/app/ai/tools.py` | Tool implementations |
| P1 | `backend/app/scheduling/engine.py` | Core scheduling logic |
| P2 | `frontend/src/app/dashboard/chat/page.tsx` | Chat UI with window global hack |
| P2 | `frontend/src/app/dashboard/calendar/page.tsx` | Hardcoded URL bug |

---

## Files to Change

| File | Action | Justification |
|------|--------|---------------|
| `backend/app/api/users.py` | FIX | Remove duplicate preference endpoints |
| `backend/app/api/availability.py` | REFACTOR | Replace inline logic with engine call |
| `backend/requirements.txt` | UPDATE | Add `google-genai` |
| `frontend/src/app/dashboard/calendar/page.tsx` | FIX | Replace hardcoded URL with API client |
| `frontend/src/app/dashboard/chat/page.tsx` | FIX | Replace window global hack with React state |
| `frontend/src/app/dashboard/layout.tsx` | FIX | Replace `<a>` with Next.js `<Link>` |
| `frontend/src/types/index.ts` | CREATE | Shared TypeScript types |
| `frontend/src/components/ErrorBoundary.tsx` | CREATE | Top-level error boundary |
| `frontend/src/components/LoadingSkeleton.tsx` | CREATE | Reusable loading skeletons |
| `frontend/src/app/not-found.tsx` | CREATE | 404 page |
| `frontend/src/app/auth/callback/page.tsx` | CREATE | Google OAuth callback handler |
| `backend/app/scheduling/engine.py` | EXTEND | Add recurring appointment support |
| `backend/app/database/models.py` | EXTEND | Recurring appointment fields |
| `backend/app/ai/tools.py` | EXTEND | Recurring appointment tool |
| `backend/tests/test_integration.py` | FIX | Implement skipped endpoints |
| `.claude/PRPs/plans/project-completion-plan.md` | CREATE | This file |

---

## NOT Building (Out of Scope)

- Location-aware scheduling (Phase 27 - advanced, not in completion criteria)
- Weather-aware scheduling (Phase 6 - optional, not in completion criteria)
- Email notifications (Phase 28 - requires paid provider)
- Browser push notifications (out of scope for competition)
- Custom domain (not required, can use platform subdomain)

---

## Step-by-Step Tasks

### Task 1: Fix Bugs - Backend
- **ACTION**: Fix duplicate endpoints, remove inline availability logic, update requirements.txt
- **IMPLEMENT**:
  1. `backend/app/api/users.py`: Remove the duplicate GET/PATCH /preferences endpoints (keep the ones from `preferences.py` router)
  2. `backend/app/api/availability.py`: Replace inline slot generation (lines 75-131) with call to `generate_available_slots()` from `app.scheduling.engine`
  3. `backend/requirements.txt`: Add `google-genai` package
- **MIRROR**: Follow existing code patterns in `app/api/users.py` and `app/scheduling/engine.py`
- **GOTCHA**: The `availability.py` inline logic uses different parameters than the engine - must map correctly
- **VALIDATE**: Run `pytest tests/` - existing 20 unit tests should still pass

### Task 2: Fix Bugs - Frontend
- **ACTION**: Fix hardcoded URLs, window global hack, navigation
- **IMPLEMENT**:
  1. `frontend/src/app/dashboard/calendar/page.tsx`: Replace `http://localhost:8000` with `apiFetch` from `@/lib/api`
  2. `frontend/src/app/dashboard/chat/page.tsx`: Replace `(window as any).__selectedSlot` with React state (`useState` for selected slot)
  3. `frontend/src/app/dashboard/layout.tsx`: Replace `<a href="/dashboard">` with `<Link href="/dashboard">` from `next/link`
- **MIRROR**: Follow existing patterns in `frontend/src/lib/api.ts` for API calls
- **GOTCHA**: The chat page's confirmation handler uses window global to pass slot data to the booking handler - need to restructure with state
- **VALIDATE**: `npm run build` should complete without errors

### Task 3: Create Shared Types
- **ACTION**: Extract duplicated types into shared location
- **IMPLEMENT**: Create `frontend/src/types/index.ts` with:
  ```typescript
  export interface User { id: number; name: string; email: string; timezone: string; locale: string; }
  export interface Appointment { id: number; title: string; description: string; start_time: string; end_time: string; duration_minutes: number; status: string; }
  export interface Preferences { preferred_earliest_time: string; preferred_latest_time: string; avoid_lunch: boolean; min_break_minutes: number; preferred_duration_minutes: number; }
  export interface WorkingHours { day_of_week: number; start_time: string; end_time: string; is_off_day: boolean; }
  export interface GoogleStatus { connected: boolean; email?: string; }
  export interface Message { id: string; role: 'user' | 'assistant'; content: string; timestamp: string; toolCalls?: ToolCall[]; }
  export interface ToolCall { name: string; arguments: Record<string, any>; result?: any; }
  export interface AvailableSlot { start: string; end: string; score: number; }
  ```
  Update all components to import from `@/types` instead of defining locally.
- **MIRROR**: Follow naming conventions from existing inline types
- **GOTCHA**: Some types have slight differences between files (e.g., `Appointment` in `dashboard/page.tsx` vs `calendar/page.tsx`) - need to reconcile
- **VALIDATE**: `npm run build` should complete without type errors

### Task 4: Add Error Boundary and Loading States
- **ACTION**: Create reusable error boundary and loading skeleton components
- **IMPLEMENT**:
  1. Create `frontend/src/components/ErrorBoundary.tsx` - React error boundary with fallback UI
  2. Create `frontend/src/components/LoadingSkeleton.tsx` - Skeleton variants for cards, text, calendar
  3. Wrap dashboard layout in ErrorBoundary
  4. Add loading skeletons to dashboard, calendar, and settings pages
- **MIRROR**: Follow existing component patterns in `frontend/src/components/`
- **VALIDATE**: `npm run build` completes

### Task 5: Create Missing Pages
- **ACTION**: Add 404 page and Google OAuth callback page
- **IMPLEMENT**:
  1. Create `frontend/src/app/not-found.tsx` - styled 404 with link back to dashboard
  2. Create `frontend/src/app/auth/callback/page.tsx` - handles Google OAuth redirect, extracts code, calls backend callback endpoint, redirects to settings
- **MIRROR**: Follow existing page patterns in `frontend/src/app/`
- **GOTCHA**: Google OAuth callback needs to handle error responses (user denies access, etc.)
- **VALIDATE**: Navigate to `/nonexistent` shows 404; Google OAuth flow completes

### Task 6: Implement Skipped Integration Test Endpoints
- **ACTION**: Add missing appointment endpoints so integration tests pass
- **IMPLEMENT**:
  1. `backend/app/api/appointments.py`: Add `GET /appointments/{id}` and `PATCH /appointments/{id}` endpoints
  2. Verify all 25 integration tests pass (currently 5 skipped)
- **MIRROR**: Follow existing patterns in `backend/app/api/appointments.py`
- **GOTCHA**: PATCH endpoint must validate user ownership before allowing update
- **VALIDATE**: `pytest tests/test_integration.py` - 25/25 passing

### Task 7: Recurring Appointments
- **ACTION**: Add recurring appointment support to engine and agent
- **IMPLEMENT**:
  1. `backend/app/database/models.py`: Add `recurrence_pattern` (daily/weekly/monthly), `recurrence_interval`, `recurrence_end_date`, `parent_id` (self-referential FK for recurring series) fields to Appointment model
  2. `backend/app/scheduling/engine.py`: Add `generate_recurring_slots()` that creates instances of a recurring pattern within a date range
  3. `backend/app/ai/tools.py`: Update `create_appointment` tool to accept recurrence parameters
  4. `backend/app/ai/provider.py`: Update tool schema to include recurrence fields
  5. `frontend/src/app/dashboard/chat/page.tsx`: Handle recurrence display in appointment suggestions
- **MIRROR**: Follow existing patterns in `engine.py` for slot generation
- **GOTCHA**: Must handle conflicts for each occurrence individually; must not create infinite loops with no end date
- **VALIDATE**: Create "every Monday at 3 PM" appointment, verify multiple instances created

### Task 8: Fix Chat ToolCallIndicator During Loading
- **ACTION**: Show tool call indicators during agent processing
- **IMPLEMENT**: In `frontend/src/app/dashboard/chat/page.tsx`, pass the current message's tool calls to `ToolCallIndicator` during the loading phase (use a ref or state to track which tools are being executed)
- **MIRROR**: Follow existing `ToolCallIndicator` component usage
- **VALIDATE**: When sending a message, see animated tool execution indicators

### Task 9: Security Audit Pass
- **ACTION**: Review and fix security issues
- **IMPLEMENT**:
  1. Review all endpoints for proper auth middleware
  2. Verify no secrets are exposed in frontend code
  3. Add rate limiting to auth endpoints (use `slowapi` or similar)
  4. Verify CORS configuration is restrictive
  5. Add input validation on all POST/PATCH endpoints
  6. Review prompt injection protection in system prompt
- **MIRROR**: Follow existing patterns in `backend/app/auth/`
- **VALIDATE**: Manual security checklist review

### Task 10: Benchmark Suite
- **ACTION**: Create 100+ scheduling scenarios for testing
- **IMPLEMENT**:
  1. Create `backend/benchmarks/scenarios.json` with 100+ test cases across categories (basic, natural language, constraints, duration, multi-person, timezone, preferences, conflicts, ambiguity, destructive, adversarial)
  2. Create `backend/benchmarks/runner.py` - automated test runner that sends prompts to the agent and validates responses
  3. Create `backend/benchmarks/metrics.py` - tracks accuracy, latency, tool call counts
- **MIRROR**: Follow existing test patterns in `backend/tests/`
- **GOTCHA**: Cannot call Gemini API during benchmark development - use mock responses for structure, run real benchmarks manually
- **VALIDATE**: `python -m benchmarks.runner` runs without errors (with mocked LLM)

### Task 11: Documentation
- **ACTION**: Create comprehensive documentation
- **IMPLEMENT**:
  1. `README.md` - Project overview, features, architecture, setup, running, deployment
  2. `ARCHITECTURE.md` - System architecture diagram, component relationships
  3. `API.md` - All endpoints with request/response examples
  4. `DEPLOYMENT.md` - Step-by-step deployment guide
  5. `FREE_SERVICES.md` - All external dependencies and their free tier limits
- **MIRROR**: Follow standard documentation patterns
- **VALIDATE**: All links work, all endpoints documented

### Task 12: Deployment Preparation
- **ACTION**: Prepare for public deployment
- **IMPLEMENT**:
  1. Ensure all environment variables are documented in `.env.example`
  2. Verify frontend builds for production (`npm run build`)
  3. Verify backend starts cleanly without debug mode
  4. Add production-appropriate CORS settings
  5. Test health endpoint responds correctly
  6. Verify no hardcoded localhost URLs remain
- **VALIDATE**: Fresh clone + `npm install && npm run build` works

---

## Testing Strategy

### Unit Tests
- Existing: 20/20 passing (scheduling engine)
- Target: 30+ tests covering recurring appointments, new endpoints

### Integration Tests
- Existing: 20/25 passing (5 skipped)
- Target: 25/25 passing (implement missing endpoints)

### Manual Testing (DO NOT call Gemini API)
- User should manually test:
  1. Auth flow (register, login, logout)
  2. Chat with agent (test different prompts)
  3. Calendar view and appointment management
  4. Settings page (profile, preferences, working hours)
  5. Google Calendar sync
  6. Mobile responsiveness

### Edge Cases Checklist
- [ ] Empty input handling
- [ ] Maximum length messages
- [ ] Concurrent booking requests
- [ ] Timezone edge cases (DST transitions)
- [ ] Recurring appointment conflicts
- [ ] Google Calendar sync failures
- [ ] Network disconnection during chat

---

## Validation Commands

### Backend
```bash
cd backend
python -m pytest tests/ -v
```
EXPECT: All tests pass (25+ unit, 25 integration)

### Frontend
```bash
cd frontend
npm run build
npm run lint
```
EXPECT: Zero build errors, zero lint errors

### Manual Validation
- [ ] Register new user, login, logout
- [ ] Send chat messages to agent
- [ ] View calendar with appointments
- [ ] Create/edit/cancel appointments
- [ ] Update preferences and working hours
- [ ] Test on mobile viewport
- [ ] Verify no console errors

---

## Acceptance Criteria
- [ ] All 30+ completion checklist items from PROJECT_SPEC are checked
- [ ] All bugs fixed (hardcoded URLs, window global, duplicate endpoints)
- [ ] All tests passing (25+ unit, 25 integration)
- [ ] No TypeScript/build errors
- [ ] No hardcoded secrets or localhost URLs in frontend
- [ ] Recurring appointments work
- [ ] Documentation complete (README, ARCHITECTURE, API, DEPLOYMENT)
- [ ] Application builds for production
- [ ] No critical TODOs remain

## Completion Checklist
- [ ] Code follows discovered patterns
- [ ] Error handling matches codebase style
- [ ] Logging follows codebase conventions
- [ ] Tests follow test patterns
- [ ] No hardcoded values (except test fixtures)
- [ ] Documentation updated
- [ ] No unnecessary scope additions
- [ ] Self-contained implementation

## Risks
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Gemini free quota exhausted | High | Cannot test AI features | Manual user testing only; mock for benchmarks |
| Google Calendar OAuth complexity | Medium | Sync may break | Test with real Google account manually |
| Recurring appointment edge cases | Medium | Incorrect slot generation | Extensive unit tests for recurrence patterns |
| Deployment platform free tier limits | Low | App may sleep/have cold starts | Acceptable for competition |

## Notes
- **GEMINI QUOTA**: The free tier has 20 requests/day. Do NOT call the Gemini API during implementation. All AI testing must be done manually by the user.
- The backend uses synchronous SQLAlchemy (not async) despite `asyncpg` being in requirements - this is intentional and should not be changed.
- The `confirm_action` tool is currently a pass-through - this is acceptable as the confirmation flow is handled in the frontend UI.
- The `Calendar` and `AvailabilityRule` models exist but have no endpoints - this is acceptable as they're used internally by the scheduling engine.
