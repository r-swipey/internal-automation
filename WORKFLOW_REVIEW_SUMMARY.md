# Workflow Review Summary - Company Creation via Zapier Webhook

**Date**: November 6, 2025
**Production URL**: https://internal-automation-production.up.railway.app
**Endpoint**: `/zapier-webhook`

---

## Executive Summary

✅ **Workflow Code**: Working correctly
❌ **Current Issue**: Row-Level Security (RLS) blocking database operations
✅ **Fix**: Implemented and ready to deploy

The workflow is properly implemented but currently failing due to RLS policies enabled on Supabase. The fix has been committed and requires a simple environment variable update in Railway.

---

## Workflow Analysis

### 1. Zapier Webhook Endpoint (`/zapier-webhook`)

**Location**: `app.py:1024-1095`

**Purpose**: Receives customer data from Zapier when a Typeform is submitted

**Expected Payload**:
```json
{
  "customer_name": "John Doe",
  "customer_email": "john@company.com",
  "company_name": "ABC Corp",
  "phone": "+1234567890",
  "business_type": "Technology",
  "typeform_response_id": "abc123",
  "submission_timestamp": "2025-01-15T10:30:00Z",
  "clickup_task_id": "task_id_from_zapier",
  "clickup_task_url": "https://app.clickup.com/t/task_id"
}
```

**Workflow Steps**:
1. ✅ Validates required fields (customer_name, customer_email, company_name, clickup_task_id)
2. ✅ Generates customer upload token
3. ❌ **Creates company record in Supabase** - Currently failing due to RLS
4. ✅ Updates ClickUp KYB status to 'pending_documents'
5. ✅ Sends email to customer with upload link
6. ✅ Updates ClickUp task with upload link
7. ✅ Returns success response to Zapier

### 2. Company Creation Logic (`store_customer_info`)

**Location**: `app.py:273-302`

**Supabase Table**: `companies`

**Fields Created**:
```python
{
    'email': customer_data['customer_email'],
    'customer_name': customer_data['customer_name'],
    'customer_first_name': customer_data.get('customer_first_name'),
    'phone': customer_data.get('phone'),
    'clickup_task_id': task_id,
    'company_name': customer_data['company_name'],
    'typeform_submission_id': customer_data.get('typeform_response_id'),
    'kyb_status': 'pending_documents',
    'kyb_failure_reason': None,
    'first_upload_at': None,
    'kyb_completed_at': None
}
```

**Current Issue**:
```
Error: new row violates row-level security policy for table "companies"
Code: 42501
```

---

## Root Cause Analysis

### The Problem

When you enabled Row-Level Security (RLS) on the `companies` and `documents` tables in Supabase, you activated a security feature that restricts database operations based on user permissions.

### Why It's Failing

The application was using `SUPABASE_ANON_KEY` which:
- Is designed for client-side (frontend) operations
- Has limited permissions
- Is subject to RLS policies
- Cannot bypass RLS restrictions

For backend operations, we need `SUPABASE_SERVICE_ROLE_KEY` which:
- Is designed for server-side operations
- Has full database access
- Bypasses all RLS policies
- Should never be exposed to the client

### The Fix

**Code Changes** (Already committed):

**Before** (`app.py:59`):
```python
supabase_key = os.getenv('SUPABASE_ANON_KEY')
```

**After** (`app.py:59-60`):
```python
# Use SERVICE_ROLE_KEY for backend operations to bypass RLS
supabase_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY') or os.getenv('SUPABASE_ANON_KEY')
```

The code now:
- Prioritizes the service role key
- Falls back to anon key if service key unavailable
- Logs which key is being used for debugging

---

## Implementation Steps

### Step 1: Get Service Role Key from Supabase

1. Go to https://app.supabase.com
2. Select your project
3. Navigate to: **Settings** → **API**
4. Scroll to **Project API keys**
5. Find **service_role** (marked as "secret")
6. Click the eye icon and copy the key

⚠️ **Security Note**: This key is sensitive. Never commit to git or expose publicly.

### Step 2: Update Railway Environment Variable

1. Go to https://railway.app
2. Open project: **internal-automation-production**
3. Click on your service/deployment
4. Go to **Variables** tab
5. Add new variable:
   - **Name**: `SUPABASE_SERVICE_ROLE_KEY`
   - **Value**: [paste the service role key]
6. Save

Railway will automatically redeploy (takes ~1-2 minutes).

### Step 3: Verify the Fix

After redeployment, check Railway logs. You should see:
```
Supabase client created successfully!
Using SERVICE_ROLE_KEY (bypasses RLS)
```

### Step 4: Test the Workflow

**Option A: Use the test script**
```bash
python test_zapier_webhook_simple.py
```

**Option B: Send a real webhook from Zapier**
- Trigger your Zapier workflow
- Check Railway logs for success
- Verify company created in Supabase

---

## Test Scripts Created

### 1. `test_zapier_webhook_simple.py`
- Simple test without Supabase dependencies
- Tests endpoint availability
- Tests webhook with valid payload
- Tests validation with missing fields
- **Usage**: `python test_zapier_webhook_simple.py`

### 2. `test_live_workflow.py`
- Advanced test with Supabase verification
- Sends webhook request
- Queries Supabase to verify company creation
- Validates all fields match expected values
- **Usage**: `python test_live_workflow.py`
- **Requires**: Supabase credentials in environment

---

## Workflow Components Overview

### Components Involved

