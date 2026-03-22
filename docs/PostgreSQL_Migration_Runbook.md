# SiloXR SQLite to PostgreSQL Migration Runbook

This runbook is the safest way to migrate the existing SiloXR data from SQLite to PostgreSQL without breaking the Django event-driven workflow.

## 1. Goal

Move the current production or staging dataset from SQLite to PostgreSQL while preserving:

- users and authentication data
- products
- inventory events
- burn rates and forecasts
- decisions and feedback history
- notifications and billing records

## 2. Current Configuration

SiloXR now supports both backends through environment variables in:

- [base.py](/C:/Users/HP/Desktop/SiloXR_/venv/siloxr/siloxr/settings/base.py)
- [\.env](/C:/Users/HP/Desktop/SiloXR_/venv/siloxr/siloxr/settings/.env)

Set:

```env
DB_BACKEND=sqlite
```

for SQLite, or:

```env
DB_BACKEND=postgres
POSTGRES_DB=siloxr
POSTGRES_USER=siloxr
POSTGRES_PASSWORD=replace_me
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5432
```

for PostgreSQL.

## 3. Prerequisites

Before cutover, make sure:

1. PostgreSQL is installed and running.
2. A PostgreSQL database and user exist.
3. The Django PostgreSQL driver is installed.

Recommended package:

```powershell
pip install psycopg[binary]
```

Alternative:

```powershell
pip install psycopg2-binary
```

## 4. Backup the Existing SQLite Database

Always keep the SQLite file untouched until PostgreSQL is fully verified.

From:

- [manage.py](/C:/Users/HP/Desktop/SiloXR_/venv/siloxr/manage.py)

copy the database file:

```powershell
Copy-Item .\db.sqlite3 .\db.backup.sqlite3
```

## 5. Create the PostgreSQL Database

Example:

```sql
CREATE DATABASE siloxr;
CREATE USER siloxr WITH PASSWORD 'replace_me';
GRANT ALL PRIVILEGES ON DATABASE siloxr TO siloxr;
```

## 6. Switch Django to PostgreSQL

Update [\.env](/C:/Users/HP/Desktop/SiloXR_/venv/siloxr/siloxr/settings/.env):

```env
DB_BACKEND=postgres
POSTGRES_DB=siloxr
POSTGRES_USER=siloxr
POSTGRES_PASSWORD=replace_me
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5432
POSTGRES_CONN_MAX_AGE=60
POSTGRES_SSLMODE=prefer
```

## 7. Create the PostgreSQL Schema

Run migrations against PostgreSQL:

```powershell
python manage.py migrate
```

This creates the schema structure before any data import.

## 8. Export Data from SQLite

Switch [\.env](/C:/Users/HP/Desktop/SiloXR_/venv/siloxr/siloxr/settings/.env) back temporarily to:

```env
DB_BACKEND=sqlite
```

Then export:

```powershell
python manage.py dumpdata --natural-foreign --natural-primary --exclude auth.permission --exclude contenttypes > data.json
```

If the database is large, export app by app:

```powershell
python manage.py dumpdata core inventory engine notifications billing api --natural-foreign --natural-primary > data.json
```

## 9. Load Data into PostgreSQL

Switch [\.env](/C:/Users/HP/Desktop/SiloXR_/venv/siloxr/siloxr/settings/.env) back to:

```env
DB_BACKEND=postgres
```

Then load:

```powershell
python manage.py loaddata data.json
```

## 10. Reset PostgreSQL Sequences

After loading fixtures, reset auto-increment sequences:

```powershell
python manage.py sqlsequencereset core inventory engine notifications billing api auth | python manage.py dbshell
```

This prevents ID collisions when new records are created after import.

## 11. Verify Critical Counts

Before cutover, compare SQLite and PostgreSQL counts for:

- users
- products
- inventory events
- burn rates
- forecast snapshots
- decisions
- notifications
- billing/payment records

Example checks:

```powershell
python manage.py shell
```

Then compare model counts in each backend.

## 12. Verify Critical Flows

After import, test:

1. user login
2. signup
3. password reset
4. product creation
5. sale recording
6. restock recording
7. stock count recording
8. uploads
9. forecast rendering
10. decision generation
11. notifications
12. billing flow

## 13. Recommended Cutover Strategy

Safest approach:

1. back up SQLite
2. create PostgreSQL schema
3. export SQLite data
4. import into PostgreSQL
5. verify counts and flows in staging
6. freeze writes briefly
7. do a final export/import if needed
8. switch production env to PostgreSQL
9. monitor logs

## 14. Important Notes for SiloXR

SiloXR is event-driven, so timestamp integrity matters. Pay close attention to:

- `occurred_at`
- `created_at`
- UUID relationships
- product ownership
- decision and forecast foreign keys

The migration must preserve event chronology because the engines use time ordering for learning, forecasting, and trust.

## 15. Rollback Plan

If anything fails after switching to PostgreSQL:

1. revert [\.env](/C:/Users/HP/Desktop/SiloXR_/venv/siloxr/siloxr/settings/.env) to:

```env
DB_BACKEND=sqlite
```

2. restart the backend
3. continue operating from the original SQLite file

Because the SQLite file is left untouched, rollback is straightforward.

## 16. Recommended Next Step

Before production cutover, do one full dry run in staging:

- export from SQLite
- import to PostgreSQL
- validate counts
- test all key user flows

That is the lowest-risk path for SiloXR.
