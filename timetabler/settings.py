"""
timetabler/settings.py
=======================
Production-ready Django settings for the Timetabler project.
  - Framework : Django 5.x+
  - Database  : PostgreSQL via DATABASE_URL
  - Auth      : Session + Token (DRF)
  - CORS      : django-cors-headers
  - API Docs  : drf-spectacular (Swagger / ReDoc)
  - Target    : TVET colleges / polytechnics (Kenya)
  - Hosting   : Render (backend) + Vercel (frontend)

Required environment variables (set in Render Dashboard → Environment):
  DJANGO_SECRET_KEY         — long random string, never commit this
  DJANGO_DEBUG              — "False" in production
  DJANGO_ALLOWED_HOSTS      — comma-separated, e.g. timetabler-cr5d.onrender.com
  DATABASE_URL              — postgres://user:pass@host:port/dbname
  GROQ_API_KEY              — your Groq API key (gsk_...)
  CORS_ALLOWED_ORIGINS      — comma-separated frontend origins, e.g. https://yourapp.vercel.app
"""

import os
import sys
from pathlib import Path
import dj_database_url
from dotenv import load_dotenv

# ── Paths ──────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env for local development only — Render injects env vars directly.
load_dotenv(dotenv_path=BASE_DIR / ".env", override=False)


# ── Helper ─────────────────────────────────────────────────────────────────
def env(key, default=None, required=False):
    """Read an environment variable, optionally asserting it exists."""
    value = os.environ.get(key, default)
    if required and not value:
        print(f"[settings] FATAL: environment variable '{key}' is not set.", file=sys.stderr)
        sys.exit(1)
    return value


# ── Core secrets ───────────────────────────────────────────────────────────
SECRET_KEY = env(
    "DJANGO_SECRET_KEY",
    required=True,          # Hard-fail at startup if missing in production
    default="django-insecure-local-dev-only-change-me",
)

GROQ_API_KEY = env("GROQ_API_KEY", required=False, default="")
if not GROQ_API_KEY:
    import warnings
    warnings.warn("[settings] GROQ_API_KEY is not set — AI chat will not work.", RuntimeWarning)


# ── Debug ──────────────────────────────────────────────────────────────────
# Render sets DJANGO_DEBUG=False; locally it defaults to True.
DEBUG = env("DJANGO_DEBUG", default="True").strip().lower() in ("true", "1", "yes")


# ── Allowed Hosts ─────────────────────────────────────────────────────────
# Always includes the Render internal health-check host.
_raw_hosts = env(
    "DJANGO_ALLOWED_HOSTS",
    default="localhost,127.0.0.1",
)
ALLOWED_HOSTS = [h.strip() for h in _raw_hosts.split(",") if h.strip()]

# Render sends health-checks from the internal hostname — always allow it.
RENDER_EXTERNAL_HOSTNAME = env("RENDER_EXTERNAL_HOSTNAME")   # auto-set by Render
if RENDER_EXTERNAL_HOSTNAME and RENDER_EXTERNAL_HOSTNAME not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)

# Safety net: never run in production with an empty ALLOWED_HOSTS
if not DEBUG and not ALLOWED_HOSTS:
    sys.exit("[settings] FATAL: ALLOWED_HOSTS is empty in production.")


# ── Installed Apps ─────────────────────────────────────────────────────────
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "rest_framework",
    "rest_framework.authtoken",
    "corsheaders",
    "drf_spectacular",
    # Project app
    "timetable",
]


# ── Middleware ─────────────────────────────────────────────────────────────
MIDDLEWARE = [
    "timetabler.db_retry_middleware.DBRetryMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",       # Serve static files on Render
    "corsheaders.middleware.CorsMiddleware",            # Must be before CommonMiddleware
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


# ── URL & WSGI ─────────────────────────────────────────────────────────────
ROOT_URLCONF     = "timetabler.urls"
WSGI_APPLICATION = "timetabler.wsgi.application"


# ── Templates ──────────────────────────────────────────────────────────────
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]


# ── Database ───────────────────────────────────────────────────────────────
_DATABASE_URL = env("DATABASE_URL")

if _DATABASE_URL:
    DATABASES = {
        "default": dj_database_url.config(
            default=_DATABASE_URL,
            conn_max_age=60,
            ssl_require=not DEBUG,      # Require SSL in production only
        )
    }
