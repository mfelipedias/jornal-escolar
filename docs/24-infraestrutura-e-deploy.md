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
| `caddy` | `caddy:2` | 1 | Proxy interno: `/static/` e `/media/` dos volumes com cache, cabeçalhos, `trusted_proxies`, o resto para `web` |
| `web` | imagem própria (Python 3.13 slim) | 1 | Gunicorn + Django |
| `db` | `postgres:17` (Fase 5: `pgvector/pgvector:pg17`) | 1 | Banco |
| `backup` | imagem própria (`python:3.13-alpine` + `postgresql17-client` + `rclone` + `supercronic`) | 1 | Backup diário |
| `worker` | mesma imagem de `web`, `python manage.py procrastinate worker` | 4 | Tarefas agendadas (limpezas, avisos diários; coleta RSS a partir da E45) |
| `ollama` | `ollama/ollama:rocm` | 5 (congelada) | Modelos locais |

Volumes: `pgdata`, `media`, `static`, `caddy_data`. Perfis: `tunel` (liga o `cloudflared`), `ai`. O `worker` sobe sempre, sem perfil (E44).

Arquivos (E27): `infra/docker-compose.yml`, `infra/Dockerfile`, `infra/caddy/Caddyfile`, `infra/scripts/{entrypoint.sh,healthcheck.py}`, `infra/backup/` (Dockerfile, `backup.py`, `restore.py`, `comum.py`, `crontab`) e `infra/env/.env.producao.example`. Guia para o dono em [34](34-guia-deploy.md).

Cada serviço recebe só as variáveis de que precisa (lista `environment` no Compose, sem `env_file`): o `web` não conhece as chaves do R2 nem o token do túnel. O Compose lê os valores de `infra/env/.env` com `--env-file` (atalhos `make deploy`, `make backup` etc.).

Por que manter o Caddy atrás do túnel: servir `/media/` com cache e cabeçalhos corretos sem passar pelo Django, e permitir rodar sem Cloudflare (ex.: rede interna da escola) trocando só o perfil.

## Dockerfile (multi-stage)

1. `node:24-slim` (mesma versão do Compose de dev), na arquitetura de quem constrói (`--platform=$BUILDPLATFORM`): `npm ci`, `vite build`, gera `backend/static/dist/`.
2. `python:3.13-slim` com `uv`: dependências do `uv.lock` sem as de desenvolvimento, em `/opt/venv`.
3. `python:3.13-slim` final: venv, código, `dist/`, `collectstatic` em `/app/staticfiles`, usuário `jornal` (uid 1000), `HEALTHCHECK` com `healthcheck.py`. O `entrypoint.sh` copia os estáticos para o volume `static`, roda `migrate` e liga o Gunicorn. Imagem final sem Node nem uv (cerca de 370 MB). Build multi-arch; o servidor constrói a própria imagem no `make deploy`, sem registry.

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

### Cache

O cache do Django (limites por minuto, configurações do site, blocos da home e listas) fica, em produção, numa tabela do próprio PostgreSQL (`DatabaseCache`, tabela `django_cache`, em `config/settings/prod.py`). O Gunicorn roda vários workers, e cada um é um processo separado: com o cache em memória, cada worker teria o seu, e um limite de 60 por minuto viraria 60 por worker; publicar limparia o cache de um worker só. A tabela resolve isso sem serviço novo (sem Redis). O `entrypoint.sh` roda `createcachetable` depois do `migrate`, então o `make deploy` cria a tabela sozinho. Em desenvolvimento e nos testes o cache continua em memória. Se um dia o volume de acessos pedir, trocar por Redis é mudar só `CACHES`.

## Tarefas agendadas

