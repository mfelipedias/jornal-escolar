# 24 — Infraestrutura e deploy

## Domínio e exposição

- Domínio: **`jornal.projetosrosa.com.br`** (subdomínio de domínio próprio já existente).
- DNS e TLS na **Cloudflare**; o servidor é alcançado por **Cloudflare Tunnel** (`cloudflared`), sem portas abertas. HTTPS na borda da Cloudflare; entre `cloudflared` e o Caddy interno o tráfego é HTTP na rede do Docker.
- Dois alvos de hospedagem possíveis, com o mesmo `docker-compose.yml`:

| Alvo | Quando | Observações |
|---|---|---|
| Home lab (Ubuntu, x86, GPUs AMD) | Padrão; necessário para a Fase 5 (IA local) | Depende da energia e da internet da casa |
| Oracle Cloud Free Tier (VM Ampere A1, ARM64, até 4 OCPU e 24 GB) | Se a disponibilidade do home lab for problema, ou como ambiente de homologação | Sem GPU; ARM exige imagens `linux/arm64` |

Decisão: o **banco vive em um só lugar**. Não há replicação entre os dois alvos. Trocar de alvo é restaurar o backup no outro e apontar o túnel. A imagem Docker é construída para `linux/amd64` e `linux/arm64` (`docker buildx`) ou construída no próprio host.

## Serviços (Docker Compose)

| Serviço | Imagem | Fase | Função |
|---|---|---|---|
| `cloudflared` | `cloudflare/cloudflared` | 1 | Túnel para a Cloudflare; encaminha para `caddy:80` |
| `caddy` | `caddy:2` | 1 | Proxy interno: `/media/` do volume com cache, cabeçalhos, `trusted_proxies`, o resto para `web` |
| `web` | imagem própria (Python 3.13 slim) | 1 | Gunicorn + Django; WhiteNoise serve `/static/` |
| `db` | `postgres:17` (Fase 5: `pgvector/pgvector:pg17`) | 1 | Banco |
| `backup` | `alpine` + `postgresql-client` + `rclone` + `supercronic` | 1 | Backup diário |
| `worker` | mesma imagem de `web`, `procrastinate worker` | 4 | Tarefas em segundo plano (coleta RSS, limpezas) |
| `ollama` | `ollama/ollama:rocm` | 5 (congelada) | Modelos locais |

Volumes: `pgdata`, `media`, `caddy_data`. Perfis: `default`, `worker`, `ai`.

Por que manter o Caddy atrás do túnel: servir `/media/` com cache e cabeçalhos corretos sem passar pelo Django, e permitir rodar sem Cloudflare (ex.: rede interna da escola) trocando só o perfil.

## Dockerfile (multi-stage)

1. `node:22-alpine`: instala `frontend/`, roda `vite build`, gera `backend/static/dist/`.
2. `python:3.13-slim`: dependências com `uv` (lock), código, `dist/`, `collectstatic`, usuário não root, `entrypoint.sh` (migrate + gunicorn). Imagem final sem Node. Build multi-arch.

## Configuração

Variáveis de ambiente (`django-environ`), documentadas em `infra/env/.env.example`:

| Variável | Exemplo |
|---|---|
| `DJANGO_SETTINGS_MODULE` | `config.settings.prod` |
| `SECRET_KEY`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` | `jornal.projetosrosa.com.br` |
| `DATABASE_URL` | `postgres://jornal:...@db:5432/jornal` |
| `MEDIA_ROOT`, `MEDIA_URL` | `/data/media`, `/media/` |
| `SITE_URL` | `https://jornal.projetosrosa.com.br` |
| `MS_CLIENT_ID`, `MS_CLIENT_SECRET` | Registro do app na Microsoft; guia em [32](32-guia-login-microsoft.md) |
| `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET` | Backup; guia em [31](31-guia-backup.md) |
| `BACKUP_PASSPHRASE` | Senha que criptografa os backups; guardar fora do servidor |
| `AUTH_ALLOWED_DOMAINS` | `professor.educacao.sp.gov.br,educacao.sp.gov.br` |
| `WEATHER_LAT`, `WEATHER_LON` | `-23.5329`, `-46.7918` (Osasco, SP) (Fase 3) |
| `CLOUDFLARE_TUNNEL_TOKEN` | |
| `EMAIL_URL` | vazio no MVP; serviço gratuito se ligado (Evolução) |
| `AI_*` | Fase 5, congelada |

