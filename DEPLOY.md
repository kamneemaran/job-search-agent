# JobPilot Deployment Guide

## Prerequisites
- GitHub repo with the code pushed
- Supabase project created with schema run
- Accounts on Vercel.com and Railway.app (free tiers)

---

## Step 1: Deploy Backend to Railway

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Link to new project (from repo root)
railway init

# Set environment variables
railway variables set PYTHON_VERSION=3.12
railway variables set ENV=production

# Add your .env vars (from your local .env)
railway variables set GMAIL_ADDRESS=kminterviewer@gmail.com
railway variables set GMAIL_APP_PASSWORD="pyka twte bfrd jxek"
railway variables set GSHEET_ID=1NO-erkRi_aV7RSY8dMbZkxEZBA9jEN55IfIrK3S8WEg
railway variables set GMAIL_DIGEST_LABEL=JobDigests

# Deploy
railway up

# Get your URL
railway domain
# → https://your-project.up.railway.app
```

Test: `curl https://your-project.up.railway.app/api/health`

---

## Step 2: Deploy Frontend to Vercel

```bash
# Install Vercel CLI
npm install -g vercel

# Login
vercel login

# Deploy (from web/ directory)
cd web
vercel

# Set environment variables
vercel env add NEXT_PUBLIC_SUPABASE_URL
# → paste your Supabase URL

vercel env add NEXT_PUBLIC_SUPABASE_ANON_KEY
# → paste your Supabase anon key

vercel env add NEXT_PUBLIC_API_URL
# → https://your-project.up.railway.app

# Deploy to production
vercel --prod
# → https://your-project.vercel.app
```

---

## Step 3: Update Supabase Auth Redirects

In Supabase Dashboard → Authentication → URL Configuration:
- Site URL: `https://your-project.vercel.app`
- Redirect URLs: `https://your-project.vercel.app/auth/callback`

---

## Step 4: Update Railway CORS

In Railway → Variables, add:
```
ALLOWED_ORIGINS=https://your-project.vercel.app
```

---

## Step 5: Custom Domain (Optional)

### Vercel
Vercel Dashboard → your project → Settings → Domains → Add your domain

### Railway
Railway Dashboard → your project → Settings → Networking → Custom Domain

---

## Architecture

```
User → Vercel (Next.js frontend)
         ↓ API calls
       Railway (FastAPI backend)
         ↓ connects to
       Supabase (Auth + Database)
       Google Sheets (optional)
       Gmail (optional)
```

## Costs (Free Tiers)

| Service | Free Tier | Limits |
|---------|-----------|--------|
| Vercel | 100GB bandwidth | Serverless functions: 100hrs/mo |
| Railway | $5 credit/mo | ~500 hours of basic instance |
| Supabase | 500MB database | 50K MAU, 1GB storage |
| **Total** | **$0/mo** | Until you exceed limits |
