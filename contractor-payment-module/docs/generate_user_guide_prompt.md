# AI Prompt — Generate User Guide & Constraints Document
# Ben's Contractor Payment System (Cloud Kitchen × Swipey)

Paste the prompt below into Claude chat to generate the full work document.

---

## PROMPT (copy everything below this line)

---

You are a technical writer producing a professional internal work document for **Ben's Cloud Kitchen × Swipey — Contractor Payment System**. The audience is HR staff (admin/manager) and food-court contractors (non-technical).

Produce a complete, well-structured document with the following sections. Use clear headings, tables where appropriate, and plain language for the contractor sections.

---

## SECTION 1 — SYSTEM OVERVIEW

Write a 1-page executive summary covering:
- What this system replaces (manual process: HR scanning ~80 TNG QR codes one-by-one in Swipey, ~2.5 hours per run)
- What the new flow is: contractors self-register via QR upload → submit monthly timesheets → HR bulk-approves → auto-syncs to Swipey Bill Payment API
- Who uses it and in what capacity (Admin/HR, Site Manager, Contractor)
- Current status: live, mock Swipey mode active until API key arrives from Swipey team

---

## SECTION 2 — USER ROLES & PERMISSIONS

Document the three roles in a table with columns: Role | Who Holds It | What They Can Do | What They Cannot Do

**Admin / HR**
- Full system access
- Add, deactivate, reactivate contractors
- Approve, reject, and bulk-approve timesheets
- Sync payments to Swipey Bill Payment API
- Edit custom hourly rate per day (e.g. public holidays)
- Create and manage user accounts (managers/admins)
- View contractor detail panel including stored QR image
- Write internal and external notes on contractors

**Site Manager**
- Review timesheet day-by-day breakdown
- Approve or reject individual timesheets (with written reason required for rejection)
- Edit contractor details (name, phone, outlet, hourly rate)
- Write internal and external notes on contractors
- Copy registration and timesheet links
- Cannot: bulk-approve or sync to Swipey, edit custom day rates, manage user accounts

**Contractor**
- No login — accessed via a unique token link (UUID in URL)
- Complete self-registration: upload DuitNow QR → verify bank details → enter IC number
- Submit monthly timesheet (day-by-day hours)
- View submission history and payment status
- View external notes posted by HR

---

## SECTION 3 — ADMIN & MANAGER USER GUIDE

### 3.1 Logging In
- URL: the system login page
- Enter email and password (credentials set by Admin)
- On success: redirected to the Manager Dashboard with tabs: Contractors | Timesheets | Users (admin only)

### 3.2 Contractors Tab

#### Adding a Contractor
Steps: click "+ Add Contractor" → fill form → Create
Required fields: Full Name, Phone number, Outlet, Hourly Rate (RM)

Constraints:
- Phone number must be unique across all contractors. The system will block a duplicate with the name of the existing contractor.
- Hourly rate must be greater than RM 0.00
- Outlet must be selected from the configured outlet list

What happens next: system generates a unique registration link (token-based). Copy it via the 🪪 icon and send it to the contractor (WhatsApp, SMS, etc.)

#### Contractor Statuses (explained in plain terms)
| Status | Meaning |
|---|---|
| pending | Created, awaiting contractor to complete QR registration |
| active | Fully registered — can submit timesheets |
| inactive | Deactivated by HR. Cannot submit timesheets. Can be reactivated. |
| terminated | Permanently closed. Registration link disabled. Cannot be reactivated. |

#### Contractor Detail Panel
Click any contractor row to open the detail panel (slides in from the right). Shows:
- Identity: name, phone, IC number, outlet, status
- Payment details: bank name, masked account number
- Registration date
- Stored QR image (the image the contractor uploaded during registration)
- Quick links: copy registration link, copy timesheet link
- Actions: Deactivate or Re-activate

#### Deactivating a Contractor
Click the contractor row → Deactivate button in panel, or use the Deactivate button in the table row.
Effect: status → inactive. Registration link disabled. Timesheet link disabled.

#### Reactivating a Contractor
Click Re-activate on an inactive contractor.
Effect: status → pending. The contractor must open their registration link again and re-confirm their IC. Their previously uploaded QR bank details are retained — they do NOT need to re-upload the QR image. If their bank details have changed, they can upload a new QR from the registration page.

### 3.3 Timesheets Tab

#### Filters
Filter by: Month, Year, Approval Status (submitted / approved / rejected), Sync Status (pending / syncing / synced / failed)

#### Timesheet Statuses
| Status | Meaning |
|---|---|
| submitted | Contractor submitted hours, awaiting HR review |
| approved | HR approved — payment queued or processed |
| rejected | HR rejected — contractor notified to resubmit |

#### Sync Statuses (Swipey payment pipeline)
| Sync Status | Meaning |
|---|---|
| pending | Approved but not yet sent to Swipey |
| syncing | Payment in progress |
| synced | Successfully sent to Swipey |
| failed | Swipey sync failed — can be retried via bulk-approve |

