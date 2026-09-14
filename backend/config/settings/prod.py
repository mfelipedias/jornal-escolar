from .base import *  # noqa: F403
from .base import env

DEBUG = False

# HTTPS termina na Cloudflare; o Caddy repassa o esquema original (docs/24).
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=60 * 60 * 24 * 30)
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
# Avisos do check --deploy silenciados de propósito (docs/23, checklist da E28): o jornal é um
# subdomínio, e HSTS para todos os subdomínios ou a lista "preload" dos navegadores valeriam
# para o domínio inteiro, que tem outros sites. O HSTS do próprio jornal continua ligado.
SILENCED_SYSTEM_CHECKS = ["security.W005", "security.W021"]
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REDIRECT_EXEMPT = [r"^healthz/$"]  # healthcheck interno do Compose usa HTTP

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True

# Sem e-mail (docs/05 D8): erros e avisos vão para a saída do container, que o Docker guarda.
# Ver com: make prod-logs
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simples": {"format": "{asctime} {levelname} {name}: {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "simples"},
    },
    "root": {"handlers": ["console"], "level": env.str("LOG_LEVEL", default="INFO")},
    "loggers": {
        "django": {"handlers": ["console"], "level": "WARNING", "propagate": False},
    },
}