## Backups

Diário às 3h no container `backup`:

1. `pg_dump -Fc`.
2. `tar` do volume `media` (incremental por data).
3. Criptografa com `age`.
4. `rclone` para **Cloudflare R2** (10 GB grátis, na mesma conta Cloudflare já usada para DNS e túnel). Decidido; guia passo a passo em [31](31-guia-backup.md).
5. Retém 7 diários, 4 semanais, 6 mensais.
6. Verifica o dump com `pg_restore --list`.

`restore.sh` documenta a restauração em servidor limpo (inclusive de x86 para ARM). Teste trimestral.

## Monitoramento mínimo

- `/healthz/` (banco acessível, migrações aplicadas, versão do sistema) usado pelo `healthcheck` do Compose e por um monitor externo gratuito (UptimeRobot) com alerta.
- Logs JSON para stdout, rotação pelo Docker.
- Erros de aplicação: e-mail não existe, então erros vão para log estruturado e para uma página `/admin/` de últimos erros (tabela `ErrorLog` simples, retenção 30 dias). GlitchTip auto-hospedado é Evolução.
- Analytics da Cloudflare (gratuito, sem cookie) cobre tráfego básico.

## Ambiente de desenvolvimento

`infra/docker-compose.dev.yml`: `web` com `runserver` e volume do código, `db` com porta exposta, sem Caddy nem túnel, Vite em modo dev com HMR (a partir da E04).

Detalhes definidos na E02:

- O `web` de dev usa a imagem pronta `ghcr.io/astral-sh/uv:python3.13-bookworm-slim`, sem Dockerfile próprio (o Dockerfile de produção é da E27). O ambiente virtual do container fica num volume (`/opt/venv`) para não se misturar com o `backend/.venv` do Windows.
- O `db` publica a porta **5433** no computador, porque a 5432 já é usada por um PostgreSQL local. Dentro do Compose o Django usa `db:5432`.
- O `.env` fica em `infra/env/.env` e é lido pelo Django (modo nativo) e pelo Compose (`--env-file`).
- `make dev` sobe tudo no Docker; `make dev-native` sobe só o banco e roda o Django no Windows. Login Microsoft em dev usa `http://localhost:8000` registrado como redirect adicional no app do Entra ID; login por senha também funciona.

`Makefile`:

| Comando | Faz |
|---|---|
| `make dev` | Sobe banco e app em modo dev |
| `make migrate`, `make shell`, `make superuser` | Atalhos |
| `make seed` | Taxonomia inicial e dados de exemplo |
| `make test`, `make lint` | |
| `make build` | Imagem de produção multi-arch |
| `make deploy` | No servidor: `git pull`, `docker compose up -d --build`, `migrate` |
| `make release VERSION=x.y.z` | Atualiza `VERSION`, `CHANGELOG.md`, cria tag ([30](30-versionamento.md)) |
| `make backup`, `make restore FILE=` | |

Dados de exemplo: 5 membros da equipe (professores, um monitor, uma coordenadora), 30 publicações em vários estados, alunos creditados, comentários em vários estados, imagens placeholder.

## CI

GitHub Actions: `ruff`, `djlint`, `pytest` com PostgreSQL, build da imagem. Deploy manual (`make deploy`) no MVP.

## Atualizações

`uv.lock` travado; `pip-audit` mensal; Django patches imediatos, próxima LTS quando madura; PostgreSQL major só com `pg_upgrade` planejado.

## Histórico

- 2026-09-12: versão inicial.
- 2026-09-12: domínio `jornal.projetosrosa.com.br`, Cloudflare Tunnel decidido, Oracle Free Tier como alvo alternativo (ARM), sem e-mail, variáveis de Microsoft e clima, versão no healthz.