#### Viewing Timesheet Detail
Click any timesheet row to open the detail panel. Shows:
- Contractor name, outlet, month/year, submission sequence number
- Day-by-day breakdown: date, day name, outlet, hours worked, hourly rate
- Total hours and total amount
- Approve / Reject buttons (if status = submitted)
- Audit history (collapsible): every submission, rejection, and resubmission event with timestamps

#### Approving a Timesheet (single)
Open timesheet → click Approve. Days are locked — contractor cannot resubmit approved days.
Approval changes: status → approved, sync_status stays → pending (payment not yet sent to Swipey).

#### Rejecting a Timesheet
Open timesheet → click Reject → enter written reason (required) → Confirm Reject.
Effect: all submitted days are unlocked. Contractor can resubmit corrected hours.
Rejection reason is visible to the contractor on their timesheet history page.

#### Bulk Approve & Sync to Swipey (Admin only)
1. Filter to the target month/year
2. Check the boxes next to timesheets to process
3. The header shows total count and total RM amount
4. Click the Process button → confirm dialog
5. System approves any still-submitted timesheets, generates invoice numbers (format: BEN-YYYYMM-SEQ), and syncs to Swipey Bill Payment API
6. Results show: X synced, X failed

Eligible for bulk-approve:
- Status = submitted (will be auto-approved then synced), OR
- Status = approved AND sync_status = pending or failed (retry)

Not eligible: already synced timesheets.

#### Custom Day Rates (Admin only)
In the timesheet detail panel, admin can click on any day's rate (shown with a dashed underline) to override it — for example, setting a higher rate for a public holiday.
Custom rates are marked with a ★ star.
Changing a rate immediately recalculates the total amount for that timesheet.

### 3.4 Sequence Numbers (multiple submissions per month)
If a contractor's first batch is approved and they later submit more days in the same month, a new timesheet record is created with Submission #2, #3, etc. Each sequence is reviewed and paid independently.

### 3.5 Notes
Notes can be attached to any contractor:
- **Internal**: only visible to managers and admins
- **External**: visible to the contractor on their timesheet page

Use external notes for payment instructions, attendance queries, or messages you want the contractor to see.

### 3.6 Users Tab (Admin only)
Add new users (managers or admins), view existing users, deactivate users.
You cannot deactivate your own account.
Roles:
- **Site Manager** — review/edit hours, approve/reject timesheets
- **Admin / HR** — full access including Swipey sync and user management

---

## SECTION 4 — CONTRACTOR USER GUIDE

Write this section in simple, friendly language. The audience is food-court workers who may be non-technical.

