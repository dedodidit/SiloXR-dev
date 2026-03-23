# SiloXR Release Workflow

This is the standard workflow for moving changes from local development to production.

## Current Stack

- Frontend: Vercel
- Backend: Render
- Database: Supabase PostgreSQL
- Source control: GitHub

## Branching Model

Recommended:

- `master` or `main`: production branch watched by hosting providers
- feature branches: short-lived branches for new work

Example feature branch:

```powershell
git checkout -b codex/short-description
```

## Day-to-Day Change Flow

### 1. Make changes locally

Work in:

- [C:\Users\HP\Desktop\SiloXR_](C:/Users/HP/Desktop/SiloXR_)

### 2. Test locally

Frontend:

```powershell
cd C:\Users\HP\Desktop\SiloXR_\frontend
npm run build
```

Backend:

```powershell
cd C:\Users\HP\Desktop\SiloXR_\venv\siloxr
python manage.py check
```

If the change affects production settings or PostgreSQL:

```powershell
python manage.py check --settings=siloxr.settings.production
```

### 3. Commit the change

From repo root:

```powershell
cd C:\Users\HP\Desktop\SiloXR_
git status
git add .
git commit -m "Describe the change"
```

### 4. Push to GitHub

If the branch already exists remotely:

```powershell
git push
```

If it is a new branch:

```powershell
git push -u origin your-branch-name
```

### 5. Merge to the production branch

Use GitHub:

- open a pull request
- review
- merge into the branch watched by Vercel and Render

If you are operating without PRs, push directly to the production branch only when you are confident in the change.

## What happens after merge

### Frontend

Vercel redeploys automatically when the watched branch updates.

### Backend

Render redeploys automatically when the watched branch updates.

## Database Changes

If your change adds or modifies Django models:

1. create migrations locally
2. commit the migration files
3. deploy the backend
4. run:

```powershell
python manage.py migrate --settings=siloxr.settings.production
```

Do not skip this when model/schema changes are involved.

## Safe Release Checklist

Before pushing:

- frontend builds
- backend `check` passes
- new env vars are documented
- migrations are included if models changed
- local smoke test passes

After deploy:

- open landing page
- log in
- open dashboard
- open one workspace
- create or edit a product
- record sale / restock / stock count
- verify billing page
- verify notifications path if affected

## Change Types and What To Do

### Frontend-only change

- push code
- let Vercel redeploy
- smoke test UI

### Backend-only change

- push code
- let Render redeploy
- test API-backed flows

### Database/schema change

- push code
- let Render redeploy
- run migrations
- test writes and reads

### Configuration/env change

- update provider environment variables
- redeploy backend or frontend if needed
- verify affected flow

## Recommended Habit

Use this order every time:

1. change
2. test
3. commit
4. push
5. merge
6. deploy
7. migrate if needed
8. smoke test production

This keeps SiloXR predictable and reduces deployment mistakes.
