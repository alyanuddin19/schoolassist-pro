# SchoolAssist

**A Pakistan school-focused teacher assistant SaaS** — multi-tenant (individual teachers + schools), powered by the Qwen AI model from Alibaba Model Studio.

SchoolAssist helps teachers and school management generate worksheets and tests, import marksheets, analyse student performance, produce term reports, and get things done through a bilingual (English / Urdu / Roman Urdu) AI assistant that can actually control the dashboard.

> Built as a clean, school-focused product derived from the university-focused TeachAssist project. No HOD / CLO / semester / course terminology — everything speaks the language of Pakistani schools: classes, sections, subjects, terms, coordinators, principals.

---

## Tech Stack

| Layer      | Technology |
|------------|------------|
| Frontend   | Angular 16 (TypeScript, strict mode) |
| Backend    | FastAPI (Python 3.11+) |
| Database   | PostgreSQL (Supabase) — SQLite fallback for local dev |
| ORM        | SQLAlchemy |
| Auth       | FastAPI JWT (bearer tokens) |
| AI         | Alibaba Model Studio / Qwen (OpenAI-compatible API) |
| Voice      | Browser Web Speech API (SpeechRecognition + SpeechSynthesis) |
| Exports    | openpyxl (Excel), python-docx (DOCX), reportlab (PDF) |
| Hosting    | Frontend: Vercel · Backend: Render / Railway / Alibaba ECS |

## Features

1. **Teacher dashboard** — classes, subjects, students, recent work
2. **School admin dashboard** — staff, invites, teacher seats, billing
3. **Subject coordinator / principal dashboard** — class performance, weak students, final reports
4. **Setup** — classes, sections, subjects, students (single + bulk Excel import), teacher-subject assignments
5. **Worksheet generator** — MCQ / short / long questions, difficulty, language; with answer key + marking scheme
6. **Weekly / monthly / mid-term / final-term test generator** — smart defaults per test type
7. **Answer key & marking scheme generators** — included with every worksheet/test
8. **Marksheet upload/import** — Excel upload with roll-number matching and unmatched-row reporting
9. **Student-wise performance analysis** — subject-wise marks, percentages, grades
10. **Subject-wise class report** — averages, highest/lowest, pass rate
11. **Coordinator/principal final term report** — consolidated multi-subject report
12. **Exports** — PDF / DOCX (worksheets, tests, reports), XLSX / PDF (marksheets), XLSX (final reports)
13. **AI assistant** — text, image input, voice in/out, acts as a dashboard controller
14. **Multi-tenancy** — every school-owned table is scoped by `organization_id`
15. **Role-based access** — Individual Teacher, School Owner, Teacher, Subject Coordinator, Principal
16. **Seat-based school plans** — 25 / 30 / 50 / 100 teacher seats, enforced by the backend

## Repository Structure

```
schoolassist/
├── backend/          # FastAPI application
│   ├── app/
│   │   ├── core/         # config, security (JWT)
│   │   ├── routers/      # auth, organizations, dashboard, academics,
│   │   │                 # worksheets, tests, marksheets, reports, exports, chat
│   │   ├── services/     # Qwen client, generation, analytics, exports,
│   │   │                 # chat engine, AI action handlers, seed data
│   │   ├── main.py       # app entry point (table creation + plan seeding)
│   │   ├── models.py     # SQLAlchemy models (multi-tenant)
│   │   ├── schemas.py    # Pydantic request/response schemas
│   │   └── deps.py       # auth + organization context dependencies
│   ├── requirements.txt
│   └── .env.example
├── frontend/         # Angular 16 application
│   ├── src/app/
│   │   ├── components/   # login, signup, invite, AI assistant
│   │   ├── core/         # API service, auth, models, guards, voice
│   │   ├── layout/       # main layout (sidebar, topbar, org switcher)
│   │   └── pages/        # dashboards, setup, worksheets, tests,
│   │                     # marksheets, reports
│   └── src/environments/ # local + prod API URLs
└── README.md
```

---

## Quick Start (Local)

Runs immediately on a local SQLite database — no Supabase or Qwen key needed for the basic app (AI features need the Qwen key).