### 4.1 What You Need
- The registration link sent to you by HR (via WhatsApp or SMS)
- Your DuitNow QR code image (from your Touch 'n Go, Maybank/MAE, or Affin Bank app)
- Your IC number (MyKad)
- A smartphone with a browser (no app download needed)

### 4.2 Step 1 — Register Your Payment Details
1. Open the registration link HR sent you
2. Upload your DuitNow QR code image (tap the upload area or take a photo)
3. The system reads your bank name and account number from the QR
4. Verify the details are correct — if not, tap "Try Again" and upload again
5. Enter your IC number (format: 901231-14-1234 or 12 digits without dashes)
6. Optionally correct your name if it appears wrong
7. Tap "Complete Registration"

You only need to do this once. Your payment details are saved securely.

If you are being re-registered after being inactive: your previous bank details are shown automatically. You only need to re-confirm your IC. You can upload a new QR if your bank account has changed.

### 4.3 Step 2 — Submit Your Monthly Timesheet
Open your timesheet link (separate from the registration link — HR will send it).
1. Select the month and year
2. Tap each day you worked to add hours
3. Review total hours and estimated payment amount
4. Tap Submit

You can submit days in multiple batches within the same month. Approved days are locked and cannot be changed.

### 4.4 What Happens After You Submit
- HR will review your timesheet
- If approved: payment will be processed via your registered DuitNow account
- If rejected: you will see the reason on your timesheet page. Resubmit the corrected days.

### 4.5 Checking Your Payment History
Open your timesheet link → scroll to the history section. You can see all past submissions, statuses (submitted / approved / rejected / synced), and amounts.

### 4.6 Notes from HR
If HR has left you a message, it will appear at the top of your timesheet page.

---

## SECTION 5 — FULL CONSTRAINTS REFERENCE

List all system constraints grouped by category. Be precise and include error messages where relevant.

### 5.1 Contractor Record Constraints
| Constraint | Detail |
|---|---|
| Phone uniqueness | Each phone number can only appear once. Error: "A contractor with this phone number already exists: [Name]." |
| Hourly rate | Must be greater than RM 0.00 |
| IC number format | Must match: 901231-14-1234 (with dashes) or 901231141234 (12 digits, no dashes) |
| Activation gate | Contractor cannot be set to active without: acquirer_id, account_number, and bank_name all present. Error: "Cannot activate: payment details missing." |
| Termination | Terminated contractors cannot be reactivated. Their registration link is permanently disabled. |
| Inactive reactivation | Sets status back to pending. Contractor must re-confirm via registration link. Existing QR data is retained. |

### 5.2 QR Code Constraints
| Constraint | Detail |
|---|---|
| Format | Must be a DuitNow QR (EMVCo TLV format). Non-DuitNow QR codes will be rejected. |
| Account uniqueness | Each bank account number can only be registered to one contractor. Error: "This [bank] account (···XXXX) is already registered to another contractor." |
| Supported banks | Touch 'n Go (acquirer ID: 890053), Maybank/MAE (588734), Affin Bank (501664). Other banks show as "Unknown". |
| Image quality | Must be a clear, readable QR image (PNG, JPG, or screenshot). Blurry or partial images will fail. |
| Registration link gate | The registration link is blocked for contractors with status inactive or terminated. |

### 5.3 Timesheet Constraints
| Constraint | Detail |
|---|---|
| Active status required | Only contractors with status = active can submit timesheets. |
| Hours per day | Must be greater than 0. Cannot submit 0-hour days. |
| Day range | Day number must be between 1 and 31. |
| Month range | Month must be between 1 and 12. |
| At least one day | Cannot submit an empty timesheet (no days provided). |
| Approved days locked | Once a day entry is approved, it cannot be resubmitted. |
| Rejected days unlocked | Rejected day entries can be resubmitted with corrected hours. |
| New sequence on re-submit post-approval | If a contractor submits new days after their batch is approved, a new timesheet record is created (Submission #2, #3…). |

### 5.4 Approval & Sync Constraints
| Constraint | Detail |
|---|---|
| Rejection reason required | Cannot reject a timesheet without providing a written reason. |
| Approve gate | Single approve only works on timesheets with status = submitted. |
| Bulk approve eligibility | Only: submitted timesheets OR approved timesheets with sync_status = pending or failed. Already-synced timesheets are skipped. |
| Bulk approve role | Admin role required. Managers cannot bulk-approve. |
| Custom day rate | Admin role required. Managers cannot edit day-level rates. |
| Invoice format | BEN-YYYYMM-SEQ (e.g., BEN-202603-001) |
| Swipey mock mode | Active when SWIPEY_API_KEY starts with "stub". All payments are simulated — no real money moves. |
| Payment record timing | A payment record is inserted in the database BEFORE the Swipey sync attempt. Failed syncs are recorded with the error message for retry. |
| Retry logic | Swipey sync retries up to 3 times with exponential backoff (2s, 4s, 8s). |

### 5.5 Notes Constraints
| Constraint | Detail |
|---|---|
| Visibility | internal = managers/admins only. external = contractor can also see it. |
| Who can write | Any manager or admin. |
| Content | Free text, no length limit enforced in the interface. |

### 5.6 User Account Constraints
| Constraint | Detail |
|---|---|
| Self-deactivation blocked | An admin cannot deactivate their own account. |
| Roles | Only two roles: admin and manager. |
| Password minimum | 8 characters minimum. |
| Email uniqueness | Each email address can only be used for one account. |

---

## SECTION 6 — WEEK MAPPING (for payroll reference)

Days submitted by contractors are automatically grouped into weeks for the payroll summary:

| Days | Week |
|---|---|
| 1 – 7 | Week 1 |
| 8 – 14 | Week 2 |
| 15 – 21 | Week 3 |
| 22 – 31 | Week 4 |

---

## SECTION 7 — OUT OF SCOPE

The following are explicitly not supported in the current system. Do not attempt to configure or request these features:

1. WhatsApp or SMS API integration — link sharing is manual
2. Multi-level approver workflow — single approve/reject only
3. Automated audit logs — the day-level audit history is available but not a formal audit module
4. Role-based access beyond admin/manager — no department or outlet-level access control
5. Multi-company segregation (e.g., BEN HQ vs BEN HR) — this is a Swipey platform feature
6. Automated notifications (email, SMS, push) — all communication is manual
7. Reporting and analytics dashboards — payment history is viewable per contractor but no aggregate reports exist

---

## SECTION 8 — PENDING / KNOWN LIMITATIONS

Document these as known items awaiting resolution:

1. **Swipey API key** — mock mode is currently active. No real payments are processed until the live API key and endpoint spec are received from the Swipey team and configured in the backend.
2. **Public Bank QR** — the acquirer ID for Public Bank QR codes has not been confirmed. Public Bank QRs will parse as "Unknown (XXXXXX)" until the ID is added to the bank code map.
3. **Swipey sandbox URL** — a staging/sandbox endpoint from Swipey is needed for end-to-end testing before going live.
4. **Rate limit** — Swipey's rate limit for the bulk-approve endpoint (up to ~80 contractors per run) has not been confirmed.

---

Format the final document cleanly with:
- Clear section headers (H1 for sections, H2/H3 for subsections)
- Tables where data is comparative
- Numbered steps for all workflows
- Bold for key terms on first use
- A short summary box at the top of each section stating who that section is for

Output as a single markdown document ready to be saved as a PDF or printed.