else:
    # Local fallback — mirrors .env values
    DATABASES = {
        "default": {
            "ENGINE":   "django.db.backends.postgresql",
            "NAME":     env("DB_NAME",     default="tani-africa"),
            "USER":     env("DB_USER",     default="postgres"),
            "PASSWORD": env("DB_PASSWORD", default=""),
            "HOST":     env("DB_HOST",     default="localhost"),
            "PORT":     env("DB_PORT",     default="5432"),
            "CONN_MAX_AGE": 60,
            "OPTIONS":  {"connect_timeout": 10},
        }
    }

# Connection keep-alive — applied regardless of which branch was taken above
DATABASES["default"].setdefault("OPTIONS", {})
DATABASES["default"]["CONN_MAX_AGE"] = 60
DATABASES["default"]["OPTIONS"].update({
    "connect_timeout": 10,
    "keepalives":          1,
    "keepalives_idle":     30,
    "keepalives_interval": 10,
    "keepalives_count":    5,
})


# ── CORS ───────────────────────────────────────────────────────────────────
_raw_origins = env(
    "CORS_ALLOWED_ORIGINS",
    default="http://localhost:3000,http://localhost:5173",
)
CORS_ALLOWED_ORIGINS = [o.strip() for o in _raw_origins.split(",") if o.strip()]

# In production, never allow all origins — rely on the explicit list above.
CORS_ALLOW_ALL_ORIGINS = DEBUG

CORS_ALLOW_CREDENTIALS = True
CORS_EXPOSE_HEADERS    = ["Content-Type", "Authorization"]
CORS_ALLOW_HEADERS     = [
    "accept",
    "authorization",
    "content-type",
    "origin",
    "x-requested-with",
]


# ── Security ───────────────────────────────────────────────────────────────
SESSION_COOKIE_SECURE           = not DEBUG
CSRF_COOKIE_SECURE              = not DEBUG
SECURE_BROWSER_XSS_FILTER       = True
SECURE_CONTENT_TYPE_NOSNIFF     = True
X_FRAME_OPTIONS                 = "DENY"
SECURE_HSTS_SECONDS             = 0 if DEBUG else 31_536_000   # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS  = not DEBUG
SECURE_HSTS_PRELOAD             = not DEBUG

# Trust Render's reverse proxy so HTTPS is detected correctly
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")


# ── Password Validation ────────────────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# ── Internationalisation ───────────────────────────────────────────────────
LANGUAGE_CODE = "en-us"
TIME_ZONE     = "Africa/Nairobi"
USE_I18N      = True
USE_TZ        = True


# ── Static & Media Files ───────────────────────────────────────────────────
STATIC_URL  = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# WhiteNoise: serve compressed static files efficiently without a CDN
STATICFILES_STORAGE = (
    "django.contrib.staticfiles.storage.StaticFilesStorage"
    if DEBUG
    else "whitenoise.storage.CompressedManifestStaticFilesStorage"
)

MEDIA_URL   = "/media/"
MEDIA_ROOT  = BASE_DIR / "mediafiles"


# ── Django REST Framework ──────────────────────────────────────────────────
REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.TokenAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.FormParser",
        "rest_framework.parsers.MultiPartParser",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 100,
    "EXCEPTION_HANDLER": "timetable.exceptions.custom_exception_handler",
}


# ── drf-spectacular ────────────────────────────────────────────────────────
SPECTACULAR_SETTINGS = {
    "TITLE":       "Timetabler API",
    "DESCRIPTION": "Automated timetabling system for TVET colleges and polytechnics (Kenya).",
    "VERSION":     "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SWAGGER_UI_SETTINGS": {
        "deepLinking":          True,
        "persistAuthorization": True,
        "displayOperationId":   True,
    },
    "SCHEMA_PATH_PREFIX":      r"/api/",
    "COMPONENT_SPLIT_REQUEST": True,
    "SORT_OPERATIONS":         False,
}


# ── Logging ────────────────────────────────────────────────────────────────
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style":  "{",
        },
        "simple": {
            "format": "{levelname} {asctime} {message}",
            "style":  "{",
        },
    },
    "handlers": {
        "console": {
            "class":     "logging.StreamHandler",
            "formatter": "verbose" if DEBUG else "simple",
        },
    },
    "root": {
        "handlers": ["console"],
        "level":    "WARNING",
    },
    "loggers": {
        "timetable": {
            "handlers":  ["console"],
            "level":     "DEBUG" if DEBUG else "INFO",
            "propagate": False,
        },
        "django.request": {
            "handlers":  ["console"],
            "level":     "ERROR",
            "propagate": False,
        },
        "django.db.backends": {
            "handlers":  ["console"],
            "level":     "WARNING",
            "propagate": False,
        },
    },
}


# ── Default primary key ────────────────────────────────────────────────────
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"