#!/bin/sh
# Primeiro programa que roda quando o container "web" de produção liga (infra/Dockerfile).
#
# Com o comando padrão ("gunicorn"):
#   1. copia os arquivos estáticos da imagem para o volume que o Caddy entrega em /static/;
#   2. aplica as migrações do banco e cria a tabela do cache compartilhado (se faltar);
#   3. liga o Gunicorn, o servidor que executa o Django.
# Qualquer outro comando roda direto, por exemplo:
#   docker compose -f infra/docker-compose.yml run --rm web python manage.py createsuperuser
set -eu

if [ "${1:-}" = "gunicorn" ]; then
    if [ -d /data/static ]; then
        # Cópia por cima: arquivos novos entram e os antigos continuam servindo quem ainda
        # está com a página velha aberta. Os arquivos do Vite têm nome com hash e são pequenos.
        cp -R /app/staticfiles/. /data/static/
    fi

    python manage.py migrate --noinput
    python manage.py createcachetable

    exec gunicorn config.wsgi:application \
        --bind 0.0.0.0:8000 \
        --workers "${GUNICORN_WORKERS:-3}" \
        --timeout "${GUNICORN_TIMEOUT:-60}" \
        --max-requests 1000 \
        --max-requests-jitter 100 \
        --access-logfile - \
        --error-logfile -
fi

exec "$@"
