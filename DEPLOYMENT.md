# Deployment Guide

## Prerequisites

1. GitHub account
2. Supabase account (free) - https://supabase.com
3. Render account (free) - https://render.com
4. Vercel account (free) - https://vercel.com

## Step 1: Create Database (Supabase)

1. Go to https://supabase.com and create a new project
2. Note your **Project URL** and **anon key**
3. Go to Settings > Database and copy the **Connection string** (URI format)
   - It looks like: `postgresql://postgres.[ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres`
4. Update the connection string to use port `5432` instead of `6543` for direct connections

## Step 2: Push to GitHub

```bash
cd "D:\Coding\appointment scheduling agent"
git init
git add .
git commit -m "Initial commit: AI Appointment Scheduling Agent"
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

**IMPORTANT:** Make sure `backend/.env` is in `.gitignore` (it should be already).

## Step 3: Deploy Backend (Render)

1. Go to https://render.com and sign in with GitHub
2. Click **New +** > **Web Service**
3. Connect your GitHub repository
4. Configure:
   - **Name:** `ai-scheduler-backend`
   - **Region:** US East (or closest to you)
   - **Runtime:** Python 3
   - **Build Command:** `cd backend && pip install -r requirements.txt`
   - **Start Command:** `cd backend && gunicorn app.main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT --timeout 120`
   - **Plan:** Free

5. Add environment variables (copy from `backend/.env` but update values):

   | Variable | Value |
   |----------|-------|
   | `DATABASE_URL` | Your Supabase connection string (from Step 1) |
   | `JWT_SECRET_KEY` | Generate a new random string (min 32 chars) |
   | `GEMINI_API_KEY` | Your Gemini API key |
   | `GEMINI_MODEL` | `gemini-1.5-flash` |
   | `FRONTEND_URL` | Will be set after Vercel deploy (see Step 4) |
   | `ALLOWED_ORIGINS` | `["https://YOUR-PROJECT.vercel.app"]` |
   | `GOOGLE_CLIENT_ID` | Your Google OAuth client ID |
   | `GOOGLE_CLIENT_SECRET` | Your Google OAuth client secret |
   | `GOOGLE_REDIRECT_URI` | `https://YOUR-PROJECT.onrender.com/auth/google/callback` |
   | `DEBUG` | `false` |
   | `ENVIRONMENT` | `production` |

6. Click **Create Web Service**
7. Wait for deploy to complete
8. Note your backend URL: `https://YOUR-PROJECT.onrender.com`

## Step 4: Deploy Frontend (Vercel)

1. Go to https://vercel.com and sign in with GitHub
2. Click **Import Project** and select your repository
3. Configure:
   - **Framework Preset:** Next.js
   - **Root Directory:** `frontend`
   - **Build Command:** `npm run build`
   - **Output Directory:** `.next`

4. Add environment variables:

   | Variable | Value |
   |----------|-------|
   | `NEXT_PUBLIC_API_URL` | Your Render backend URL (from Step 3) |

5. Click **Deploy**
6. Wait for deploy to complete
7. Note your frontend URL: `https://YOUR-PROJECT.vercel.app`

## Step 5: Finalize Configuration

1. **Update Render env vars:**
   - Go to your Render service > Environment
   - Set `FRONTEND_URL` to your Vercel URL: `https://YOUR-PROJECT.vercel.app`
   - Set `ALLOWED_ORIGINS` to: `["https://YOUR-PROJECT.vercel.app"]`

2. **Update Google OAuth:**
   - Go to https://console.cloud.google.com
   - Navigate to APIs & Services > Credentials
   - Update your OAuth 2.0 Client ID:
     - Add `https://YOUR-PROJECT.vercel.app` to Authorized JavaScript origins
     - Add `https://YOUR-PROJECT.onrender.com/auth/google/callback` to Authorized redirect URIs

3. **Trigger a redeploy on Render** to pick up the new env vars

## Step 6: Verify

1. Visit your Vercel URL: `https://YOUR-PROJECT.vercel.app`
2. Register a new account
3. Test the AI chat
4. Test creating an appointment
5. Check the calendar view

## Troubleshooting

### CORS Errors
- Make sure `ALLOWED_ORIGINS` on Render matches your Vercel URL exactly
- Include `https://` and no trailing slash

### Database Connection Errors
- Make sure `DATABASE_URL` uses port `5432` (not `6543`)
- Make sure the Supabase database is running

### Google OAuth Errors
- Make sure `GOOGLE_REDIRECT_URI` on Render matches your backend URL
- Make sure Google Cloud Console has the correct authorized origins and redirect URIs

### Build Failures on Render
- Check the build logs for missing dependencies
- Make sure `requirements.txt` is in the `backend/` directory
- Make sure the build command includes `cd backend &&`
