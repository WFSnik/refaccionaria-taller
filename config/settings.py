from decimal import Decimal
from pathlib import Path
from urllib.parse import unquote, urlparse
import os

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]
DEBUG = os.environ.get("DJANGO_DEBUG", "0") == "1"
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

# En Railway el dominio público llega en RAILWAY_PUBLIC_DOMAIN y el HTTPS lo termina su proxy.
EN_RAILWAY = bool(os.environ.get("RAILWAY_ENVIRONMENT"))
CSRF_TRUSTED_ORIGINS = [o for o in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if o]
if os.environ.get("RAILWAY_PUBLIC_DOMAIN"):
    ALLOWED_HOSTS.append(os.environ["RAILWAY_PUBLIC_DOMAIN"])
    CSRF_TRUSTED_ORIGINS.append(f"https://{os.environ['RAILWAY_PUBLIC_DOMAIN']}")
if EN_RAILWAY:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
    SECURE_CONTENT_TYPE_NOSNIFF = True

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "inventario",
    "catalogo",
    "asistente",
    # Módulos del flujo del taller; docs/modulos.md explica cómo se conectan.
    "taller",
    "clientes",
    "mostrador",
    "ventas",
    "almacen",
    "proveedores",
    "contabilidad",
    "sst",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
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
                "inventario.context_processors.alertas_pendientes",
                "taller.context_processors.permisos",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("DB_NAME", "refaccionaria"),
        "USER": os.environ.get("DB_USER", "refaccionaria"),
        "PASSWORD": os.environ.get("DB_PASSWORD", ""),
        "HOST": os.environ.get("DB_HOST", "localhost"),
        "PORT": os.environ.get("DB_PORT", "5432"),
        "CONN_MAX_AGE": 60,
    }
}
# Railway entrega la base como DATABASE_URL.
if os.environ.get("DATABASE_URL"):
    _url = urlparse(os.environ["DATABASE_URL"])
    DATABASES["default"].update(
        NAME=_url.path.lstrip("/"), USER=unquote(_url.username or ""), PASSWORD=unquote(_url.password or ""),
        HOST=_url.hostname, PORT=str(_url.port or 5432),
    )

# Contadores de límites (asistente y accesos) en una tabla, para que los compartan todos los procesos.
CACHES = {"default": {"BACKEND": "django.core.cache.backends.db.DatabaseCache", "LOCATION": "cache_refaccionaria"}}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "es-mx"
TIME_ZONE = "America/Mexico_City"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
# En producción los estáticos llevan hash en el nombre para que el navegador no use versiones viejas.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage" if EN_RAILWAY
        else "django.contrib.staticfiles.storage.StaticFilesStorage"
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "login"

# Avisos de reorden: en desarrollo se imprimen en la consola del servidor.
EMAIL_BACKEND = os.environ.get("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "inventario@refaccionaria.local")
COMPRAS_EMAILS = [e for e in os.environ.get("COMPRAS_EMAILS", "compras@refaccionaria.local").split(",") if e]
SITIO_URL = os.environ.get("SITIO_URL", "http://127.0.0.1:8000").rstrip("/")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"consola": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["consola"], "level": "INFO"},
}

# Tasa que se suma a los precios del presupuesto y la factura.
IVA_TASA = Decimal(os.environ.get("IVA_TASA", "0.16"))

# Asistente de piezas: con ANTHROPIC_API_KEY usa Claude; sin ella, o al pasar el tope diario, contesta en modo básico.
ASISTENTE_MODELO = os.environ.get("ASISTENTE_MODELO", "claude-haiku-5-5")
ASISTENTE_TOPE_DIARIO_USD = float(os.environ.get("ASISTENTE_TOPE_DIARIO_USD", "2"))
# Mensajes por visitante (IP) por minuto, hora y día.
ASISTENTE_LIMITES_IP = [int(n) for n in os.environ.get("ASISTENTE_LIMITES_IP", "8,40,100").split(",")]
