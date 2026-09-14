# Imagem de PRODUÇÃO do Jornal Escolar (docs/24, "Dockerfile").
#
# Construída a partir da raiz do repositório:
#   docker build -f infra/Dockerfile -t jornal-escolar .
# Para os dois tipos de processador (home lab x86 e Oracle ARM), veja "make build" e docs/34.
#
# Três etapas:
#   1. frontend: Node gera o CSS e o JS finais (Vite + Tailwind).
#   2. deps:     uv instala as dependências Python travadas no uv.lock.
#   3. final:    Python + dependências + código + arquivos estáticos. Sem Node, sem uv.

# --- 1. Frontend ------------------------------------------------------------------------------
# $BUILDPLATFORM: o CSS e o JS gerados são iguais em qualquer processador, então esta etapa roda
# na arquitetura de quem constrói (rápido) mesmo quando a imagem final é para ARM.
FROM --platform=$BUILDPLATFORM node:24-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
# O Tailwind procura as classes usadas nos templates e nos apps (@source em src/css).
COPY backend/templates /app/backend/templates
COPY backend/apps /app/backend/apps
RUN npm run build

# --- 2. Dependências Python --------------------------------------------------------------------
FROM python:3.13-slim AS deps
COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv
WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# --- 3. Imagem final ---------------------------------------------------------------------------
FROM python:3.13-slim AS final

LABEL org.opencontainers.image.title="Jornal Escolar" \
      org.opencontainers.image.source="https://github.com/mfelipedias/jornal_escolar"

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=config.settings.prod \
    STATIC_ROOT=/app/staticfiles \
    MEDIA_ROOT=/data/media

# Usuário sem privilégios de administrador: se alguém explorar uma falha no site,
# não ganha controle do container.
RUN groupadd --system --gid 1000 jornal \
    && useradd --system --uid 1000 --gid jornal --home-dir /app --shell /usr/sbin/nologin jornal

WORKDIR /app/backend
COPY --from=deps /opt/venv /opt/venv
COPY VERSION /app/VERSION
COPY backend/ /app/backend/
COPY --from=frontend /app/backend/static/dist /app/backend/static/dist
COPY infra/scripts/entrypoint.sh infra/scripts/healthcheck.py /app/

# collectstatic junta os estáticos do projeto, do admin e do Vite em /app/staticfiles.
# Os valores abaixo existem só para o Django carregar as configurações durante o build.
RUN SECRET_KEY=somente-build DATABASE_URL=postgres://build@localhost/build \
    python manage.py collectstatic --noinput \
    && chmod +x /app/entrypoint.sh \
    && mkdir -p /data/media /data/static \
    && chown -R jornal:jornal /data

USER jornal
EXPOSE 8000

# O Compose também usa este teste para saber quando o site está pronto.
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD ["python", "/app/healthcheck.py"]

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["gunicorn"]
