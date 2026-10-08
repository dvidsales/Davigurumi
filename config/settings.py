"""Production fails closed; manage.py explicitly defaults to local development."""

import os
import re
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
DEBUG = os.getenv("DJANGO_DEBUG", "0") == "1"
SECRET_KEY = os.getenv(
    "DJANGO_SECRET_KEY", "development-only-do-not-use-in-production-davigurumi"
)
ALLOWED_HOSTS = os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,[::1]").split(
    ","
)
if not DEBUG and (
    not os.getenv("DJANGO_SECRET_KEY") or not os.getenv("DJANGO_ALLOWED_HOSTS")
):
    raise ImproperlyConfigured(
        "Configure DJANGO_SECRET_KEY e DJANGO_ALLOWED_HOSTS para produção."
    )

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "accounts",
    "materials",
    "pricing",
    "purchasing",
    "projects",
    "sales",
    "operations",
    "production",
    "finance",
    "portability",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "accounts.middleware.DevelopmentSecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "accounts.privacy.ErasureGateMiddleware",
    "accounts.demo.DemoMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "config.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]
WSGI_APPLICATION = "config.wsgi.application"
if os.getenv("POSTGRES_DB"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ["POSTGRES_DB"],
            "USER": os.getenv("POSTGRES_USER", "davigurumi"),
            "PASSWORD": os.getenv("POSTGRES_PASSWORD", ""),
            "HOST": os.getenv("POSTGRES_HOST", "localhost"),
            "PORT": os.getenv("POSTGRES_PORT", "5432"),
            "OPTIONS": {"sslmode": os.getenv("POSTGRES_SSLMODE", "require")},
        }
    }
else:
    (BASE_DIR / ".local").mkdir(exist_ok=True)
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / ".local" / "db.sqlite3",
        }
    }
AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if DEBUG and os.getenv("DJANGO_STATIC_MANIFEST", "0") != "1"
            else "whitenoise.storage.CompressedManifestStaticFilesStorage"
        )
    },
}
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
SUPABASE_FILES_BUCKET = os.getenv("SUPABASE_FILES_BUCKET", "davigurumi-files")
SUPABASE_LEDGER_BUCKET = os.getenv("SUPABASE_LEDGER_BUCKET", "davigurumi-erasure")
REMOTE_PRIVATE_STORAGE = os.getenv("DJANGO_REMOTE_STORAGE", "0") == "1"
if REMOTE_PRIVATE_STORAGE:
    STORAGES["default"] = {"BACKEND": "config.storage.SupabasePrivateStorage"}
MEDIA_ROOT = Path(os.getenv("DJANGO_MEDIA_ROOT", str(BASE_DIR / ".local" / "files")))
MAX_PRIVATE_IMAGES_PER_USER = 100
MAX_IMAGES_PER_QUOTE = 10
PUBLIC_SIGNUP_ENABLED = os.getenv("DJANGO_PUBLIC_SIGNUP", "1" if DEBUG else "0") == "1"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "login"
EMAIL_BACKEND = os.getenv(
    "DJANGO_EMAIL_BACKEND",
    (
        "django.core.mail.backends.console.EmailBackend"
        if DEBUG
        else "django.core.mail.backends.dummy.EmailBackend"
    ),
)
if not DEBUG and EMAIL_BACKEND == "django.core.mail.backends.console.EmailBackend":
    raise ImproperlyConfigured(
        "Console de e-mail não é permitido em produção: links de recuperação não podem ir para logs."
    )