**Prerequisites:** Python 3.11+, Node.js 18+ (with npm).

### 1. Backend (http://localhost:8000)

```powershell
cd D:\schoolassist\backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env      # then edit values (see below)
uvicorn app.main:app --reload
```

API docs: http://localhost:8000/docs · Health: http://localhost:8000/api/health

On first start the backend creates all tables automatically and seeds the subscription plans (25 / 30 / 50 / 100 teacher seats).

### 2. Frontend (http://localhost:4200)

```powershell
cd D:\schoolassist\frontend
npm install
npm start
```

Sign up as an **Individual Teacher** (instant, one user) or as a **School / Organization** (pick a teacher-seat plan, then invite or create teacher accounts from the admin dashboard).

---

## Environment Variables (backend/.env)

Copy `backend/.env.example` to `backend/.env` and fill in:

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Production | PostgreSQL connection string. **Empty/omitted = local SQLite file** (`schoolassist.db`). |
| `JWT_SECRET_KEY` | Yes | Long random secret. Generate: `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `DASHSCOPE_API_KEY` | For AI | Qwen API key from Alibaba Model Studio. Without it, AI endpoints return a clear "not configured" error. |
| `QWEN_BASE_URL` | No | Defaults to `https://dashscope-intl.aliyuncs.com/compatible-mode/v1` |
| `QWEN_MODEL` | No | Defaults to `qwen-plus` |
| `ALLOWED_ORIGINS` | Yes | Comma-separated frontend origins, e.g. `http://localhost:4200` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | No | Token lifetime, default 1440 (24h) |

**Security rule: all secrets live only in the backend `.env`. The Angular app never contains API keys — it only calls your backend.**

---

## Connecting Supabase PostgreSQL

