# Deploying TickrAI

Frontend → **Vercel**.  Backend + Postgres → **Railway**.  Total setup: ~30 min.

---

## 1 · Railway (backend + Postgres)

### 1.1 Create the project
1. Sign in at https://railway.app and **New Project → Deploy from GitHub repo → `jayadityak/valyu-us`**.
2. After the initial detect, Railway will create one service. Open it and:
   - **Settings → Service → Root Directory:** `backend`
   - **Settings → Service → Watch Paths:** `backend/**` (so frontend-only commits don't redeploy the API)
3. **Settings → Networking → Generate Domain** to get a public URL (e.g. `tickrai-production.up.railway.app`).

### 1.2 Add Postgres
1. In the same project: **+ New → Database → Add PostgreSQL**.
2. Railway auto-creates `DATABASE_URL` and exposes it as a reference variable.
3. In the **backend service → Variables**, add `DATABASE_URL = ${{Postgres.DATABASE_URL}}` so it stays in sync if Postgres is rotated.

### 1.3 Environment variables (backend service)

Set these in **Variables**:

| Variable | Value | Notes |
|---|---|---|
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` | Reference the Postgres plugin. |
| `OPENAI_API_KEY` | `sk-…` | Required for narrative LLM enhancement. |
| `OPENAI_MODEL` | `gpt-4o` | Default is fine. |
| `FMP_API_KEY` | `…` | Financial Modeling Prep Starter key. |
| `SEC_EDGAR_USER_AGENT` | `TickrAI you@email.com` | SEC requires a real contact. |
| `GOOGLE_CLIENT_ID` | `…apps.googleusercontent.com` | Same value as `VITE_GOOGLE_CLIENT_ID` on the frontend. |
| `GOOGLE_CLIENT_SECRET` | `…` | Backend-only. |
| `JWT_SECRET` | `<random 32+ char string>` | `openssl rand -hex 32` to generate. |
| `JWT_ALGORITHM` | `HS256` | Default. |
| `JWT_EXPIRY_DAYS` | `7` | Default. |
| `FRONTEND_URL` | `https://your-domain.com` | Primary frontend origin. |
| `CORS_EXTRA_ORIGINS` | `https://www.your-domain.com,https://tickrai.vercel.app` | Comma-separated. Vercel previews via `*.vercel.app` regex are already allowed. |
| `ENVIRONMENT` | `production` | Optional but recommended. |
| `FINNHUB_API_KEY` | `…` | Free at finnhub.io — required for Congress trading tab. |
| `ALERTS_STORE_PATH` | `/data/alerts.json` | Only if you mount a volume — see 1.4. |

### 1.4 (Optional) Persist price alerts across redeploys
Alerts are stored in a JSON file. Railway containers are ephemeral, so without a volume the file is wiped on each deploy.
1. Backend service → **Variables → + Volume → Mount path:** `/data`.
2. Set `ALERTS_STORE_PATH=/data/alerts.json`.

### 1.5 Deploy
Push to `main`. Railway auto-redeploys. Verify `https://<backend-url>/api/health` returns `{"status":"ok"}`.

---

## 2 · Vercel (frontend)

### 2.1 Create the project
1. Sign in at https://vercel.com and **Add New → Project → Import `jayadityak/valyu-us`**.
2. **Root Directory:** `frontend`.
3. Framework preset: **Vite** (auto-detected).
4. Build command: `npm run build` (default).
5. Output directory: `dist` (default).

### 2.2 Environment variables (Vercel project)

In **Settings → Environment Variables** (set for Production, Preview, Development):

| Variable | Value |
|---|---|
| `VITE_API_URL` | `https://<railway-backend-url>/api` (include `/api`, no trailing slash) |
| `VITE_GOOGLE_CLIENT_ID` | `…apps.googleusercontent.com` |

### 2.3 Deploy
Vercel auto-deploys on push to `main`. Each PR gets a preview URL — those URLs are already CORS-allowed by the backend's `*.vercel.app` regex.

---

## 3 · Custom domain

### 3.1 Vercel side (frontend)
1. **Vercel → Project → Settings → Domains → Add** `your-domain.com` and `www.your-domain.com`.
2. Vercel will print the required DNS records — usually:
   - `A` record on apex: `76.76.21.21`
   - `CNAME` on `www`: `cname.vercel-dns.com`
3. Add these at your DNS host (Cloudflare / Namecheap / etc.).
4. Wait for SSL provisioning (~1 min).

### 3.2 Railway side (backend — optional)
The backend doesn't need a custom domain (frontend talks to it directly), but if you want `api.your-domain.com`:
1. **Railway → Backend service → Settings → Networking → Custom Domain → Add** `api.your-domain.com`.
2. Add the printed `CNAME` to your DNS.
3. Update Vercel's `VITE_API_URL` to `https://api.your-domain.com/api`.

### 3.3 Update CORS
Once the domain is live, set on Railway:
```
FRONTEND_URL=https://your-domain.com
CORS_EXTRA_ORIGINS=https://www.your-domain.com
```
Restart the service if it doesn't pick up automatically.

### 3.4 Update Google OAuth
1. https://console.cloud.google.com → **APIs & Services → Credentials → OAuth 2.0 Client ID**.
2. **Authorized JavaScript origins:** add `https://your-domain.com`, `https://www.your-domain.com`, and the Vercel default URL.
3. **Authorized redirect URIs:** if your flow uses one, add the corresponding paths.

---

## 4 · Smoke test

After both services are live:
1. `curl https://<backend-url>/api/health` → `{"status":"ok"}`
2. Visit the frontend → search `AAPL` → report should generate in ~60s.
3. Sign in with Google → confirm session persists across refresh (validates `DATABASE_URL` + JWT).
4. Open the network tab — confirm requests go to the Railway backend, not localhost.

---

## 5 · Common gotchas

- **CORS error in browser console** → backend isn't allowing your origin. Add it to `CORS_EXTRA_ORIGINS` and restart.
- **`/api/...` returns 404 on Vercel** → `VITE_API_URL` isn't set; frontend is hitting Vercel itself. Set it in Vercel env vars and redeploy.
- **Google sign-in fails with `idpiframe_initialization_failed`** → origin not in the OAuth client's allowed list. Add it in Google Cloud Console.
- **Reports build but the AI narrative is generic** → `OPENAI_API_KEY` missing on Railway. The app falls back to the rules-based narrative; not a crash, just degraded quality.
- **FMP rate limit hit immediately** → `FMP_API_KEY` missing. App falls back to yfinance, which is slower and less detailed.
