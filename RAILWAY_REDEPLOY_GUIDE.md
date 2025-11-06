# Railway Deployment Issue - How to Force Redeploy

## Problem
Railway is still running old code that doesn't use SUPABASE_SERVICE_ROLE_KEY.
You added the environment variable, but Railway needs to pull and deploy the updated code.

## Solution: Force Railway to Redeploy

### Option 1: Trigger Redeploy from Railway Dashboard (Fastest)

1. Go to https://railway.app
2. Select your project: **internal-automation-production**
3. Click on your service
4. Go to the **Deployments** tab
5. Find the latest deployment
6. Click the **three dots menu** (⋮) on the right
7. Click **Redeploy**

This will rebuild and redeploy with the latest code from GitHub.

### Option 2: Push a Dummy Commit to Trigger Auto-Deploy

If Railway is connected to your GitHub repo, pushing new commits triggers auto-deploy.

Since we already pushed our changes, try:
```bash
git commit --allow-empty -m "Trigger Railway redeploy"
git push
```

### Option 3: Manual Redeploy via Railway CLI

If you have Railway CLI installed:
```bash
railway up
```

## What to Look For After Redeploying

### In Railway Build Logs:
You should see the build pulling latest code from the branch:
```
Cloning repository...
Checking out commit: e4ef2e8...
```

### In Railway Application Logs (Startup):
You MUST see these messages:
```
Supabase client created successfully!
Using SERVICE_ROLE_KEY (bypasses RLS)
```

If you see this instead, it's NOT working:
```
Warning: Using ANON_KEY (subject to RLS policies)
```

## Verify Environment Variable is Set

While you're in Railway dashboard:

1. Go to your service
2. Click **Variables** tab
3. Verify you see:
   - `SUPABASE_SERVICE_ROLE_KEY` = [your service key]
   - `SUPABASE_URL` = [your supabase url]

## Check Which Branch Railway is Deploying

1. In Railway dashboard
2. Go to **Settings** tab
3. Under **Source**, check:
   - Is it connected to the correct GitHub repo?
   - Which branch is it deploying? (Should be `main` or your production branch)

**IMPORTANT**: Our changes are on branch `claude/review-live-workflow-011CUrsmXtJdLPe3VYV4j6Gk`

If Railway is deploying from `main` branch, you need to either:
- Merge our PR to main, OR
- Change Railway to deploy from our branch

## Let Me Know

After you trigger the redeploy, check:
1. What branch is Railway deploying from?
2. Do you see "Using SERVICE_ROLE_KEY" in the logs?
3. Does the RLS error still occur?