Desde a E44, as tarefas que rodam sozinhas ficam num **worker**: um programa que fica ligado ao lado do site, olha a fila e executa o que chegou a hora de executar. É o [Procrastinate](https://procrastinate.readthedocs.io/), com a fila no próprio PostgreSQL (sem Redis), como decidido em [05](05-arquitetura-tecnica.md) D8.

- Código em `backend/apps/core/tasks.py` e `backend/apps/curation/tasks.py` (coleta de notícias, E45), descoberto pelo app `procrastinate.contrib.django`; as tabelas da fila (`procrastinate_jobs` e outras) vêm pelas migrações. Cada tarefa só chama a regra que já existe nos services, a mesma dos comandos de gerenciamento, e pode rodar de novo sem estrago.
- Serviço `worker` nos dois Compose, com a mesma imagem e configuração do `web`. Em produção, espera o `web` ficar saudável (é o `web` que aplica as migrações) e tem teste de saúde próprio (`manage.py procrastinate healthchecks`), porque o da imagem pergunta ao Gunicorn. Em dev, espera as migrações e não recarrega ao salvar: `docker compose restart worker` depois de mexer numa tarefa.
- O Procrastinate lê o cron em UTC; `local_cron` escreve os horários no horário de Brasília. Se o worker ficar desligado, a tarefa atrasada até 10 minutos ainda roda ao religar; atrasos maiores esperam o próximo horário.
- O registro das tarefas fica no banco e aparece no Django Admin ("Procrastinate"), só leitura. Os logs (`docker compose logs worker` ou `make prod-logs`) mostram cada execução e o resultado.

| Tarefa | Quando (Brasília) | O que faz | Comando equivalente |
|---|---|---|---|
| `heartbeat` | a cada hora, minuto 0 | tarefa de teste: registra "Worker vivo" no log | — |
| `cleanup` | todo dia, 4h30 | leituras com mais de 90 dias, comentários rejeitados há 30 dias, dados técnicos de comentários com 30 dias, notícias coletadas há mais de 60 dias (menos as salvas, interessantes ou que viraram pauta) | `cleanup` |
| `remind_pending_comments` | todo dia, 7h | avisa editores de comentários de leitores pendentes há 3 dias | `notify_pending_comments` |
| `remind_stale_reviews` | todo dia, 7h10 | avisa revisor e autores de revisões paradas há 5 dias ([04](04-fluxo-editorial.md)) | `notify_stale_reviews` |
| `fetch_news` | a cada 30 minutos (5 e 35 de cada hora) | enfileira uma `fetch_news_source` para cada fonte de notícias ativa cujo intervalo já passou ([21](21-curadoria-de-noticias.md)) | `fetch_news --vencidas` |
| `fetch_news_source` | quando `fetch_news` enfileira | coleta um feed, grava e classifica as notícias novas e as sugere a quem se interessa | `fetch_news --fonte ID` |
| `reclassify_news` | quando o admin muda palavras-chave, tópicos ou padrões de fonte (E47) | classifica de novo as notícias guardadas e recalcula as sugestões | `classify_news` |
| `notify_new_suggestions` | segunda, 7h20 | aviso no sino para quem recebeu sugestões de pauta na semana (E48) | — |
| `purge_worker_history` | domingo, 5h | apaga o registro das tarefas concluídas há mais de 30 dias (as que falharam ficam) | — |

A limpeza das 4h30 fica depois do backup das 3h. `WORKER_HEARTBEAT_CRON` (em UTC) troca o horário do batimento; `* * * * *` serve para ver o agendamento funcionando.

## Backups

Diário às 3h no container `backup` (`infra/backup/backup.py`, disparado pelo `supercronic`):

1. `pg_dump -Fc` e verificação com `pg_restore --list`.
2. Envio para `banco/jornal-AAAA-MM-DD_HHMMSS.dump` no destino.
3. `rclone sync` do volume `media` para `midia/`; arquivos apagados ou trocados vão para `midia-removida/<data>/` (`--backup-dir`). Só fotos novas trafegam, sem cadeia de backups incrementais.
4. Criptografia pelo remoto `crypt` do rclone com `BACKUP_PASSPHRASE` (nomes legíveis, conteúdo cifrado).
5. Destino **Cloudflare R2** (10 GB grátis, na mesma conta Cloudflare já usada para DNS e túnel), ou uma pasta local com `BACKUP_DESTINO=local`. Guia em [31](31-guia-backup.md).
6. Retenção: todos os backups dos 7 últimos dias com backup, o mais recente de cada uma das 4 últimas semanas e de cada um dos 6 últimos meses; pastas de mídia removida com mais de 6 meses são apagadas.

`infra/backup/restore.py` (`make restore FILE=`) restaura em servidor limpo ou em uso (inclusive de x86 para ARM): recria o schema `public`, `pg_restore --no-owner`, `rclone sync` da mídia e devolve as fotos removidas depois da data escolhida. Teste trimestral.

## Monitoramento mínimo

- `/healthz/` (banco acessível, migrações aplicadas, versão do sistema; aceita GET e HEAD) usado pelo `healthcheck` do Compose e por um monitor externo gratuito (UptimeRobot, monitor de palavra-chave) com alerta.
- `manage.py check --deploy` (`make prod-check`) avisa quando `SITE_URL` aponta para localhost, não usa https ou tem caminho (`core.W001` a `W003`).
- Logs JSON para stdout, rotação pelo Docker.
- Erros de aplicação: e-mail não existe, então erros vão para log estruturado e para uma página `/admin/` de últimos erros (tabela `ErrorLog` simples, retenção 30 dias). GlitchTip auto-hospedado é Evolução.
- Analytics da Cloudflare (gratuito, sem cookie) cobre tráfego básico.

## Ambiente de desenvolvimento

`compose.yaml` na raiz (antes `infra/docker-compose.dev.yml`; movido para que `docker compose up` funcione sem parâmetros): `web` com `runserver` e volume do código, `db` com porta exposta, sem Caddy nem túnel, Vite em modo dev com HMR (a partir da E04).

Detalhes definidos na E02:

- O `web` de dev usa a imagem pronta `ghcr.io/astral-sh/uv:python3.13-bookworm-slim`, sem Dockerfile próprio (o Dockerfile de produção é da E27). O ambiente virtual do container fica num volume (`/opt/venv`) para não se misturar com o `backend/.venv` do Windows.
- O `db` publica a porta **5433** no computador, porque a 5432 já é usada por um PostgreSQL local. Dentro do Compose o Django usa `db:5432`.
- O `.env` fica em `infra/env/.env` e é lido pelo Django (modo nativo). No Compose ele é **opcional**: o `compose.yaml` já traz credenciais e chave secreta de desenvolvimento, para que um clone novo suba só com `docker compose up`.
- `make dev` sobe tudo no Docker; `make dev-native` sobe só o banco e roda o Django no Windows.
- Desde 2026-09-12 o Compose de dev também tem o serviço `vite` (`node:24-slim`, porta 5173), a pedido do dono do projeto, para que `make dev` suba o projeto inteiro sem Node no Windows. O `node_modules` do container fica num volume próprio (binários Linux) e o Vite observa arquivos por polling (`VITE_USE_POLLING`), porque pastas montadas do Windows não geram eventos de alteração.
- Foi pedido um container único com banco e Django; a decisão foi manter **um container por serviço** agrupados no mesmo projeto Compose, pelo alinhamento com produção, atualizações independentes, backup do banco e reinício isolado em falhas. Login Microsoft em dev usa `http://localhost:8000` registrado como redirect adicional no app do Entra ID; login por senha também funciona.

`Makefile`:

| Comando | Faz |
|---|---|
| `make dev` | Sobe banco e app em modo dev |
| `make migrate`, `make shell`, `make superuser` | Atalhos |
| `make seed` | Taxonomia inicial e dados de exemplo |
| `make test`, `make lint` | |
| `make build` | Confere o build das imagens para amd64 e arm64 |
| `make deploy` | No servidor: `git pull`, `docker compose up -d --build --wait` (o `migrate` roda no entrypoint) |
| `make prod-check`, `make prod-logs`, `make prod-down`, `make prod-superuser` | Atalhos de produção |
| `make release VERSION=x.y.z` | Atualiza `VERSION`, `CHANGELOG.md`, cria tag ([30](30-versionamento.md)) |
| `make backup`, `make backups`, `make restore FILE=` | Backup agora, lista de backups, restauração |

Dados de exemplo: 5 membros da equipe (professores, um monitor, uma coordenadora), 30 publicações em vários estados, alunos creditados, comentários em vários estados, imagens placeholder.

## CI

GitHub Actions: `ruff`, `djlint`, `pytest` com PostgreSQL, build do frontend e build das imagens do site e do backup para amd64 e arm64 (sem push). Deploy manual (`make deploy`) no MVP.

## Atualizações

`uv.lock` travado; `pip-audit` mensal; Django patches imediatos, próxima LTS quando madura; PostgreSQL major só com `pg_upgrade` planejado.

## Histórico

- 2026-09-12: versão inicial.
- 2026-09-12: domínio `jornal.projetosrosa.com.br`, Cloudflare Tunnel decidido, Oracle Free Tier como alvo alternativo (ARM), sem e-mail, variáveis de Microsoft e clima, versão no healthz.
- 2026-09-14: E27. `/static/` passa a ser entregue pelo Caddy a partir de um volume preenchido pelo entrypoint, em vez do WhiteNoise: uma dependência a menos e o mesmo caminho da mídia. Backup criptografado com o `crypt` do rclone em vez do `age`, porque o `age` só aceita senha digitada no terminal e o backup roda sozinho; mídia espelhada com `rclone sync --backup-dir` em vez de `tar` incremental (restauração sem cadeia de arquivos, e fotos apagadas somem de vez após 6 meses). Scripts de backup em Python, não shell. Node 24 no build, igual ao dev. `cloudflared` no perfil `tunel`. A retenção diária guarda todos os backups dos 7 últimos dias, para que um backup manual não substitua o das 3h.
- 2026-09-14: E39. Cache compartilhado em produção com `DatabaseCache` (seção "Cache"); `createcachetable` no entrypoint.
- 2026-09-17: E44. Seção "Tarefas agendadas": worker do Procrastinate nos dois Compose. O `worker` deixa de ter perfil próprio e sobe sempre, porque as limpezas e os avisos diários dependem dele desde já, não só a coleta da Fase 4. O cron do host previsto para a Fase 3 não chegou a existir: os comandos continuam para rodar à mão. A limpeza passa de mensal para diária (é leve e cumpre melhor o prazo de 30 dias dos dados técnicos dos comentários).
- 2026-09-17: E45. Tarefas `fetch_news` (a cada 30 minutos) e `fetch_news_source` (uma por fonte) na tabela de tarefas agendadas. O worker e o `web` passam a acessar a internet para ler feeds; nenhuma variável nova.
