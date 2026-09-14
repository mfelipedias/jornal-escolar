"""Configurações comuns a todos os ambientes.

Valores que mudam entre máquinas ou são secretos vêm de variáveis de ambiente
(django-environ). Em desenvolvimento, eles são lidos de infra/env/.env.
"""

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # backend/
REPO_DIR = BASE_DIR.parent

env = environ.Env()
ENV_FILE = Path(env.str("DJANGO_ENV_FILE", default=str(REPO_DIR / "infra" / "env" / ".env")))
if ENV_FILE.is_file():
    # Variáveis já definidas no ambiente (ex.: pelo Docker Compose) têm prioridade.
    environ.Env.read_env(ENV_FILE)


def _read_version() -> str:
    version_file = REPO_DIR / "VERSION"
    if version_file.is_file():
        return version_file.read_text(encoding="utf-8").strip()
    return env.str("APP_VERSION", default="0.0.0")


APP_VERSION = _read_version()

SECRET_KEY = env.str("SECRET_KEY")
DEBUG = env.bool("DEBUG", default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[])
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])
SITE_URL = env.str("SITE_URL", default="http://localhost:8000")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "django.contrib.sitemaps",
    "django_vite",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.microsoft",
    "apps.core",
    "apps.accounts",
    "apps.taxonomy",
    "apps.publications",
    "apps.editorial",
    "apps.dashboard",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "apps.core.middleware.HtmxMessagesMiddleware",
    "apps.core.middleware.AppVersionHeaderMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

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
                "apps.core.context_processors.site",
                "apps.taxonomy.context_processors.navigation",
                "apps.editorial.context_processors.notifications",
            ],
        },
    },
]

DATABASES = {"default": env.db("DATABASE_URL")}
DATABASES["default"]["CONN_MAX_AGE"] = env.int("CONN_MAX_AGE", default=60)
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "accounts.User"

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --- Autenticação (docs/05 D7, docs/23) ---
# Só a equipe tem conta, criada pelo admin. Entrada pela Microsoft ou por senha de reserva.
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

SESSION_COOKIE_AGE = 60 * 60 * 24 * 14  # 14 dias...
SESSION_SAVE_EVERY_REQUEST = True  # ...contados a partir do último uso
SESSION_COOKIE_SAMESITE = "Lax"

ACCOUNT_ADAPTER = "apps.accounts.adapters.AccountAdapter"
SOCIALACCOUNT_ADAPTER = "apps.accounts.adapters.SocialAccountAdapter"
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*"]
ACCOUNT_EMAIL_VERIFICATION = "none"  # sem serviço de e-mail (docs/05 D8)
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_SESSION_REMEMBER = True
ACCOUNT_LOGOUT_ON_GET = False
# 5 erros por e-mail em 15 min. Por IP o limite é maior: a escola inteira sai pelo mesmo IP,
# e 5 erros de uma pessoa não podem bloquear todos os professores (docs/23).
ACCOUNT_RATE_LIMITS = {"login_failed": "30/15m/ip,5/15m/key"}
# Atrás da Cloudflare o IP real vem neste cabeçalho (definir só em produção, docs/24).
ALLAUTH_TRUSTED_CLIENT_IP_HEADER = env.str("TRUSTED_CLIENT_IP_HEADER", default="") or None
SOCIALACCOUNT_STORE_TOKENS = False
SOCIALACCOUNT_EMAIL_AUTHENTICATION = False  # a ligação com a conta é feita pelo adaptador

# Domínios aceitos no login Microsoft. Só entram contas já cadastradas pelo admin.
AUTH_ALLOWED_DOMAINS = [
    domain.strip().lower()
    for domain in env.list(
        "AUTH_ALLOWED_DOMAINS", default=["professor.educacao.sp.gov.br", "educacao.sp.gov.br"]
    )
    if domain.strip()
]
MS_CLIENT_ID = env.str("MS_CLIENT_ID", default="")
MS_CLIENT_SECRET = env.str("MS_CLIENT_SECRET", default="")
MICROSOFT_LOGIN_CONFIGURED = bool(MS_CLIENT_ID and MS_CLIENT_SECRET)
SOCIALACCOUNT_PROVIDERS = {
    "microsoft": {
        "TENANT": "organizations",
        "SCOPE": ["User.Read"],
        "APPS": (
            [
                {
                    "client_id": MS_CLIENT_ID,
                    "secret": MS_CLIENT_SECRET,
                    "settings": {"tenant": "organizations"},
                }
            ]
            if MICROSOFT_LOGIN_CONFIGURED
            else []
        ),
    }
}

LANGUAGE_CODE = "pt-br"
LANGUAGES = [("pt-br", "Português (Brasil)")]
LOCALE_PATHS = [BASE_DIR / "locale"]
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = Path(env.str("STATIC_ROOT", default=str(BASE_DIR / "staticfiles")))
STATICFILES_DIRS = [BASE_DIR / "static"]

# CSS e JS gerados pelo Vite a partir de frontend/ (docs/08, "Fluxo de assets").
# Em modo dev, as páginas carregam direto do servidor do Vite (make assets-dev).
DJANGO_VITE = {
    "default": {
        "dev_mode": env.bool("VITE_DEV_MODE", default=False),
        "dev_server_port": 5173,
        "static_url_prefix": "dist",
        "manifest_path": BASE_DIR / "static" / "dist" / "manifest.json",
    }
}

MEDIA_URL = env.str("MEDIA_URL", default="/media/")
MEDIA_ROOT = Path(env.str("MEDIA_ROOT", default=str(BASE_DIR / "media")))

# Uploads de imagem (docs/23, "Uploads")
MEDIA_MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MEDIA_MAX_DIMENSION = 6000
MEDIA_USER_QUOTA_BYTES = 1024 * 1024 * 1024
MEDIA_UPLOADS_PER_HOUR = 60
EDITOR_MAX_BODY_BYTES = 1_000_000  # autosave do editor (docs/16)
DATA_UPLOAD_MAX_MEMORY_SIZE = 2_621_440  # corpo não-arquivo (padrão do Django)
FILE_UPLOAD_MAX_MEMORY_SIZE = MEDIA_MAX_UPLOAD_BYTES + 1024 * 1024
