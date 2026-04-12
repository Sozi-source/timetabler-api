import os
from pathlib import Path
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-your-secret-key-here')
DEBUG = os.getenv('DEBUG', 'False') == 'True'

# Dynamic ALLOWED_HOSTS for Render
RENDER_EXTERNAL_HOSTNAME = os.getenv('RENDER_EXTERNAL_HOSTNAME', '')
ALLOWED_HOSTS = [
    'localhost',
    '127.0.0.1',
    'timetabler-cr5d.onrender.com',
]
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)

CSRF_TRUSTED_ORIGINS = [
    'https://timetabler-cr5d.onrender.com',
]
if RENDER_EXTERNAL_HOSTNAME:
    CSRF_TRUSTED_ORIGINS.append(f"https://{RENDER_EXTERNAL_HOSTNAME}")

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third party apps
    'rest_framework',
    'corsheaders',
    'django_filters',
    'import_export',
    'drf_spectacular',

    # Local app
    'timetable',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'timetabler.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'timetabler.wsgi.application'

# Database — uses DATABASE_URL env var on Render, SQLite locally
import dj_database_url

DATABASE_URL = os.getenv('DATABASE_URL')
if DATABASE_URL:
    DATABASES = {
        'default': dj_database_url.config(default=DATABASE_URL, conn_max_age=600, ssl_require=True)
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# Cache - Use database cache for production, local memory for development
if DATABASE_URL:
    # Create cache table with: python manage.py createcachetable
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
            'LOCATION': 'django_cache_table',
        }
    }
else:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'unique-snowflake',
        }
    }

# REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.BasicAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_FILTER_BACKENDS': (
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 50,
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/day',
        'user': '1000/day',
    },
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

# DRF Spectacular (API docs)
SPECTACULAR_SETTINGS = {
    'TITLE': '📅 Timetable Management System',
    'DESCRIPTION': '''
## Overview
A comprehensive API for managing academic timetables for certificate and diploma programmes.

## Features
- 🏫 **Academic Structure** — Years, Semesters, Departments, Programmes
- 👨‍🏫 **Resource Management** — Lecturers, Rooms, Intakes
- 🤖 **AI-Powered Scheduling** — Automated generation with OR-Tools + AI
- ⚠️ **Conflict Detection** — Automatic detection and resolution
- 📄 **Export** — PDF and Excel reports
- 🔴 **Real-time Updates** — WebSocket support

## Authentication
1. Login via [/admin/](/admin/) with your credentials
2. Session cookie is used automatically for all requests

## Base URL
`https://timetabler-cr5d.onrender.com/api/`
    ''',
    'VERSION': 'v1',
    'SERVE_INCLUDE_SCHEMA': False,
    'CONTACT': {'email': 'admin@college.edu'},
    'LICENSE': {'name': 'MIT License'},
    'TAGS': [
        {'name': 'academic-years', 'description': 'Manage academic years'},
        {'name': 'semesters', 'description': 'Manage semesters (Jan-Apr, May-Aug, Sep-Dec)'},
        {'name': 'departments', 'description': 'Manage academic departments'},
        {'name': 'programmes', 'description': 'Manage Certificate and Diploma programmes'},
        {'name': 'stages', 'description': 'Manage stages/years of study'},
        {'name': 'units', 'description': 'Manage academic units/subjects'},
        {'name': 'intakes', 'description': 'Manage student intake cohorts'},
        {'name': 'lecturers', 'description': 'Manage teaching staff'},
        {'name': 'rooms', 'description': 'Manage teaching venues'},
        {'name': 'time-slots', 'description': 'View available time slots'},
        {'name': 'timetable-entries', 'description': 'View and manage timetable entries'},
        {'name': 'conflicts', 'description': 'Detect and resolve scheduling conflicts'},
        {'name': 'timetable', 'description': 'Master and personal timetable views'},
        {'name': 'schedule', 'description': 'Generate and publish schedules'},
        {'name': 'export', 'description': 'Export timetables to PDF and Excel'},
        {'name': 'dashboard', 'description': 'Statistics and analytics'},
        {'name': 'websocket', 'description': 'Real-time WebSocket token'},
    ],
    'SWAGGER_UI_SETTINGS': {
        'deepLinking': True,
        'persistAuthorization': True,
        'displayOperationId': False,
        'defaultModelsExpandDepth': 1,
        'defaultModelExpandDepth': 2,
        'docExpansion': 'list',
        'filter': True,
        'showExtensions': True,
        'showCommonExtensions': True,
        'tryItOutEnabled': True,
    },
    'SWAGGER_UI_FAVICON_HREF': 'https://www.svgrepo.com/show/374049/django.svg',
    'REDOC_UI_SETTINGS': {
        'hideDownloadButton': False,
        'expandResponses': '200,201',
        'pathInMiddlePanel': True,
    },
    'COMPONENT_SPLIT_REQUEST': True,
    'SORT_OPERATIONS': False,
}

# CORS Settings
CORS_ALLOWED_ORIGINS = [
    'http://localhost:3000',
    'http://127.0.0.1:3000',
    'https://timetabler-cr5d.onrender.com',
]
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HTTP_OPTIONS = True

# Static & Media Files
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Create directories
os.makedirs(STATIC_ROOT, exist_ok=True)
os.makedirs(MEDIA_ROOT, exist_ok=True)
os.makedirs(BASE_DIR / 'logs', exist_ok=True)
os.makedirs(BASE_DIR / 'templates', exist_ok=True)

# Email Settings
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# For production email (uncomment when ready):
# if not DEBUG:
#     EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
#     EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
#     EMAIL_PORT = int(os.getenv('EMAIL_PORT', 587))
#     EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
#     EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
#     EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True') == 'True'

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {asctime} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': True,
        },
        'timetable': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': True,
        },
    },
}

# Security Settings for Production
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    X_FRAME_OPTIONS = 'DENY'

# Custom Settings
SEMESTER_MONTHS = {
    'JAN_APR': {'start_month': 1, 'end_month': 4, 'name': 'January-April'},
    'MAY_AUG': {'start_month': 5, 'end_month': 8, 'name': 'May-August'},
    'SEP_DEC': {'start_month': 9, 'end_month': 12, 'name': 'September-December'},
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
LOGIN_URL = '/admin/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'