1. Create a project at [supabase.com](https://supabase.com) (free tier works).
2. Go to **Project Settings → Database → Connection string → URI** and copy it. Use the **direct connection / session pooler on port 5432** (not the serverless transaction pooler on 6543 — it is not compatible with SQLAlchemy sessions).
3. Replace `[YOUR-PASSWORD]` with your database password, and make sure the scheme is `postgresql://` (SQLAlchemy 1.4+ rejects `postgres://`).
4. Put it in `backend/.env`:

   ```env
   DATABASE_URL=postgresql://postgres.abcdefghijklm:YOUR-PASSWORD@aws-0-eu-central-1.pooler.supabase.com:5432/postgres
   ```

5. Restart the backend — all tables are created automatically on startup (MVP uses `Base.metadata.create_all`; switch to Alembic migrations when the schema starts evolving).

**Supabase notes:**
- Row Level Security is not used in the MVP; tenant isolation is enforced in the API layer (`organization_id` scoping on every query). If you expose the database key publicly later, enable RLS too.
- Supabase Storage (for worksheet/test files and images) is a planned next step — the export endpoints currently stream generated files directly from the API.

---

## Qwen API Setup (Alibaba Model Studio)

1. Create an account at [Alibaba Cloud Model Studio (International)](https://www.alibabacloud.com/product/modelstudio).
2. Open **API-KEY Management** and create an API key.
3. Add to `backend/.env`:

   ```env
   DASHSCOPE_API_KEY=sk-xxxxxxxxxxxxxxxx
   QWEN_BASE_URL=https://dashscope-intl.aliyuncs.com/compatible-mode/v1
   QWEN_MODEL=qwen-plus
   ```

4. Restart the backend. Verify with `GET /api/health` → `"qwen_configured": true`.

The backend uses the OpenAI-compatible chat/completions endpoint (`openai` Python SDK pointed at the DashScope base URL), so you can swap models (`qwen-plus`, `qwen-max`, `qwen-turbo`) or regional endpoints by changing env vars only.

---

## Roles & Signup Flow

| Role | What they can do |
|------|------------------|
| **Individual Teacher** | Own workspace: classes, students, worksheets, tests, marksheets, reports, AI assistant |
| **School Owner (Org Admin)** | Everything: staff, invites, seat plans, billing, academic setup, all reports |
| **Principal / Academic Head** | Academic management, all classes, final reports, exports |
| **Subject Coordinator** | Assigned classes/subjects: performance, weak students, final reports |
| **Teacher** | Their assigned classes/subjects: generate, import marks, reports |

**Signup flow:** choose *Individual Teacher* (immediate workspace) or *School/Organization* (school details + teacher-seat plan 25/30/50/100 → invite teachers by code or create accounts directly). The backend rejects new teacher accounts when the seat limit is reached.

**Payments (MVP):** plan selection and billing are mocked/sandboxed. The payments table and plan structure are ready for real Pakistani gateways later — Safepay, PayPro, JazzCash, or manual invoice approval.

---

## The AI Assistant

A floating assistant available on every page after login. It is a **dashboard controller**, not just a Q&A bot: it understands the logged-in user's role, organization, classes and subjects, and answers by executing **safe, permission-checked backend action handlers** — it never writes to the database on its own.

- **Languages:** English, Urdu (اردو), Roman Urdu
- **Voice input:** browser SpeechRecognition (mic button)
- **Voice output:** browser SpeechSynthesis (toggle on/off)
- **Image input:** attach a photo of a question paper and ask for an explanation

**Available actions:** `view_marksheet`, `open_student_report`, `generate_worksheet`, `generate_weekly_test`, `generate_monthly_test`, `show_class_performance`, `show_weak_students`, `create_final_report`, `invite_teacher`, `check_teacher_seat_limit`, `open_dashboard_page`.

Try:
- "Show me Class 8 Maths weekly test marksheet."
- "Generate a worksheet for Class 5 Science on digestion."
- "Show weak students in Class 9 Physics."
- "Open Ali Raza's subject-wise report."
- "Class 6 ka final term report banao." (Roman Urdu / Urdu)
- "Explain this uploaded question image in Urdu."

---

## Deployment

### Frontend → Vercel

1. Push the repository to GitHub/GitLab.
2. In Vercel: **Add New → Project**, import the repo.
3. Set **Root Directory** to `frontend` (Vercel auto-detects Angular: build `npm run build`, output `dist/schoolassist`).
4. Point the app at your deployed backend — edit `frontend/src/environments/environment.prod.ts`:

   ```typescript
   export const environment = {
     production: true,
     apiUrl: 'https://your-backend-host/api'
   };
   ```

5. Deploy, then add the Vercel domain (e.g. `https://schoolassist.vercel.app`) to backend `ALLOWED_ORIGINS`.

### Backend → Render

1. **New → Web Service**, connect the repo.
2. **Root Directory:** `backend` · **Runtime:** Python 3 · **Build:** `pip install -r requirements.txt` · **Start:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
3. Add environment variables: `DATABASE_URL` (Supabase), `JWT_SECRET_KEY`, `DASHSCOPE_API_KEY`, `ALLOWED_ORIGINS=https://your-frontend.vercel.app`.
4. Health check path: `/api/health`.

### Backend → Railway

New project → Deploy from repo → set Service Root Directory `backend`, start command `uvicorn app.main:app --host 0.0.0.0 --port $PORT`, add the same env vars.

### Backend → Alibaba ECS

```bash
# on the ECS instance (Ubuntu example)
sudo apt update && sudo apt install -y python3-pip python3-venv nginx
cd /opt/schoolassist/backend
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env && nano .env       # fill in real values
uvicorn app.main:app --host 127.0.0.1 --port 8000
# then reverse-proxy :80/:443 -> :8000 with nginx, or run uvicorn
# under systemd for auto-restart
```

---

## MVP Notes

- **Auth:** FastAPI JWT — access tokens only (no refresh tokens yet); swap in refresh tokens / SSO later if needed.
- **Migrations:** tables auto-create on startup; move to Alembic before changing models in production.
- **Storage:** generated files stream from the API; Supabase Storage integration is the next step.
- **Payments:** mocked; add Safepay / PayPro / JazzCash webhooks into the existing payments/plans tables.

## Local Scripts Cheat Sheet

```powershell
# Backend
cd D:\schoolassist\backend ; .\.venv\Scripts\activate ; uvicorn app.main:app --reload

# Frontend
cd D:\schoolassist\frontend ; npm start

# Production build (frontend) -> dist/schoolassist
cd D:\schoolassist\frontend ; npm run build
```
