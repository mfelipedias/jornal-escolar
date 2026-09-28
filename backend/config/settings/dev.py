from .base import *  # noqa: F403
from .base import DJANGO_VITE, env

DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "0.0.0.0"]

# Por padrão usa o servidor do Vite (make assets-dev). Com VITE_DEV_MODE=False usa o build.
DJANGO_VITE["default"]["dev_mode"] = env.bool("VITE_DEV_MODE", default=True)

# O servidor do Vite injeta estilos e roda em outra porta, o que a CSP bloquearia. Com
# VITE_DEV_MODE=False (arquivos do build, como em produção) a CSP fica ligada para testar.
# Sem e-mail configurado (admin ou .env), os códigos de cadastro aparecem no terminal do Django.
EMAIL_FALLBACK_CONSOLE = True
EMAIL_FORCE_CONFIGURED = True

if DJANGO_VITE["default"]["dev_mode"]:
    CONTENT_SECURITY_POLICY = None
