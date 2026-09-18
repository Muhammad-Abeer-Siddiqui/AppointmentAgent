# AI Appointment Scheduling Agent

A production-quality AI-powered appointment scheduling agent with **$0 operating cost**. Built with FastAPI, Next.js, PostgreSQL, and Google Gemini.

## Live Demo

- **Frontend**: https://frontend-ecru-sigma-86.vercel.app
- **Backend API**: https://ai-scheduler-backend.fastapicloud.dev
- **API Docs**: https://ai-scheduler-backend.fastapicloud.dev/api/docs

## Features

- **AI Chat Agent** — Natural language scheduling via Google Gemini
- **Smart Slot Scoring** — Preference-aware ranking with lunch avoidance, morning preference, buffer time
- **Conflict Detection** — Real-time overlap detection with auto-suggested alternatives
- **Recurring Appointments** — Daily/weekly/monthly series with per-occurrence conflict handling
- **Multi-Person Scheduling** — Find common availability across multiple attendees
- **Timezone Support** — Full IANA timezone handling with DST awareness
- **Google Calendar Sync** — Bidirectional sync with Google Calendar
- **Visual Calendar** — Month grid and week view with appointment indicators
- **Dark Mode** — Full dark mode support across all pages

## Architecture

```
┌─────────────┐     ┌──────────────────────┐     ┌──────────────┐
│  Next.js     │────▶│  FastAPI Backend      │────▶│  PostgreSQL  │
│  Frontend    │     │  + AI Agent (Gemini)  │     │  (Supabase)  │
│  (Vercel)    │     │  (FastAPI Cloud)      │     │              │
└─────────────┘     └──────────────────────┘     └──────────────┘
```

- **Frontend**: Next.js 15, React 19, Tailwind CSS 4, TypeScript
- **Backend**: FastAPI, SQLAlchemy, Pydantic Settings v2
- **Database**: PostgreSQL via Supabase (free tier)
- **AI**: Google Gemini 1.5 Flash (free tier, 20 req/day)
- **Hosting**: Vercel (frontend) + FastAPI Cloud (backend) — all free tiers

## Getting Started

### Prerequisites
- Python 3.12+
- Node.js 18+
- PostgreSQL database

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements.txt

# Set environment variables
export DATABASE_URL="postgresql://..."
export JWT_SECRET_KEY="your-secret"
export GEMINI_API_KEY="your-key"

uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install

# Set environment variable
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local

npm run dev
```

### Running Tests

```bash
cd backend
python -m pytest tests/ -v              # Unit + integration tests
python -m pytest tests/benchmark/ -v    # 106 benchmark scenarios
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/auth/register` | POST | Register new user |
| `/auth/login` | POST | Login, get tokens |
| `/auth/refresh` | POST | Refresh access token |
| `/agent/chat` | POST | Chat with AI agent |
| `/agent/search-availability` | POST | Find available slots |
| `/agent/create-appointment` | POST | Book an appointment |
| `/agent/multi-person-availability` | POST | Multi-person scheduling |
| `/calendar/` | GET | List appointments |
| `/appointments/{id}` | GET | Get single appointment |
| `/appointments/{id}` | PATCH | Update appointment |
| `/appointments/{id}` | DELETE | Cancel appointment |
| `/appointments/series/{id}` | DELETE | Cancel recurring series |
| `/users/me` | GET/PATCH | User profile |
| `/users/working-hours` | GET/POST | Working hours |
| `/users/preferences` | GET/POST | Scheduling preferences |

## Benchmark Suite

106 automated test scenarios covering:
- Tool dispatcher (21 tests)
- Scheduling engine scoring (14 tests)
- Recurrence patterns (12 tests)
- Conflict detection (14 tests)
- Edge cases: timezone, overflow, off-days (12 tests)
- API contract validation (21 tests)
- Engine conflict detection (12 tests)

## Zero-Cost Stack

| Service | Free Tier | Purpose |
|---------|-----------|---------|
| Supabase | 500MB DB, 50K MAU | PostgreSQL database |
| FastAPI Cloud | 1 app | Backend hosting |
| Vercel | 100GB bandwidth | Frontend hosting |
| Google Gemini | 20 req/day | AI agent |

## License

MIT
