from .base import *  # noqa: F403
from .base import DJANGO_VITE

DEBUG = False
ALLOWED_HOSTS = ["testserver", "localhost"]

# Hash de senha rápido: os testes criam muitos usuários.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Os testes não dependem do build do frontend: só geram as tags apontando para o Vite.
DJANGO_VITE["default"]["dev_mode"] = True

# Os testes nunca chamam a API de clima; quem precisa do bloco simula a resposta.
WEATHER_API_BASE = ""

# A coleta de notícias nos testes usa httpx.MockTransport e endereços falsos, sem DNS.
CURATION_BLOCK_PRIVATE_HOSTS = False
