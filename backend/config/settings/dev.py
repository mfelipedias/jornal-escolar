from .base import *  # noqa: F403
from .base import DJANGO_VITE, env

DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "0.0.0.0"]

# Por padrão usa o servidor do Vite (make assets-dev). Com VITE_DEV_MODE=False usa o build.
DJANGO_VITE["default"]["dev_mode"] = env.bool("VITE_DEV_MODE", default=True)

# O servidor do Vite injeta estilos e roda em outra porta, o que a CSP bloquearia. Com
# VITE_DEV_MODE=False (arquivos do build, como em produção) a CSP fica ligada para testar.
# Sem Gmail configurado, os e-mails (códigos de cadastro) aparecem no terminal do Django.
if not EMAIL_CONFIGURED:  # noqa: F405
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
    EMAIL_CONFIGURED = True

if DJANGO_VITE["default"]["dev_mode"]:
    CONTENT_SECURITY_POLICY = None
