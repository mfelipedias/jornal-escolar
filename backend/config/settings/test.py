from .base import *  # noqa: F403

DEBUG = False
ALLOWED_HOSTS = ["testserver", "localhost"]

# Hash de senha rápido: os testes criam muitos usuários.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
