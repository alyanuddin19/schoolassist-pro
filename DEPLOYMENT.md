# SchoolAssist — Deployment & Team Guide

Complete guide for deploying SchoolAssist to production and working on it as a team.

```
   Teachers' browsers
          │
          ▼
   Vercel (frontend)          github.com/<you>/schoolassist  ← all code, all team members
   schoolassist.vercel.app            │  (push / PR merge triggers auto-deploy)
          │  /api/* proxied            ├──────────────► Vercel  : builds frontend/
          ▼                             │                          (Angular, Node 20)
   Render (backend)                     └──────────────► Render   : builds backend/
   schoolassist-api.onrender.com                     (FastAPI, Python 3.11)
          │
          ▼
   Supabase (PostgreSQL database — all school data)
```

All three services have **free tiers** and none require a credit card for this setup.

---

## 1. One-time production deployment (owner)

Everything below assumes you already pushed this repo to GitHub.

### Step A — Supabase: create the database (2 min)

1. Go to [supabase.com/dashboard](https://supabase.com/dashboard) → **New project**
2. Name: `schoolassist` · Region: **Southeast Asia (Singapore)** · Set a strong **database password** and save it
3. When ready, open **Project Settings → Database → Connection string → URI → Session pooler** and copy it.
   It looks like:
   `postgresql://postgres.abcdefghij:[YOUR-PASSWORD]@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres`
4. Replace `[YOUR-PASSWORD]` with your real password and append `?sslmode=require` at the end.

> Where do the tables come from? **You don't create any.** On the backend's first boot it
> runs `Base.metadata.create_all()` — every table (users, organizations, classes,
> worksheets, …) is created automatically, and the 4 subscription plans are seeded.
> The first account you sign up also gets Class 1–8 + default subjects automatically.
> View data anytime in Supabase Dashboard → **Table Editor** or run SQL in **SQL Editor**.

### Step B — Render: deploy the backend (3 min)

1. Go to [dashboard.render.com](https://dashboard.render.com) → **New + → Blueprint**
2. Select this GitHub repository. Render reads `render.yaml` at the repo root.
3. It will ask for 3 secret values — they are stored **only in Render**, never in the repo:

| Secret | Value |
|---|---|
| `DATABASE_URL` | the Supabase URI from Step A |
| `JWT_SECRET_KEY` | a long random string: run `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `DASHSCOPE_API_KEY` | your Groq API key (`gsk_...`) from [console.groq.com/keys](https://console.groq.com/keys) |

4. Click **Apply**. Wait ~3 min for the build.
5. Verify: open `https://schoolassist-api.onrender.com/api/health` — it must show
   `"database": "postgres"`. If it says `"sqlite"`, the `DATABASE_URL` secret is missing/wrong.

### Step C — Vercel: deploy the frontend (3 min)

1. Edit `frontend/vercel.json` and replace `PASTE-YOUR-RENDER-URL` with your Render URL
   from Step B (e.g. `https://schoolassist-api.onrender.com`). Commit + push.
2. Go to [vercel.com/new](https://vercel.com/new) → import the GitHub repo
3. **Root Directory: `frontend`** (everything else auto-detects: Angular, `npm run build`)
4. Deploy. You get `https://<your-app>.vercel.app`.
5. Copy that URL.

### Step D — Connect the three (2 min)

1. **Render → Environment**: set `ALLOWED_ORIGINS` to
   `https://<your-app>.vercel.app,http://localhost:4200` (comma-separated) → Save (auto redeploys)
2. **GitHub → Settings → Secrets and variables → Actions → Variables**: add
   `RENDER_BACKEND_URL = https://schoolassist-api.onrender.com` — this activates the
   keep-warm workflow (free Render sleeps after 15 min; the workflow pings it during
   Pakistani school hours).

### Step E — Verify

- Open your Vercel URL → sign up → create a worksheet from the AI assistant.
- If the first request after ~15 min idle takes 30–60 s, that's a Render cold start (normal on free).

---

## 2. Team setup (owner does once)

1. **GitHub repo → Settings → Collaborators → Add people** — invite teammates with **Write** access.
2. (Recommended) **Settings → Branches → Add branch protection rule** for `main`:
   require a pull request before merging. This keeps broken code off production.
3. Every member installs: [Node.js 20+](https://nodejs.org), Python 3.11+, and
   [Qoder](https://qoder.com) (or any editor). That's all — no accounts on
   Vercel/Render/Supabase are needed for developers, because **production secrets
   live only in the service dashboards**, never in the repo.

## 3. Team member — local development (first time)

```powershell
git clone https://github.com/<owner>/schoolassist.git
cd schoolassist

# Backend
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
copy .env.example .env        # works instantly with SQLite; add your own Groq key for AI
.venv\Scripts\python -m uvicorn app.main:app --reload

# Frontend (new terminal)
cd frontend
npm install
npm start                     # http://localhost:4200
```

Local dev uses SQLite automatically (`schoolassist.db`) — nobody can break the
production database while developing.

## 4. Daily team workflow

```
git checkout main && git pull
git checkout -b feature/<short-name>     # e.g. feature/urdu-worksheets
# ...code (use Qoder AI freely)...
git add -A && git commit -m "Add Urdu worksheet option"
git push -u origin feature/<short-name>
# GitHub → open Pull Request → teammate reviews → Merge
```

**Merging to `main` auto-deploys everything** (Render backend + Vercel frontend),
typically within 2–3 minutes. No one deploys by hand.

> **Vercel Hobby rule — who can trigger the frontend deploy:** the free Hobby plan
> only auto-deploys commits **authored by the Vercel account owner's email**.
> Commits from other authors are silently skipped by Vercel (the deployment shows
> as *Blocked*); the Render backend deploys regardless of author. Therefore:
>
> - The owner's machine is already configured (repo-local `git config user.email`
>  is set to the Vercel account email — check with `git config user.email`).
> - **The owner merges PRs** using **"Create a merge commit"** on GitHub — the merge
>  commit is authored by the owner, so the frontend deploys.
> - Avoid **"Squash and merge"** by members: the squashed commit keeps the member's
>  authorship and the frontend deploy will be skipped. If that happens, the owner
>  just runs `git commit --allow-empty -m "redeploy" && git push`.
> - Members' branch pushes don't get Vercel preview links on Hobby — preview
>  locally with `npm start` instead. (Upgrading to Vercel Pro removes all of these
>  limits and allows real team deployments.)

## 5. Troubleshooting

| Symptom | Cause & fix |
|---|---|
| Frontend says "Cannot reach the SchoolAssist backend" | Backend down or wrong URL in `frontend/vercel.json`. Check the Render dashboard and the rewrite destination. |
| First request slow (~30–60 s) | Render free-tier cold start. The keep-warm workflow reduces this; it needs `RENDER_BACKEND_URL` set in GitHub Actions variables. |
| `/api/health` shows `"database": "sqlite"` | `DATABASE_URL` missing in Render → data would be lost on redeploy. Fix the env var immediately. |
| Browser console shows CORS errors | `ALLOWED_ORIGINS` on Render doesn't include your Vercel URL. |
| 401 for everyone after a redeploy | `JWT_SECRET_KEY` was changed — all tokens invalidate; users just log in again. |
| AI assistant "not configured" | `DASHSCOPE_API_KEY` missing in Render, or the Groq key is invalid/out of quota. |
| Frontend didn't update after a push (Vercel shows *Blocked*) | Vercel Hobby only deploys commits authored by the account owner's email. Check `git log -1 --format="%ae"` — if it's not the owner's email, merge as the owner or push an empty commit from the owner's machine. |
