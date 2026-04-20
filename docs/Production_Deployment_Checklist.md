# SiloXR Production Deployment Checklist

## Backend

1. Copy [\.env.production.example](/C:/Users/HP/Desktop/SiloXR_/venv/siloxr/siloxr/settings/.env.production.example) into your real production env store.
2. Set:
   - `SECRET_KEY`
   - `ALLOWED_HOSTS`
   - `CSRF_TRUSTED_ORIGINS`
   - PostgreSQL credentials
   - Gmail SMTP credentials
   - Paystack live keys
3. Run Django with:

```powershell
python manage.py migrate --settings=siloxr.settings.production
```

4. Verify:

```powershell
python manage.py check --settings=siloxr.settings.production
```

## Database Cutover

SQLite backup and export already created:

- [db.backup.sqlite3](/C:/Users/HP/Desktop/SiloXR_/docs/data/db.backup.sqlite3)
- [sqlite_export.json](/C:/Users/HP/Desktop/SiloXR_/docs/data/sqlite_export.json)

If you need to rerun the export/import locally:

```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\HP\Desktop\SiloXR_\venv\siloxr\scripts\export_sqlite_fixture.ps1
```

```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\HP\Desktop\SiloXR_\venv\siloxr\scripts\import_postgres_fixture.ps1
```

## Frontend

1. Build:

```powershell
npm run build
```

2. Confirm:
   - landing page on `/`
   - dashboard on `/dashboard`
   - workspaces open correctly
   - signup/login/reset password work
   - billing upgrade page loads correct price

## Ongoing Releases

Use the standard release process in:

- [Release_Workflow.md](/C:/Users/HP/Desktop/SiloXR_/docs/Release_Workflow.md)

This is the day-to-day path for:

- making local changes
- pushing to GitHub
- triggering Vercel/Render deploys
- running migrations when needed

## Post-Go-Live Checks

1. Login with an existing migrated user.
2. Create a product.
3. Record:
   - sale
   - restock
   - stock count
4. Confirm:
   - dashboard loads
   - product operations loads
   - decisions/workspaces load
   - notifications still dispatch
   - Paystack checkout initializes

## Important Note

The `.env` values shown earlier in chat included live-looking secrets. Rotate:

- Gmail app password
- any webhook/token values you already exposed
