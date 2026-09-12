from .base import *  # noqa: F403
from .base import DJANGO_VITE, env

DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "0.0.0.0"]

# Por padrão usa o servidor do Vite (make assets-dev). Com VITE_DEV_MODE=False usa o build.
DJANGO_VITE["default"]["dev_mode"] = env.bool("VITE_DEV_MODE", default=True)
