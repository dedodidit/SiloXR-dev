# SiloXR Backend Deployment on Render

## Service Setup

- Create a new `Web Service`
- Connect the GitHub repo
- Branch: `codex/siloxr-production-prep` or your merged production branch
- Root Directory: `venv/siloxr`

## Build Command

```bash
pip install -r requirements.txt
```

## Start Command

```bash
gunicorn siloxr.wsgi:application --bind 0.0.0.0:$PORT
```

## Required Environment Variables

```env
DJANGO_SETTINGS_MODULE=siloxr.settings.production
SECRET_KEY=replace-with-real-secret
ALLOWED_HOSTS=siloxr-dev.onrender.com
CSRF_TRUSTED_ORIGINS=https://siloxr-dev.onrender.com,https://your-vercel-frontend.vercel.app

DB_BACKEND=postgres
POSTGRES_DB=postgres
POSTGRES_USER=postgres.bzmkpsbankfahikoxdur
POSTGRES_PASSWORD=your-supabase-password
POSTGRES_HOST=aws-1-eu-west-1.pooler.supabase.com
POSTGRES_PORT=5432
POSTGRES_CONN_MAX_AGE=60
POSTGRES_SSLMODE=require

FRONTEND_BASE_URL=https://your-vercel-frontend.vercel.app

EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=true
EMAIL_HOST_USER=peopleofsiloxr@gmail.com
EMAIL_HOST_PASSWORD=your-gmail-app-password
DEFAULT_FROM_EMAIL=SiloXR <peopleofsiloxr@gmail.com>

TELEGRAM_BOT_TOKEN=your-telegram-bot-token
TELEGRAM_BOT_USERNAME=your-telegram-bot-username
TELEGRAM_WEBHOOK_SECRET=your-telegram-webhook-secret

PAYSTACK_PUBLIC_KEY=your-paystack-public-key
PAYSTACK_SECRET_KEY=your-paystack-secret-key
PAYSTACK_CALLBACK_URL=https://your-vercel-frontend.vercel.app/billing/upgrade
PAYSTACK_PRO_MONTHLY_NAIRA=15000
```

## After Deploy

Run once in the Render shell:

```bash
python manage.py check --settings=siloxr.settings.production
python manage.py migrate --settings=siloxr.settings.production
```

## Smoke Test

- open the frontend
- log in
- load dashboard
- open a workspace
- record a sale or stock count
- verify billing page opens
- verify backend API responds without host/csrf errors

## Current Backend Host

Your current Render backend URL is:

- `https://siloxr-dev.onrender.com`

So the minimum backend host settings should be:

```env
ALLOWED_HOSTS=siloxr-dev.onrender.com
CSRF_TRUSTED_ORIGINS=https://siloxr-dev.onrender.com,https://your-vercel-frontend.vercel.app
```
