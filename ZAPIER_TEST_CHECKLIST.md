# What to Check After Running Zapier Test

## 1. Railway Logs - Check These Messages

✅ **Success Indicators**:
```
Supabase client created successfully!
Using SERVICE_ROLE_KEY (bypasses RLS)
Received Zapier webhook data: {...}
Inserting company record: {...}
Supabase response: {...}
```

❌ **Failure Indicators**:
```
Customer storage error: {'code': '42501', ...}  # RLS error (should NOT see this now)
Warning: Using ANON_KEY (subject to RLS policies)  # Should NOT see this
```

## 2. Supabase Dashboard - Verify Company Created

1. Go to https://app.supabase.com
2. Select your project
3. Click **Table Editor** (left sidebar)
4. Open **companies** table
5. Look for the newest record with:
   - The customer email from your test
   - The clickup_task_id from Zapier
   - kyb_status: 'pending_documents'

## 3. Expected Zapier Response

If successful, Zapier should receive:
```json
{
  "success": true,
  "task_id": "your_task_id",
  "upload_link": "https://...",
  "message": "Customer data processed successfully",
  "customer_record": {...}
}
```

## Quick Checklist

- [ ] Railway logs show "Using SERVICE_ROLE_KEY"
- [ ] No RLS error in logs
- [ ] Company record appears in Supabase
- [ ] Zapier shows success (200 response)
- [ ] Customer received email with upload link
- [ ] ClickUp task updated with comment

Let me know what you see!
