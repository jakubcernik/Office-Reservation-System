# Architecture and Stack Decision

## Decision summary

Build a small browser-based Django application for local use. Use Django's built-in server, templates, forms, authentication, admin, ORM, and SQLite database. Keep the frontend server-rendered with plain HTML and CSS. Do not add a separate desktop client, JavaScript framework, REST API, background worker, or external database for the first version.

This is intentionally a monolithic application. One Python process and one SQLite file should be enough to run it locally.

## Minimal stack

| Area | Choice |
| --- | --- |
| Language | Python |
| Framework | Django |
| Database | SQLite, using Django ORM and migrations |
| UI | Django templates, standard HTML forms, and a small CSS file |
| Authentication | Django's built-in users, login, logout, and groups |
| Administration | Django admin for resources and users |
| Notifications | Django console email backend or a simple log message during local development |
| Server | Django development server on localhost |

## Application shape

Use one Django project and one main `reservations` app. Keep the initial structure small:

- `models.py`: users' reservations, desks, parking spots, dates, and statuses.
- `views.py`: browser pages and form handling.
- `forms.py`: validation for selecting dates, resources, and actions.
- `services.py`: the few operations that change reservation state.
- `templates/`: server-rendered pages.
- `static/`: plain CSS.
- Django admin: resource maintenance and basic user management.

Use Django's built-in `User` model unless the project later requires additional employee fields. Use a Django group such as `Office Manager` for administrative permissions. There is no need for a separate accounts app at this stage.

## Core behavior

The application should support:

1. Login and logout.
2. Viewing available desks and parking spots for a selected date.
3. Creating a draft reservation.
4. Confirming a reservation.
5. Cancelling the current user's confirmed reservation.
6. Managing resources through Django admin.

Reservation state changes should be handled by small explicit Python functions such as `create_draft`, `confirm_reservation`, and `cancel_reservation`. Views should call these functions rather than embedding all business rules in templates.

The parking rule remains part of confirmation: a user can confirm a parking reservation only when they also have a confirmed desk reservation for the same date. If the first version uses a cart, confirm all items in one `transaction.atomic()` block.

## Data and consistency

Start with whole-day reservations. A reservation needs:

- user
- resource
- date
- status: `DRAFT`, `CONFIRMED`, or `CANCELLED`

Only active resources should be available for new reservations. Confirmed reservations for the same resource and date must not overlap. Add a conditional unique constraint for confirmed reservations and also check availability in the service function. The database constraint protects the rule even if two browser requests arrive close together.

Use `transaction.atomic()` when confirming a reservation or cart. If a confirmation fails, no partial confirmation should remain. Draft expiry can be handled simply by ignoring old drafts when displaying the cart; a scheduled cleanup task is unnecessary for the local version.

If timed reservations or multiple simultaneous users become important, move the database to PostgreSQL and revisit the concurrency model. That is an upgrade path, not part of the initial stack.

## Notifications

Do not build a worker or message queue initially. After a successful confirmation or cancellation, write a simple notification to the console or use Django's development email backend. Keep the notification call behind a small Python function so a real external Notification Service can be added later without changing reservation logic.

## Local setup

The expected developer workflow is:

1. Create a Python virtual environment.
2. Install Django with `pip`.
3. Run migrations to create the SQLite file.
4. Create a superuser for Django admin.
5. Start the Django development server.
6. Open the local address in a browser.

Configuration should stay in Django settings and local environment variables. No credentials or generated database files should be committed.

## Implementation order

1. Create the Django project and `reservations` app.
2. Add resource and reservation models with migrations.
3. Register resources and reservations in Django admin.
4. Add login, availability, reservation, confirmation, and cancellation views.
5. Add the parking prerequisite and no-overlap validation.
6. Add simple templates and CSS for the employee workflow.
7. Add console/email notification hooks.

## Future upgrade triggers

Only add more infrastructure when a concrete need appears:

- PostgreSQL for higher concurrency or deployment beyond one local instance.
- HTMX or a JavaScript framework if server-rendered interactions become awkward.
- Celery or another worker if notifications must be retried asynchronously.
- SSO when the company identity provider is available.
- A separate API when a mobile or external client is actually required.

## Change record: PostgreSQL (Supabase) instead of SQLite

The first version stored everything in a local SQLite file. The project now needs a database that is reachable from more than one machine, so the storage layer moved to PostgreSQL hosted on Supabase.

How it was done, keeping the "no code change" promise:

- Only `settings.py` changed. `models.py`, `services.py`, `views.py`, and `forms.py` are untouched, because the Django ORM and the existing migrations target PostgreSQL as well.
- The database is selected by the `DATABASE_URL` environment variable (`.env`, git-ignored). No URL means the old local SQLite file, so a fresh checkout still runs without any cloud account.
- Secrets stay out of the repository; `requirements.txt` gained `psycopg2-binary`, `dj-database-url`, and `python-dotenv`.

Evidence: `manage.py migrate` was run first against a local PostgreSQL 18 instance and then against the Supabase project itself; all 19 migrations applied without modification in both cases.

Consequences for the rules from the section above:

- The business rule "confirmed reservations for the same resource must not overlap" is now enforced by a **partial unique index** (`unique_confirmed_resource_date`) instead of SQLite's partial index. The service-level check stays as a friendly error message; the constraint remains the last line of defence.
- The stated upgrade trigger ("PostgreSQL for higher concurrency") is now met, so the concurrency model can be revisited next.
- Tests keep running on SQLite locally, so `manage.py test` never touches the shared database.
- Draft expiry, notifications, and the missing capacity numbers are still out of scope, exactly as decided above.
