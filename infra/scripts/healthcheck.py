"""Teste de saúde do container "web" (HEALTHCHECK do infra/Dockerfile).

Pede /healthz/ ao Gunicorn dentro do próprio container. Sai com 0 se o site responde "ok" e
com 1 se não responde, o banco caiu ou faltam migrações. O Docker marca o container como
"healthy" ou "unhealthy" a partir disso.

O cabeçalho Host usa o primeiro endereço de ALLOWED_HOSTS: o Django recusa qualquer outro.
"""

import json
import os
import sys
import urllib.request


def host() -> str:
    for item in os.environ.get("ALLOWED_HOSTS", "").split(","):
        item = item.strip().lstrip(".")
        if item and item != "*":
            return item
    return "localhost"


def main() -> int:
    request = urllib.request.Request(
        "http://127.0.0.1:8000/healthz/",
        headers={"Host": host(), "X-Forwarded-Proto": "https"},
    )
    try:
        with urllib.request.urlopen(request, timeout=4) as response:
            data = json.load(response)
    except Exception as error:  # qualquer falha conta como "fora do ar"
        print(f"healthz falhou: {error}")
        return 1
    return 0 if data.get("status") == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
