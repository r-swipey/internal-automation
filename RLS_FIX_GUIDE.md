# RLS Fix Guide - Supabase Row-Level Security Issue

## Problem Summary

After enabling Row-Level Security (RLS) on the `companies` and `documents` tables in Supabase, the application started failing with the error:

```
Customer storage error: {'code': '42501', 'details': None, 'hint': None, 'message': 'new row violates row-level security policy for table "companies"'}
```

**Root Cause**: The application was using `SUPABASE_ANON_KEY` which is subject to RLS policies. When RLS was enabled, this key no longer had permission to insert records into the tables.

## Solution

Use `SUPABASE_SERVICE_ROLE_KEY` instead of `SUPABASE_ANON_KEY` for backend operations. The service role key bypasses RLS and has full database access.

## Step-by-Step Fix

### 1. Get Your Supabase Service Role Key

1. Go to your Supabase project dashboard: https://app.supabase.com
2. Select your project
3. Go to **Settings** (gear icon in bottom left)
4. Click on **API** in the settings menu
5. Scroll down to **Project API keys** section
6. Find the **service_role** key (it's marked as "secret")
7. Click the eye icon to reveal it, then copy it

⚠️ **IMPORTANT**: The service role key is sensitive! Never commit it to git or expose it publicly.

### 2. Update Railway Environment Variables

1. Go to your Railway project: https://railway.app
2. Select your project: **internal-automation-production**
3. Click on your deployment/service
4. Go to the **Variables** tab
5. Add a new variable:
   - **Name**: `SUPABASE_SERVICE_ROLE_KEY`
   - **Value**: [paste the service role key you copied]
6. Click **Add** or **Save**

The deployment will automatically restart with the new environment variable.

### 3. Verify the Fix

After Railway redeploys (takes about 1-2 minutes), check the deployment logs:

You should see:
```
Supabase client created successfully!
Using SERVICE_ROLE_KEY (bypasses RLS)
```

If you still see "Warning: Using ANON_KEY", the environment variable wasn't set correctly.

### 4. Test the Workflow

Run the test script to verify everything is working:

```bash
python test_zapier_webhook_simple.py
```

Or manually test by sending a webhook request from Zapier.

## What Changed in the Code

### app.py (Line 59-67)

**Before:**
```python
supabase_key = os.getenv('SUPABASE_ANON_KEY')
```

**After:**
```python
# Use SERVICE_ROLE_KEY for backend operations to bypass RLS
supabase_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY') or os.getenv('SUPABASE_ANON_KEY')
```

The code now:
1. First tries to use `SUPABASE_SERVICE_ROLE_KEY`
2. Falls back to `SUPABASE_ANON_KEY` if service key is not available
3. Prints which key is being used for debugging

## Understanding RLS

**Row-Level Security (RLS)** is a Supabase security feature that controls which rows users can access based on policies you define.

### Key Types:

1. **Anon Key** (Public)
   - Subject to RLS policies
   - Used for client-side operations (browser, mobile apps)
   - Limited permissions based on RLS rules

2. **Service Role Key** (Secret)
   - Bypasses ALL RLS policies
   - Full database access
   - Should only be used on backend/server
   - Must be kept secret

### When to Use Each:

- **Frontend (Client)**: Use Anon Key
  - User authentication and authorization
  - User-specific data access

- **Backend (Server)**: Use Service Role Key
  - Internal automation workflows
  - Admin operations
  - System-level database operations
  - Our case: Webhook processing, company creation

## Alternative Solutions (Not Recommended)

### Option 1: Create RLS Policies for Anon Role

You could create RLS policies that allow the anon role to insert:

```sql
-- Allow anon role to insert into companies table
CREATE POLICY "Allow anon inserts" ON companies
  FOR INSERT
  TO anon
  WITH CHECK (true);

-- Allow anon role to insert into documents table
CREATE POLICY "Allow anon inserts" ON documents
  FOR INSERT
  TO anon
  WITH CHECK (true);
```

**Why not recommended**: This defeats the purpose of RLS and creates security risks by giving public access to write operations.

### Option 2: Disable RLS

You could disable RLS on these tables:

```sql
ALTER TABLE companies DISABLE ROW LEVEL SECURITY;
ALTER TABLE documents DISABLE ROW LEVEL SECURITY;
```

**Why not recommended**: Removes security protections. Bad practice for production.

## Recommended: Keep RLS Enabled + Use Service Key

✅ **Best practice**: Keep RLS enabled for security, but use the service role key for backend operations.

This approach:
- Maintains security on the database level
- Allows backend services to operate without restrictions
- Protects against unauthorized direct database access
- Follows Supabase recommended practices

## Verification Checklist

- [ ] Obtained service role key from Supabase dashboard
- [ ] Added `SUPABASE_SERVICE_ROLE_KEY` to Railway environment variables
- [ ] Railway deployment restarted successfully
- [ ] Deployment logs show "Using SERVICE_ROLE_KEY (bypasses RLS)"
- [ ] Tested webhook endpoint successfully
- [ ] Company records are being created in Supabase
- [ ] No more RLS policy violation errors in logs

## Troubleshooting

### Still seeing "Using ANON_KEY" warning

**Issue**: The service role key environment variable isn't being read.

**Solutions**:
1. Check the variable name is exactly: `SUPABASE_SERVICE_ROLE_KEY`
2. Verify the value is correct (no extra spaces)
3. Ensure Railway redeployed after adding the variable
4. Check Railway logs for any startup errors

### Still getting RLS errors

**Issue**: The service key might not be working.

**Solutions**:
1. Verify the key is the **service_role** key, not the **anon** key
2. Check that the key hasn't been rotated/regenerated in Supabase
3. Ensure the Supabase project URL matches

### "Access denied" errors

**Issue**: Different issue, not related to RLS.

**Solutions**:
1. Check if Railway has any request filtering/firewall rules
2. Verify the endpoint URL is correct
3. Check Railway deployment logs for other errors

## Security Notes

1. **Never expose service role key**:
   - Don't commit to git
   - Don't include in client-side code
   - Don't log it in console/logs

2. **Use environment variables**:
   - Railway variables are encrypted
   - Accessible only to your deployment
   - Can be rotated easily if compromised

3. **Monitor usage**:
   - Check Supabase dashboard for unusual activity
   - Review Railway logs regularly
   - Set up alerts for errors

## Next Steps

After fixing this issue:

1. **Monitor the logs** for a few webhook requests to ensure stability
2. **Test the complete workflow** end-to-end
3. **Document** the environment variables needed for future deployments
4. Consider setting up **Supabase database webhooks** for additional automation

## Support

If you continue having issues:
- Check Railway deployment logs
- Check Supabase dashboard logs
- Review the test script output
- Verify all environment variables are set correctly
