import os
import sys
from pathlib import Path
from urllib.parse import urlparse

import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Local, git-ignored configuration.
load_dotenv(BASE_DIR / ".env")


def _env_bool(name: str, default: bool = False) -> bool:
    """Read a boolean environment variable."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_list(name: str) -> list[str]:
    """Read a comma separated environment variable into a list."""
    return [item.strip() for item in os.environ.get(name, "").split(",") if item.strip()]


SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "django-insecure-first-version-office-reservation-system")
DEBUG = _env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS: list[str] = _env_list("DJANGO_ALLOWED_HOSTS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "reservations",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "office_reservation_system.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "office_reservation_system.wsgi.application"
ASGI_APPLICATION = "office_reservation_system.asgi.application"

# ---------------------------------------------------------------------------
# Database
#
# - DATABASE_URL set   -> PostgreSQL (Supabase)
# - DATABASE_URL empty -> local SQLite file, so a fresh clone still runs
# - tests              -> always SQLite, because the test runner has to create
#                         and drop a throwaway database, which is not possible
#                         on Supabase and would touch shared data.
# ---------------------------------------------------------------------------
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
RUNNING_TESTS = len(sys.argv) > 1 and sys.argv[1] == "test"

USE_SQLITE = not DATABASE_URL or RUNNING_TESTS or _env_bool("DJANGO_USE_SQLITE")

if USE_SQLITE:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
else:
    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=600,
            conn_health_checks=True,
        )
    }

    # Supabase requires TLS. Add an explicit sslmode for remote databases when
    # the connection string does not carry one. A local PostgreSQL does not
    # have to use TLS, so localhost is left alone.
    _parsed_url = urlparse(DATABASE_URL)
    _db_host = _parsed_url.hostname or ""
    _options = DATABASES["default"].setdefault("OPTIONS", {})
    if "sslmode" not in _options and _db_host not in {"localhost", "127.0.0.1", "::1", ""}:
        _options["sslmode"] = "require"

    # Supabase's connection pooler runs PgBouncer, which cannot keep
    # server-side cursors open between transactions.
    if "pooler.supabase" in _db_host or _parsed_url.port == 6543:
        DATABASES["default"]["DISABLE_SERVER_SIDE_CURSORS"] = True

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Europe/Prague"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "reservations:availability"
LOGOUT_REDIRECT_URL = "login"
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"


