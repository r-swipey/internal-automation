# Production Deployment Checklist
# Ben's Contractor Payment System

Deploy order: Supabase → Railway Backend → Railway Frontend → First-run setup

---

## STEP 1 — Supabase: Run Schema Migration

In Supabase Dashboard → SQL Editor, run:

```sql
-- Add QR image storage path column (safe to run even if already run)
alter table contractors add column if not exists qr_image_path text;
```

Verify it ran: go to Table Editor → contractors → check `qr_image_path` column exists.

---

## STEP 2 — Supabase: Confirm Storage Bucket

In Supabase Dashboard → Storage:
- Confirm bucket `contractor-qr-images` exists
- Bucket should be **Private** (not public) — signed URLs are used by the backend
- No extra policies needed — backend uses the service role key

---

## STEP 3 — Railway: Deploy Backend

### 3.1 Create the service
- New Project → Deploy from GitHub repo → select `bens-payment/backend` as root directory
- Railway will detect the `Procfile` automatically

### 3.2 Set environment variables
In Railway → Backend service → Variables, add all of these:

| Variable | Value |
|---|---|
| `SUPABASE_URL` | `https://xvqfjtkngjacrsyhkuer.supabase.co` |
| `SUPABASE_KEY` | *(service role key from your .env)* |
| `SECRET_KEY` | *(generate: run `openssl rand -hex 32` in terminal)* |
| `SWIPEY_API_URL` | `https://api.swipey.app` |
| `SWIPEY_API_KEY` | `stub-production` *(keep stub- prefix until real key arrives)* |
| `ENVIRONMENT` | `production` |
| `FRONTEND_URL` | *(Railway frontend URL — add after Step 4, see note below)* |
| `APP_BASE_URL` | *(Railway backend URL — set after first deploy)* |

> **Note on FRONTEND_URL**: You need this for CORS. After the frontend is deployed in Step 4, come back and set this to the Railway frontend URL (e.g. `https://bens-payment-frontend.up.railway.app`). Then redeploy the backend.

### 3.3 Verify backend is live
Hit: `https://<your-backend-url>/health`
Expected: `{"status": "ok", "service": "bens-contractor-payment"}`

---

## STEP 4 — Railway: Deploy Frontend

### 4.1 Create the service
- Add service → GitHub repo → set root directory to `bens-payment/frontend`
- Railway uses `railway.toml` — build and start commands are already configured

### 4.2 Set environment variables
| Variable | Value |
|---|---|
| `VITE_API_URL` | *(Railway backend URL from Step 3, e.g. `https://bens-payment-backend.up.railway.app`)* |

> **Critical**: `VITE_API_URL` is baked into the frontend at build time. Set this variable BEFORE the first build triggers, or redeploy after setting it.

### 4.3 Verify frontend is live
Open the Railway frontend URL — you should see the login page.

---

## STEP 5 — Back to Step 3: Update FRONTEND_URL

Now that you have the frontend URL, go back to the backend Railway service:
- Set `FRONTEND_URL` = `https://<your-frontend-url>.up.railway.app`
- Trigger a redeploy (Railway → backend → Redeploy)

This fixes CORS so the frontend can talk to the backend.

---

## STEP 6 — First-Run: Create Admin User

Run this once only — creates the first HR admin account:

```bash
curl -X POST https://<your-backend-url>/auth/setup-admin \
  -H "Content-Type: application/json" \
  -d '{"email": "hr@bens.com", "password": "YourStrongPassword", "name": "HR Admin"}'
```

Or use any REST client (Postman, Insomnia, etc.)

> This endpoint is one-time only — it will refuse to create a second admin.

---

## STEP 7 — Smoke Test

Run through this checklist to confirm everything works end-to-end:

- [ ] `/health` returns `ok`
- [ ] Login at `/login` with the admin credentials
- [ ] Contractors tab loads (empty is fine)
- [ ] Add a test contractor — confirm registration link copies correctly
- [ ] Open the registration link in a new browser tab (no login)
- [ ] Upload one of the test QR images from `docs/test-qrs/` — confirm bank details parse
- [ ] Complete registration with a test IC number (e.g. `900101-14-1234`)
- [ ] Open the timesheet link — confirm it loads
- [ ] Submit a timesheet with 1 day of hours
- [ ] Back in dashboard → Timesheets → confirm it appears
- [ ] Approve the timesheet
- [ ] Confirm sync_status = `synced` (mock mode — no real payment)
- [ ] Click the contractor row → confirm detail panel opens with QR image

---

## STEP 8 — Share with End Users

Once smoke test passes, distribute:

| Who | What to send |
|---|---|
| HR Admin | Login URL + email/password |
| Site Managers | Login URL + their email/password (create via Users tab) |
| Contractors | Their unique registration link (copy from 🪪 icon) |
| Contractors | Their timesheet link (copy from 🕐 icon) — after they register |

---

## Environment Variables — Complete Reference

### Backend (Railway)
```
SUPABASE_URL=https://xvqfjtkngjacrsyhkuer.supabase.co
SUPABASE_KEY=<service role key>
SECRET_KEY=<32+ char random string>
SWIPEY_API_URL=https://api.swipey.app
SWIPEY_API_KEY=stub-production
ENVIRONMENT=production
FRONTEND_URL=https://<frontend>.up.railway.app
APP_BASE_URL=https://<backend>.up.railway.app
```

### Frontend (Railway)
```
VITE_API_URL=https://<backend>.up.railway.app
```

---

## When the Real Swipey API Key Arrives

1. In Railway backend Variables: update `SWIPEY_API_KEY` from `stub-production` to the real key
2. Update `SWIPEY_API_URL` if Swipey provides a different endpoint
3. Confirm payload fields with Swipey team (`beneficiary_name`, `duitnow_acquirer_id`, `duitnow_account_number`, `amount`, `invoice_number`) and update `backend/app/services/swipey.py` if needed
4. Redeploy backend
5. Run a single test bulk-approve with 1 contractor before doing the full ~80 run

---

## Known Limitations at Launch (for user testing feedback)

- Swipey sync is mocked — no real payments processed yet
- Public Bank QR codes will show as "Unknown" — flag any contractors using Public Bank
- No email/SMS notifications — all link sharing is manual
- No bulk export or reporting — payment history is per-contractor only
