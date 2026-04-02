# Railway Deployment

This is the easiest managed deployment path for NOVA if you do not want to run your own VPS.

## Recommended service layout

- Backend service: Docker image from `backend/Dockerfile`
- Frontend service: Railway Static Site, or a separate frontend service if you prefer full-container deployment
- Database: Railway Postgres

## 1. Create the Railway project

1. Sign in to Railway.
2. Create a new project.
3. Add a backend service from this repository.
4. Add a Postgres database.
5. Add a frontend service or Static Site.

If Railway is analyzing the repository root, it can now use the root `start.sh` and `railpack.json` files to build and start the backend.

## 2. Backend service settings

Preferred: use the backend Dockerfile.

Fallback: if Railway is set to build from the repo root, the new root `start.sh` and `railpack.json` will install backend Python dependencies and start Uvicorn.

Set these environment variables on the backend service:

- `DATABASE_URL` = value from Railway Postgres
- `OPERATIONAL_API_KEY`
- `API_AUTH_ENABLED=true`
- `ENGINE_DEFAULT_PROVIDER`
- `GROQ_API_KEY` and/or `ANTHROPIC_API_KEY`
- `REDDIT_CLIENT_ID` and `REDDIT_CLIENT_SECRET` if using Reddit
- `APIFY_API_TOKEN` if using Apify

The backend already listens on Railway's assigned `PORT`.

## 3. Frontend service settings

If you use a Railway Static Site:

- Build command: `npm ci && npm run build`
- Publish directory: `dist`
- Set build-time env var: `VITE_API_URL=https://<your-backend-service-domain>/api`

If you use a container-based frontend instead, make sure it serves on Railway's `PORT` and points to the backend URL.

## 4. Frontend env vars

Set:

- `VITE_API_URL` to your Railway backend public URL ending in `/api`
- `VITE_API_KEY` if you want the browser to send the API key automatically

## 5. Verify

After deployment, check:

- Frontend opens in the browser
- Backend health endpoint works
- Scrape and generate calls succeed

Example backend health check:

```bash
curl https://<your-backend-service-domain>/api/health
```

## 6. What Railway is best for here

- Easier than a VPS
- Better than Vercel for this backend
- Good if you want managed deploys plus Postgres

## 7. Updates

Push to GitHub, then redeploy the Railway services. The backend image and frontend build will update automatically if the services are linked to the repo.
