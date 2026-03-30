-- ============================================================
-- Ben's Contractor Payment - Supabase Schema
-- Run in Supabase SQL Editor
-- ============================================================

create extension if not exists "pgcrypto";

-- ── Users (managers / admins) ─────────────────────────────────────────────────
create table users (
  id uuid primary key default gen_random_uuid(),
  email text unique not null,
  password_hash text not null,
  name text not null,
  role text not null default 'manager' check (role in ('admin', 'manager')),
  is_active boolean default true,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

-- ── Contractors ───────────────────────────────────────────────────────────────
create table contractors (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  phone text not null,
  outlet text not null,
  hourly_rate numeric(10,2) not null check (hourly_rate > 0),
  status text not null default 'pending' check (status in ('pending', 'active', 'inactive', 'terminated')),

  -- DuitNow payment info (populated after QR upload)
  acquirer_id text,
  account_number text,
  bank_name text,
  ic_number text,

  -- Registration
  registration_token uuid unique not null default gen_random_uuid(),
  registered_at timestamptz,       -- set when contractor completes registration
  deactivated_at timestamptz,      -- set when deactivated
  created_by uuid references users(id),
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

-- Rule: active contractors must have payment details + IC
-- Enforced in app layer: contractors.py confirm endpoint

create index idx_contractors_outlet on contractors(outlet);
create index idx_contractors_status on contractors(status);
create index idx_contractors_token on contractors(registration_token);

-- ── Timesheets ────────────────────────────────────────────────────────────────
create table timesheets (
  id uuid primary key default gen_random_uuid(),
  contractor_id uuid not null references contractors(id),
  contractor_name text not null,     -- denormalised for display
  outlet text not null,              -- denormalised for filtering
  hourly_rate numeric(10,2) not null,

  year int not null,
  month int not null check (month between 1 and 12),

  -- hours must be non-negative
  week1_hours numeric(5,2) default 0 check (week1_hours >= 0),
  week2_hours numeric(5,2) default 0 check (week2_hours >= 0),
  week3_hours numeric(5,2) default 0 check (week3_hours >= 0),
  week4_hours numeric(5,2) default 0 check (week4_hours >= 0),
  total_hours numeric(6,2) generated always as (week1_hours + week2_hours + week3_hours + week4_hours) stored,
  amount numeric(10,2) not null,

  -- Business status (approval flow) — separate from sync status
  status text not null default 'submitted' check (status in ('submitted', 'approved', 'rejected')),
  rejection_reason text,

  -- Sync status (Swipey payment pipeline) — separate from business status
  sync_status text default 'pending' check (sync_status in ('pending', 'syncing', 'synced', 'failed')),

  -- Timestamps for observability
  submitted_at timestamptz,
  approved_at timestamptz,
  synced_at timestamptz,
  approved_by uuid references users(id),

  created_at timestamptz default now(),
  updated_at timestamptz default now(),

  -- One timesheet per contractor per month
  unique(contractor_id, year, month)
);

create index idx_timesheets_contractor on timesheets(contractor_id);
create index idx_timesheets_outlet on timesheets(outlet);
create index idx_timesheets_status on timesheets(status);
create index idx_timesheets_month_year on timesheets(year, month);

-- ── Payments ──────────────────────────────────────────────────────────────────
-- Represents each sync attempt to Swipey. Inserted BEFORE the attempt.
create table payments (
  id uuid primary key default gen_random_uuid(),
  timesheet_id uuid not null references timesheets(id),
  contractor_id uuid not null references contractors(id),
  contractor_name text not null,
  invoice_number text unique not null,
  amount numeric(10,2) not null,
  sync_status text not null default 'pending' check (sync_status in ('pending', 'syncing', 'synced', 'failed')),
  retry_count int default 0,
  swipey_reference text,
  error_message text,
  attempted_at timestamptz,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create index idx_payments_timesheet on payments(timesheet_id);
create index idx_payments_sync_status on payments(sync_status);

-- ── Notes ─────────────────────────────────────────────────────────────────────
create table notes (
  id uuid primary key default gen_random_uuid(),
  contractor_id uuid not null references contractors(id),
  content text not null,
  visibility text not null default 'internal' check (visibility in ('internal', 'external')),
  created_by uuid references users(id),
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create index idx_notes_contractor on notes(contractor_id);

-- ── updated_at trigger ────────────────────────────────────────────────────────
create or replace function update_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

create trigger trg_users_updated_at before update on users for each row execute function update_updated_at();
create trigger trg_contractors_updated_at before update on contractors for each row execute function update_updated_at();
create trigger trg_timesheets_updated_at before update on timesheets for each row execute function update_updated_at();
create trigger trg_payments_updated_at before update on payments for each row execute function update_updated_at();
create trigger trg_notes_updated_at before update on notes for each row execute function update_updated_at();

-- ── Migration: Day-level timesheet tracking ────────────────────────────────────
create table if not exists timesheet_days (
  id uuid primary key default gen_random_uuid(),
  contractor_id uuid not null references contractors(id),
  year int not null,
  month int not null check (month between 1 and 12),
  day int not null check (day between 1 and 31),
  hours numeric(4,2) not null check (hours > 0),
  outlet text not null,
  status text not null default 'submitted'
    check (status in ('submitted', 'approved', 'rejected')),
  rejection_reason text,
  created_at timestamptz default now(),
  updated_at timestamptz default now(),
  unique(contractor_id, year, month, day)
);

create index if not exists idx_timesheet_days_period on timesheet_days(contractor_id, year, month);

create table if not exists timesheet_day_logs (
  id uuid primary key default gen_random_uuid(),
  contractor_id uuid not null references contractors(id),
  year int not null,
  month int not null,
  day int not null,
  event text not null check (event in ('submitted', 'rejected', 'resubmitted')),
  hours numeric(4,2),
  outlet text,
  rejection_reason text,
  actor_id uuid references users(id),
  created_at timestamptz default now()
);

create index if not exists idx_timesheet_day_logs_period on timesheet_day_logs(contractor_id, year, month);

create trigger trg_timesheet_days_updated_at before update on timesheet_days
  for each row execute function update_updated_at();

-- Migration: per-day hourly rate override (admin can set a different rate per day, e.g. public holidays)
alter table timesheet_days add column if not exists hourly_rate numeric(10,2);
-- null = use contractor default rate; a value = admin override for this specific day

-- Migration: submission_id groups all day log rows from a single submit call together
-- Allows per-submission history view for contractors (multiple submissions per month)
alter table timesheet_day_logs add column if not exists submission_id uuid;
alter table timesheets add column if not exists approved_by uuid references users(id);

-- Migration: allow multiple timesheets per contractor/month (post-approval resubmissions)
-- Each approval creates a distinct timesheet record with its own sequence number
alter table timesheets drop constraint if exists timesheets_contractor_id_year_month_key;
alter table timesheets add column if not exists sequence int not null default 1;

-- Link day entries to their specific timesheet submission
alter table timesheet_days add column if not exists timesheet_id uuid references timesheets(id);
alter table timesheet_day_logs add column if not exists timesheet_id uuid references timesheets(id);

-- Migration: store QR image path
alter table contractors add column if not exists qr_image_path text;

-- Migration: add attempted_at to payments (missing from initial deploy)
alter table payments add column if not exists attempted_at timestamptz;

-- Migration: update payments sync_status check to include 'syncing' state
alter table payments drop constraint if exists payments_sync_status_check;
alter table payments add constraint payments_sync_status_check
  check (sync_status in ('pending', 'syncing', 'synced', 'failed'));

-- Migration: update timesheets sync_status check to include 'syncing' state
alter table timesheets drop constraint if exists timesheets_sync_status_check;
alter table timesheets add constraint timesheets_sync_status_check
  check (sync_status in ('pending', 'syncing', 'synced', 'failed'));
