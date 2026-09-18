# Deployment Guide

## Current Production Deployment

| Service | URL | Platform |
|---------|-----|----------|
| Frontend | https://frontend-ecru-sigma-86.vercel.app | Vercel |
| Backend | https://ai-scheduler-backend.fastapicloud.dev | FastAPI Cloud |
| Database | Supabase (ap-northeast-1) | PostgreSQL |

## Architecture

```
GitHub → Vercel (frontend build + deploy)
       → FastAPI Cloud (backend deploy)
       → Supabase (PostgreSQL)
```

## Deploying Updates

### Frontend (Vercel)

```bash
cd frontend
vercel --prod
```

Or push to GitHub — Vercel auto-deploys from the `master` branch.

### Backend (FastAPI Cloud)

```bash
cd backend
fastapi deploy
```

Or push to GitHub — FastAPI Cloud auto-deploys from the `master` branch.

## Environment Variables

### Backend (FastAPI Cloud)

| Variable | Value |
|----------|-------|
| `DATABASE_URL` | `postgresql://postgres.[ref]:[pass]@aws-0-ap-northeast-1.pooler.supabase.com:5432/postgres` |
| `JWT_SECRET_KEY` | Random 32+ char string |
| `GEMINI_API_KEY` | Google AI Studio API key |
| `GEMINI_MODEL` | `gemini-1.5-flash` |
| `ENVIRONMENT` | `production` |
| `FRONTEND_URL` | `https://frontend-ecru-sigma-86.vercel.app` |
| `GOOGLE_REDIRECT_URI` | `https://ai-scheduler-backend.fastapicloud.dev/auth/google/callback` |
| `ALLOWED_ORIGINS` | Ignored — hardcoded in `config.py` |

### Frontend (Vercel)

| Variable | Value |
|----------|-------|
| `NEXT_PUBLIC_API_URL` | `https://ai-scheduler-backend.fastapicloud.dev` |

## Google OAuth Setup

1. Go to https://console.cloud.google.com
2. Navigate to APIs & Services > Credentials
3. Update OAuth 2.0 Client ID:
   - Add `https://frontend-ecru-sigma-86.vercel.app` to Authorized JavaScript origins
   - Add `https://ai-scheduler-backend.fastapicloud.dev/auth/google/callback` to Authorized redirect URIs

## Troubleshooting

### CORS Errors
- Check that `allowed_origins_list` in `backend/app/core/config.py` includes your frontend URL
- Include `https://` and no trailing slash

### Database Connection Errors
- Ensure `DATABASE_URL` uses port `5432` (not `6543`)
- Check Supabase dashboard for database status

### Google OAuth Errors
- Ensure redirect URI in Google Console matches the backend URL exactly
- Check that the callback endpoint is `/auth/google/callback`