EMAIL_HOST = os.getenv("EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "1") == "1"
EMAIL_TIMEOUT = 10
DEFAULT_FROM_EMAIL = os.getenv(
    "DEFAULT_FROM_EMAIL", "Davigurumi <desenvolvimento@localhost>"
)
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_SSL_REDIRECT = not DEBUG
SECURE_REDIRECT_EXEMPT = [r"^healthz/$"]
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
PRIVATE_UPLOAD_LIMIT = 5 * 1024 * 1024
ARCHIVE_UPLOAD_LIMIT = 50 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 1024 * 1024
DATA_UPLOAD_MAX_NUMBER_FIELDS = 500
DATA_UPLOAD_MAX_NUMBER_FILES = 10
FILE_UPLOAD_MAX_MEMORY_SIZE = 1024 * 1024
FILE_UPLOAD_PERMISSIONS = 0o600
FILE_UPLOAD_DIRECTORY_PERMISSIONS = 0o700
PASSWORD_RESET_TIMEOUT = 3600
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SECURE_HSTS_SECONDS = 0 if DEBUG else int(os.getenv("DJANGO_HSTS_SECONDS", "3600"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
if not DEBUG:
    if (
        len(SECRET_KEY) < 50
        or len(set(SECRET_KEY)) < 5
        or SECRET_KEY.startswith("development-only-")
    ):
        raise ImproperlyConfigured(
            "Use uma chave de produção própria, aleatória e com pelo menos 50 caracteres."
        )
    if any(host == "*" or host.startswith(".") for host in ALLOWED_HOSTS):
        raise ImproperlyConfigured(
            "Use hosts explícitos; wildcard global não é permitido em produção."
        )
PORTAL_READ_RATE_LIMIT = 120
PORTAL_READ_RATE_WINDOW_SECONDS = 60
MAX_IMPORT_PREVIEWS = 20
REPORT_READ_RATE_LIMIT = 60
REPORT_READ_RATE_WINDOW_SECONDS = 60
WRITE_RATE_LIMIT = 120
WRITE_RATE_WINDOW_SECONDS = 60
AUTH_RATE_LIMIT = 15
AUTH_RATE_WINDOW_SECONDS = 900
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {"portal_redaction": {"()": "config.logging.RedactPortalToken"}},
    "handlers": {
        "console": {"class": "logging.StreamHandler", "filters": ["portal_redaction"]}
    },
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "django.server": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "django.request": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
    },
}

# Mount independently from database/media backups in production. Do not rotate
# this key without migrating all signed tombstones.
PRIVACY_LEDGER_DIR = os.getenv(
    "DJANGO_PRIVACY_LEDGER_DIR", str(BASE_DIR / ".local" / "privacy-ledger")
)
PRIVACY_LEDGER_REQUIRED = not DEBUG or bool(os.getenv("DJANGO_PRIVACY_LEDGER_DIR"))
PRIVACY_LEDGER_KEY = os.getenv("DJANGO_PRIVACY_LEDGER_KEY", SECRET_KEY if DEBUG else "")

ACCOUNT_RECORD_LIMITS = {
    "materials.material": 1000,
    "projects.project": 500,
    "sales.client": 1000,
    "sales.quote": 500,
    "purchasing.supplier": 500,
    "purchasing.purchase": 1000,
    "production.order": 500,
    "materials.stockoperation": 5000,
    "projects.projectrevision": 5000,
    "sales.quoteversion": 5000,
}
ACCOUNT_STORAGE_LIMIT = 50 * 1024 * 1024

TRUSTED_PROXY = os.getenv("DJANGO_TRUST_PROXY", "0") == "1"
# Enable only when the host prevents bypassing its trusted reverse proxy.
if TRUSTED_PROXY:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
CSRF_TRUSTED_ORIGINS = [
    value.strip()
    for value in os.getenv("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",")
    if value.strip()
]
POSTGRES_SCHEMA = os.getenv("POSTGRES_SCHEMA", "")
if POSTGRES_SCHEMA:
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", POSTGRES_SCHEMA):
        raise ImproperlyConfigured("Nome de schema PostgreSQL inválido.")
    if DATABASES["default"]["ENGINE"] != "django.db.backends.postgresql":
        raise ImproperlyConfigured("Schema privado exige PostgreSQL.")
    if os.getenv("POSTGRES_SSLROOTCERT"):
        DATABASES["default"]["OPTIONS"]["sslrootcert"] = os.environ[
            "POSTGRES_SSLROOTCERT"
        ]
    DATABASES["default"]["OPTIONS"]["options"] = "-c search_path=" + POSTGRES_SCHEMA
BETA_MODE = os.getenv("DJANGO_BETA_MODE", "0") == "1"
BETA_INVITE_SECRET = os.getenv("DJANGO_BETA_INVITE_SECRET", "")
BETA_EMAILS = {
    value.strip().lower()
    for value in os.getenv("DJANGO_BETA_EMAILS", "").split(",")
    if value.strip()
}
if BETA_MODE:
    if (
        DEBUG
        or PUBLIC_SIGNUP_ENABLED
        or not REMOTE_PRIVATE_STORAGE
        or not TRUSTED_PROXY
    ):
        raise ImproperlyConfigured(
            "Beta exige DEBUG desligado, cadastro público fechado, armazenamento remoto e proxy confiável."
        )
    if len(BETA_INVITE_SECRET) < 32 or not BETA_EMAILS or len(BETA_EMAILS) > 20:
        raise ImproperlyConfigured(
            "Configure uma chave de convites e de 1 a 20 e-mails convidados."
        )
    if not POSTGRES_SCHEMA or POSTGRES_SCHEMA == "public":
        raise ImproperlyConfigured(
            "Beta exige schema PostgreSQL privado, fora da API pública."
        )
    if (
        len(PRIVACY_LEDGER_KEY) < 32
        or PRIVACY_LEDGER_KEY == SECRET_KEY
        or SUPABASE_FILES_BUCKET == SUPABASE_LEDGER_BUCKET
    ):
        raise ImproperlyConfigured(
            "Configure chave e bucket separados para o registro de exclusões."
        )
    ACCOUNT_STORAGE_LIMIT = 10 * 1024 * 1024
    ACCOUNT_RECORD_LIMITS.update(
        {"sales.quote": 100, "projects.project": 100, "production.order": 100}
    )
