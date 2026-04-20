from pathlib import Path
import os
from urllib.parse import urlparse

# -----------------------------
# PATHS
# -----------------------------
BASE_DIR = Path(__file__).resolve().parent.parent.parent


def _load_local_env() -> None:
    """
    Minimal .env loader so local configuration can be provided without
    introducing a new dependency.
    """
    env_path = BASE_DIR / "siloxr" / "settings" / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in (value or "").split(",") if item.strip()]


def _origin_from_url(value: str) -> str:
    parsed = urlparse((value or "").strip())
    if not parsed.scheme or not parsed.netloc:
        return ""
    return f"{parsed.scheme}://{parsed.netloc}"


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if not item or item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered


_load_local_env()


# -----------------------------
# SECURITY
# -----------------------------
SECRET_KEY = "REPLACE-IN-PRODUCTION"

DEBUG = False

ALLOWED_HOSTS = []


# -----------------------------
# APPLICATIONS
# -----------------------------
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "corsheaders",
]

LOCAL_APPS = [
    "apps.core",
    "apps.inventory",
    "apps.api",
    "apps.notifications",
    "apps.billing",
    "apps.engine",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# siloxr/settings/base.py — add
FRONTEND_BASE_URL = os.environ.get("FRONTEND_BASE_URL", "http://127.0.0.1:3000")
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.environ.get("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "true").lower() == "true"
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", EMAIL_HOST_USER or "noreply@siloxr.com")
PAYSTACK_SECRET_KEY = os.environ.get("PAYSTACK_SECRET_KEY", "")
PAYSTACK_PUBLIC_KEY = os.environ.get("PAYSTACK_PUBLIC_KEY", "")
PAYSTACK_CALLBACK_URL = os.environ.get("PAYSTACK_CALLBACK_URL", f"{FRONTEND_BASE_URL.rstrip('/')}/billing/upgrade")
PAYSTACK_PRO_MONTHLY_NAIRA = int(os.environ.get("PAYSTACK_PRO_MONTHLY_NAIRA", "10000"))
# -----------------------------
# MIDDLEWARE
# -----------------------------
MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


# -----------------------------
# URLS / WSGI
# -----------------------------
ROOT_URLCONF = "siloxr.urls"
WSGI_APPLICATION = "siloxr.wsgi.application"


# -----------------------------
# DATABASE
# -----------------------------
DB_BACKEND = os.environ.get("DB_BACKEND", "sqlite").strip().lower()

if DB_BACKEND == "postgres":
    postgres_host = os.environ.get("POSTGRES_HOST", "127.0.0.1")
    default_conn_max_age = "0" if "pooler.supabase.com" in postgres_host else "60"
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("POSTGRES_DB", "siloxr"),
            "USER": os.environ.get("POSTGRES_USER", "siloxr"),
            "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
            "HOST": postgres_host,
            "PORT": os.environ.get("POSTGRES_PORT", "5432"),
            "CONN_MAX_AGE": int(os.environ.get("POSTGRES_CONN_MAX_AGE", default_conn_max_age)),
            "CONN_HEALTH_CHECKS": _env_bool("POSTGRES_CONN_HEALTH_CHECKS", True),
            "DISABLE_SERVER_SIDE_CURSORS": _env_bool(
                "POSTGRES_DISABLE_SERVER_SIDE_CURSORS",
                "pooler.supabase.com" in postgres_host,
            ),
            "OPTIONS": {
                "sslmode": os.environ.get("POSTGRES_SSLMODE", "prefer"),
            },
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / os.environ.get("SQLITE_NAME", "db.sqlite3"),
        }
    }


# -----------------------------
# AUTH
# -----------------------------
AUTH_USER_MODEL = "core.User"


# -----------------------------
# PASSWORD VALIDATION
# -----------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# -----------------------------
# INTERNATIONALIZATION
# -----------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
BUSINESS_BRIEF_TIMEZONE = os.environ.get("BUSINESS_BRIEF_TIMEZONE", "Africa/Lagos")
BUSINESS_DAY_START_HOUR = int(os.environ.get("BUSINESS_DAY_START_HOUR", "8"))
BUSINESS_DAY_CLOSE_HOUR = int(os.environ.get("BUSINESS_DAY_CLOSE_HOUR", "18"))
BUSINESS_BRIEF_WINDOW_MINUTES = int(os.environ.get("BUSINESS_BRIEF_WINDOW_MINUTES", "90"))


# -----------------------------
# STATIC FILES
# -----------------------------
STATIC_URL = "static/"


# -----------------------------
# DEFAULT PK
# -----------------------------
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# -----------------------------
# DRF CONFIG
# -----------------------------
# backend/siloxr/settings/base.py  — update REST_FRAMEWORK block

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "apps.api.pagination.StandardPagePagination",
    "PAGE_SIZE": 25,
}
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],  # you can add custom template dirs later
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

# backend/siloxr/settings/base.py  — add these to the bottom

from datetime import timedelta

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME":  timedelta(hours=8),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=30),
    "ROTATE_REFRESH_TOKENS":  True,
    "AUTH_HEADER_TYPES":      ("Bearer",),
}

CORS_ALLOWED_ORIGINS = _dedupe(
    _split_csv(os.environ.get("CORS_ALLOWED_ORIGINS", ""))
    + [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        _origin_from_url(FRONTEND_BASE_URL),
        "https://siloxr.com",
        "https://www.siloxr.com",
    ]
)

CORS_ALLOW_CREDENTIALS = True