1. **Zapier** → Sends webhook when Typeform submitted
2. **Railway App** → Receives webhook, processes data
3. **Supabase** → Stores company records
4. **SendGrid** → Sends email to customer
5. **ClickUp** → Updates task status and adds comments
6. **AWS S3** → Stores uploaded documents (later in workflow)

### Data Flow

```
Typeform Submission
    ↓
Zapier processes form data
    ↓
Zapier creates ClickUp task
    ↓
Zapier sends webhook to Railway
    ↓
Railway creates Supabase company record ← FAILING HERE
    ↓
Railway generates upload link
    ↓
Railway sends email via SendGrid
    ↓
Railway updates ClickUp task
    ↓
Customer receives email with link
```

---

## Current Status

### ✅ Working Components
- Zapier webhook endpoint
- Request validation
- Token generation
- Email sending (SendGrid)
- ClickUp updates
- Upload link generation

### ❌ Failing Component
- Supabase company record creation (RLS blocking)

### ✅ Fix Status
- Code changes: Committed ✓
- Tests created: Done ✓
- Documentation: Complete ✓
- **Pending**: Railway environment variable update

---

## Post-Fix Verification

After updating Railway environment variable, verify:

1. **Check Logs**:
   ```
   ✓ "Using SERVICE_ROLE_KEY (bypasses RLS)"
   ```

2. **Test Webhook**:
   ```bash
   python test_zapier_webhook_simple.py
   ```
   Expected: All 3 tests pass

3. **Check Supabase**:
   - Go to Supabase dashboard
   - Open `companies` table
   - Look for test company record

4. **Test Real Flow**:
   - Submit a Typeform (or trigger Zapier)
   - Check company created in Supabase
   - Verify email sent
   - Check ClickUp task updated

---

## Security Best Practices

### ✅ Do's
- Keep service role key in Railway environment variables
- Use anon key for client-side operations
- Use service role key for backend operations
- Keep RLS enabled for security
- Monitor logs for unusual activity

### ❌ Don'ts
- Never commit service role key to git
- Never expose service role key in client code
- Don't disable RLS (defeats the purpose)
- Don't use anon key for backend operations

---

## Alternative Solutions (Not Recommended)

### Option 1: Create RLS Policies for Anon Role
You could create policies allowing anon to insert:
```sql
CREATE POLICY "Allow anon inserts" ON companies
  FOR INSERT TO anon WITH CHECK (true);
```
**Why not**: Defeats RLS purpose, creates security risk.

### Option 2: Disable RLS
You could disable RLS on these tables:
```sql
ALTER TABLE companies DISABLE ROW LEVEL SECURITY;
```
**Why not**: Removes security protection, bad practice.

### ✅ Recommended Solution
Use service role key for backend + keep RLS enabled.

---

## Troubleshooting Guide

### Issue: Still seeing "Using ANON_KEY" in logs

**Cause**: Environment variable not set correctly

**Solutions**:
1. Verify variable name: `SUPABASE_SERVICE_ROLE_KEY` (exact spelling)
2. Check for extra spaces in the value
3. Ensure Railway redeployed after adding variable
4. Check deployment logs for startup errors

### Issue: Still getting RLS errors

**Cause**: Wrong key or key not working

**Solutions**:
1. Verify it's the **service_role** key, not **anon** key
2. Check key hasn't been rotated in Supabase
3. Ensure Supabase URL matches
4. Try regenerating the service role key

### Issue: "Access denied" (403 errors)

**Cause**: Different issue, not RLS-related

**Solutions**:
1. Check Railway firewall/request filtering
2. Verify endpoint URL is correct
3. Review Railway deployment logs
4. Check if Railway service is running

---

## File Changes Summary

### Modified Files
1. **app.py** (lines 59-67)
   - Uses SUPABASE_SERVICE_ROLE_KEY
   - Fallback to ANON_KEY
   - Added logging

2. **.env.template**
   - Added SUPABASE_SERVICE_ROLE_KEY
   - Documented both keys

### New Files
1. **RLS_FIX_GUIDE.md** - Detailed fix guide
2. **test_zapier_webhook_simple.py** - Simple test script
3. **test_live_workflow.py** - Advanced test script
4. **WORKFLOW_REVIEW_SUMMARY.md** - This document

---

## Quick Action Checklist

- [ ] Get service role key from Supabase dashboard
- [ ] Add `SUPABASE_SERVICE_ROLE_KEY` to Railway variables
- [ ] Wait for Railway to redeploy (~2 minutes)
- [ ] Check logs for "Using SERVICE_ROLE_KEY"
- [ ] Run test script: `python test_zapier_webhook_simple.py`
- [ ] Verify company creation in Supabase
- [ ] Test real Zapier workflow
- [ ] Monitor for any errors

---

## Support Resources

- **RLS_FIX_GUIDE.md** - Detailed step-by-step guide
- **Test Scripts** - Automated testing
- **Railway Logs** - Real-time monitoring
- **Supabase Dashboard** - Database verification

---

## Conclusion

The workflow code is correctly implemented. The only issue is the RLS policy blocking database operations. This is easily fixed by:

1. Adding the SUPABASE_SERVICE_ROLE_KEY to Railway
2. Letting Railway redeploy
3. Testing to confirm it works

The fix maintains security (keeps RLS enabled) while allowing the backend service to operate correctly.

**Estimated Time to Fix**: 5 minutes
**Risk Level**: Low (only adding an environment variable)
**Impact**: Resolves all webhook failures

---

**Next Steps**: Follow the Quick Action Checklist above to deploy the fix.
