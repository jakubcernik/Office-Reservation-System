# Office Reservation System

A first-version Django application for office desks and parking spot reservations.

## What is included

- Django project with SQLite storage
- Login/logout via Django authentication
- Availability page for desks and parking spots
- Draft, confirm, and cancel reservation flows
- Django admin for resource and reservation management
- Core business rule: parking confirmation requires a confirmed desk reservation for the same date

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
