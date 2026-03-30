# Local Development Setup

## Prerequisites
- Python 3.11+
- Node.js 18+
- Git

## Step 1 — Clone and backend setup

```bash
git clone <your-repo>
cd bens-payment/backend

pip install -r requirements.txt

# Create your local env file
cp .env.example .env
```

## Step 2 — Fill in `.env`

Open `backend/.env` and set:

```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-supabase-anon-or-service-key

# Leave as-is for local dev — enables mock Swipey responses
SWIPEY_API_KEY=stub-local-dev
SWIPEY_API_URL=https://api.swipey.app

SECRET_KEY=any-random-32-char-string
APP_BASE_URL=http://localhost:8000
FRONTEND_URL=http://localhost:3000
ENVIRONMENT=development
```

> **Swipey mock mode**: Any `SWIPEY_API_KEY` starting with `stub` skips the real API and returns a mock success response. Full end-to-end flow works locally without the real key.

## Step 3 — Supabase schema

1. Go to your Supabase project → SQL Editor
2. Copy and run `docs/supabase_schema.sql`
3. Confirm tables: `users`, `contractors`, `timesheets`, `payments`, `notes`

## Step 4 — Create first admin user

Start the backend first, then run once:

```bash
curl -X POST http://localhost:8000/auth/setup-admin \
  -H "Content-Type: application/json" \
  -d '{"email": "hr@bens.com", "password": "yourpassword"}'
```

This endpoint auto-disables after first use (returns 400 if a user already exists).

## Step 5 — Start backend

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

API docs: http://localhost:8000/docs  
Health check: http://localhost:8000/health

## Step 6 — Start frontend

```bash
cd frontend
npm install

# Create frontend env
echo "VITE_API_URL=http://localhost:8000" > .env.local

npm run dev
```

App: http://localhost:3000

---

## Local test flow (no Swipey key needed)

1. Open http://localhost:3000/login → sign in as HR manager
2. **Manager**: Add a test contractor (name, phone, outlet, rate)
3. Copy the registration link shown in the table
4. Open the link in a **new tab or mobile browser**
5. Upload one of the test QR images from `/docs/test-qrs/` (or use the real ones from Phase 0)
6. Verify extracted bank + account → confirm name + IC
7. Open the timesheet link: http://localhost:3000/timesheet/`<token>`
8. Submit hours for current month
9. Back in manager dashboard → Timesheets tab → select → Bulk Approve
10. Confirm mock Swipey sync shows `synced` ✓

---

## File structure

```
bens-payment/
├── backend/
│   ├── app/
│   │   ├── api/          ← route handlers
│   │   ├── core/         ← config, auth, db client
│   │   ├── schemas/      ← pydantic models
│   │   ├── services/     ← qr_parser.py, swipey.py
│   │   └── main.py       ← FastAPI app + CORS
│   ├── requirements.txt
│   ├── Procfile          ← Railway deploy
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── pages/        ← LoginPage, ManagerDashboard, ContractorRegister, ContractorTimesheet
│   │   ├── hooks/        ← useAuth
│   │   └── services/     ← api.js (axios)
│   ├── package.json
│   └── railway.toml      ← Railway deploy
└── docs/
    └── supabase_schema.sql
```

---

## When Swipey API is ready

1. Update `SWIPEY_API_KEY` in `.env` with the real key (not starting with `stub`)
2. Update `SWIPEY_API_URL` if staging URL differs from prod
3. Confirm field names in `backend/app/services/swipey.py` → `payload` dict match Swipey's spec
4. Test with one real contractor before bulk run
