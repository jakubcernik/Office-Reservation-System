# Office Reservation System

A first-version Django application for office desks and parking spot reservations.

## What is included

- Django project with SQLite storage, or PostgreSQL (Supabase) via `DATABASE_URL`
- Login/logout via Django authentication
- Availability page for desks and parking spots
- Create, confirm, and cancel reservation flows (reserving takes one action)
- Django admin for resource and reservation management
- Approval flow for resources that need an office manager's decision
- Core business rule: parking confirmation requires a confirmed desk reservation for the same date

## CP1 walking skeleton (C02 definition)

This section defines one concrete end-to-end path that must be runnable after C03 (before C04).

### Scope

- Endpoint: `POST /reservations`
- Flow: `validate -> persist -> return reservation ID -> automated check`
- Goal: verify that one reservation can go through the full path from HTTP request to database row and back to HTTP response.

### Request contract

`POST /reservations`

```json
{
  "resource_id": 1,
  "reservation_date": "2026-09-21"
}
```

### Validation (minimum for CP1)

- user is authenticated
- `resource_id` exists and is active
- `reservation_date` is a valid date

### Persistence (minimum for CP1)

- create one reservation row in SQLite using Django ORM
- initial status for CP1: `DRAFT`

### Response contract

- success status: `201 Created`
- body includes created identifier:

```json
{
  "reservation_id": 123
}
```

### Automated check (must be runnable in C03)

- one integration test sends `POST /reservations`
- test asserts `201` response and `reservation_id` in JSON
- test verifies the reservation row exists in DB with matching user/resource/date

Suggested command:

```powershell
py manage.py test reservations.tests.WalkingSkeletonReservationCreateTests
```

Status in C02: this is the agreed, concrete walking skeleton definition. Full implementation is planned for C03.

## Local setup

### One-command scripts on Windows

- First time only:
  ```powershell
  .\scripts\first-run.ps1
  ```
- Every next start:
  ```powershell
  .\scripts\run.ps1
  ```

The first script creates the virtual environment, installs dependencies, runs migrations, and can create a superuser.

1. Create and activate a virtual environment.
2. Install dependencies.
3. Run migrations.
4. Create a superuser.
5. Start the development server.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Open `http://127.0.0.1:8000/` in your browser.

## Database: SQLite or Supabase (PostgreSQL)

The database is selected by the `DATABASE_URL` environment variable, which is read from the git-ignored `.env` file in the project root:

| `DATABASE_URL` | Database used |
| --- | --- |
| not set | local `db.sqlite3` file |
| set | the PostgreSQL database in that URL (for example Supabase) |

Other variables in `.env`:

| Variable | Meaning |
| --- | --- |
| `DJANGO_SECRET_KEY` | secret key of this machine |
| `DJANGO_DEBUG` | `true` or `false` |
| `DJANGO_ALLOWED_HOSTS` | comma separated host names |
| `DJANGO_USE_SQLITE` | `true` forces the local SQLite file even when `DATABASE_URL` is set |

A complete `.env` therefore looks like this (values are made up):

```dotenv
DJANGO_SECRET_KEY=django-insecure-change-me
DJANGO_DEBUG=true
DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost

# Database. Comment this line out to fall back to the local db.sqlite3 file.
DATABASE_URL=postgresql://postgres.abcdefghijklmnop:your-password@aws-0-eu-central-1.pooler.supabase.com:5432/postgres

DJANGO_USE_SQLITE=false
```

### Connecting to Supabase

1. Create a project on [supabase.com](https://supabase.com) and keep the database password.
2. Open **Project Settings -> Database -> Connection string -> URI**.
3. Put that string into `.env` as `DATABASE_URL` and replace the password placeholder.
4. Create the tables, the admin user, and optionally demo data:

```powershell
python manage.py migrate
python manage.py createsuperuser
python manage.py seed_demo_data
```

Notes:

- The dashboard placeholder is written as `[YOUR-PASSWORD]`. Replace the whole `[YOUR-PASSWORD]` part **including the square brackets** - the brackets are not part of the password.
- A password with characters like `[`, `]`, `@`, `#`, `:` or `/` has to be percent-encoded inside the URL, for example `[` becomes `%5B`. A password of only letters and digits avoids the problem completely.
- Prefer the **session pooler** string (host `*.pooler.supabase.com`, port `5432`). It works over IPv4. On the transaction pooler (port `6543`) PgBouncer cannot keep server-side cursors open; `settings.py` detects that and sets `DISABLE_SERVER_SIDE_CURSORS` for you.
- Supabase requires TLS. `settings.py` adds `sslmode=require` for remote hosts, so the connection string does not need to carry it.
- `python manage.py test` always runs on SQLite: the test runner creates and drops a throwaway database, which Supabase does not allow.

To check which database is used right now:

```powershell
python manage.py shell -c "from django.db import connection; print(connection.vendor, connection.settings_dict['HOST'])"
```

## Reserving and approvals

Reserving takes **one action**: pick a date on the availability page and press **Reserve**. The reservation is created and confirmed in the same step, so the resource is taken immediately.

Resources with `requires_approval` set (Django admin, **off by default**) are the exception: reserving such a resource creates a request that waits for an office manager. Requests do **not** block the resource, and a request nobody decides expires at the end of the day the reservation is for.

Managers are staff accounts or members of the `Office Manager` group, and they decide on the **Approvals** page. The demo data contains two such resources: desk `VED-01` and parking spot `P-VIP`.

A reservation can still be created as a draft (service layer or Django admin) and confirmed later — the four basic operations stay distinct, the interface just does not ask for the extra step. A failed check leaves nothing behind: no half-finished reservation and no orphaned draft.

## Run tests

```powershell
python manage.py test
```

## Seed demo data

To populate the database with example desks and parking spots, run:

```powershell
py manage.py seed_demo_data
```

To also create sample reservations for an existing user, pass the username:

```powershell
py manage.py seed_demo_data --demo-user jakub
```

## Main app modules

- `reservations/models.py`
- `reservations/services.py`
- `reservations/views.py`
- `reservations/forms.py`
- `reservations/templates/`
- `reservations/static/`
