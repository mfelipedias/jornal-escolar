# 08 — Estrutura do repositório

## Árvore

```
jornal_escolar/
├── docs/                         # Esta documentação
├── backend/                      # Projeto Django
│   ├── manage.py
│   ├── pyproject.toml            # Dependências (uv ou pip-tools), ruff, pytest
│   ├── config/                   # Projeto Django (settings, urls, wsgi)
│   │   ├── settings/
│   │   │   ├── base.py
│   │   │   ├── dev.py
│   │   │   ├── test.py
│   │   │   └── prod.py
│   │   ├── urls.py
│   │   ├── wsgi.py
│   │   └── asgi.py
│   ├── apps/
│   │   ├── core/                 # Home, páginas estáticas, SiteSetting, AuditLog, ErrorLog, clima, versão
│   │   ├── accounts/             # User, perfis, links de acesso, login (senha e Microsoft), "Quem escreve"
│   │   ├── taxonomy/             # Áreas, disciplinas, tópicos, tipos
│   │   ├── publications/         # Article, contribuições, revisões, mídia, editor, renderizador JSON→HTML
│   │   ├── editorial/            # Máquina de estados, permissões, comentários editoriais, eventos, notificações
│   │   ├── engagement/           # Reações, leituras, comentários públicos e moderação
│   │   ├── search/               # Busca e filtros
│   │   ├── dashboard/            # Painel (agrega views das outras apps)
│   │   ├── curation/             # Fase 4: fontes, itens, classificação, recomendações, pautas
│   │   └── ai/                   # Fase 5 (congelada): não criar antes da fase
│   ├── templates/
│   │   ├── base.html
│   │   ├── layouts/              # public.html, dashboard.html, auth.html
│   │   ├── components/           # card.html, byline.html, tag.html, empty_state.html, pagination.html
│   │   ├── core/
│   │   ├── accounts/
│   │   ├── publications/
│   │   │   └── partials/
│   │   ├── editorial/
│   │   ├── dashboard/
│   │   ├── search/
│   │   ├── engagement/
│   │   └── curation/
│   ├── static/
│   │   ├── src/                  # Fonte: css/app.css (Tailwind), js/app.js, js/editor.js
│   │   ├── dist/                 # Saída do Vite (gitignored), manifest.json
│   │   ├── img/                  # Logos, ícones, placeholders
│   │   └── fonts/                # Fontes auto-hospedadas
│   ├── locale/                   # Traduções (pt_BR é o padrão; pasta reservada)
│   └── tests/
│       ├── conftest.py
│       ├── factories.py
│       ├── unit/
│       ├── integration/
│       └── e2e/                  # Playwright, poucos cenários críticos
├── frontend/                     # Só ferramentas de build
│   ├── package.json
│   ├── vite.config.js            # Entrada: backend/static/src; saída: backend/static/dist
│   └── tailwind.config.js        # Se necessário (Tailwind 4 usa CSS-first)
├── infra/
│   ├── docker-compose.yml        # Produção: cloudflared (perfil tunel), caddy, web, db, backup
│   ├── (dev)                     # O Compose de desenvolvimento é o compose.yaml da raiz
│   ├── Dockerfile                # Multi-stage, multi-arch: build de assets (node) + runtime (python)
│   ├── caddy/Caddyfile           # /static/ e /media/ dos volumes; o resto para o web
│   ├── backup/                   # Imagem do backup: Dockerfile, backup.py, restore.py, comum.py, crontab
│   ├── scripts/
│   │   ├── entrypoint.sh         # estáticos para o volume, migrate, gunicorn
│   │   └── healthcheck.py        # HEALTHCHECK do container web
│   └── env/
│       ├── .env.example          # Desenvolvimento
│       └── .env.producao.example # Servidor (docs/34)
├── .github/workflows/ci.yml      # ruff, djlint, pytest
├── .pre-commit-config.yaml
├── .editorconfig
├── .gitignore
├── compose.yaml                  # Desenvolvimento: `docker compose up` sobe db, web e vite
├── Makefile                      # make dev, test, lint, build, deploy, release, backup
├── VERSION                       # Número da versão (SemVer), ver docs/30
├── CHANGELOG.md                  # Histórico de mudanças por versão
├── CLAUDE.md                     # Instruções para o assistente de código (gerado na Fase 0)
└── README.md
```

## Papel de cada pasta

| Pasta | Responsabilidade | Não deve conter |
|---|---|---|
| `docs/` | Planejamento e decisões | Código |
| `backend/config/` | Configuração do Django; `settings/` dividido por ambiente e lido de variáveis de ambiente com `django-environ` | Lógica de negócio |
| `backend/apps/<app>/` | Cada app tem `models.py`, `views.py`, `urls.py`, `forms.py`, `services.py` (regras de negócio), `selectors.py` (consultas), `admin.py`, `tests/` | Templates (ficam em `templates/<app>/` para facilitar herança) |
| `backend/apps/editorial/permissions.py` | Única fonte das regras de permissão | Regras duplicadas em views |
| `backend/apps/publications/rendering.py` | Renderizador ProseMirror JSON → HTML | HTML vindo do cliente |
| `backend/templates/components/` | Componentes reutilizáveis via `{% include %}` com parâmetros claros | Lógica de consulta |
| `backend/static/src/` | Código-fonte de CSS e JS | Arquivos gerados |
| `frontend/` | Configuração de build | Componentes de aplicação (não há SPA) |
| `infra/` | Tudo que sobe o sistema | Segredos (só `.env.example`) |

## Convenções de código

- **Services e selectors.** Views são finas. Regras (criar publicação, transitar estado, registrar leitura) ficam em `services.py` como funções puras que recebem `user` e objetos. Consultas complexas ficam em `selectors.py`. Facilita testes sem cliente HTTP.
- **Uma migração por mudança lógica**, com nome descritivo (`0003_article_search_vector`).
- **Templates:** `layouts/` para esqueletos, `components/` para peças, `<app>/partials/` para fragmentos HTMX. Um fragmento é sempre também incluído pela página completa, garantindo que a página funcione sem JS.
- **Fixtures e fábricas (E05):** fixtures compartilhadas ficam em `backend/conftest.py` (e não em `tests/conftest.py`), para valer também nos testes dentro de `apps/*/tests/`. Fábricas em `backend/tests/factories.py`, importadas como `from tests.factories import UserFactory`.
- **Testes:** cada service tem teste unitário; cada rota tem ao menos um teste de integração com status e permissão; três a cinco fluxos e2e (login, criar e publicar, revisar, reagir, buscar).
- **Tipagem:** type hints em services e selectors; mypy opcional no CI.
- **Nomes de URL sempre em português** (rotas públicas) e nomes internos de rota em inglês (`publications:detail`).

## Fluxo de assets

**Mudança na E04:** o código-fonte de CSS e JS fica em `frontend/src/`, e não em `backend/static/src/`. Os pacotes npm ficam em `frontend/node_modules`, e o Vite e o Tailwind só os encontram a partir de arquivos dentro de `frontend/`. As fontes vêm dos pacotes Fontsource e são empacotadas pelo Vite; `backend/static/fonts/` não é usado. Onde a árvore acima diz `static/src/` e `static/fonts/`, leia `frontend/src/` e "dentro do build".

1. `frontend/src/css/app.css` importa Tailwind, as fontes e define tokens (ver [09](09-design-system.md)).
2. `frontend/src/js/app.js` importa o CSS, HTMX e Alpine.
3. `frontend/src/js/editor.js` (E14) importa TipTap e extensões; expõe `window.initEditor(el, options)`.
4. Vite gera `backend/static/dist/` com hash nos nomes e `manifest.json` (`make assets`).
5. `django-vite` lê o manifest e injeta as tags nos templates (`{% vite_asset 'src/js/app.js' %}`). Em desenvolvimento, com `make assets-dev` aberto, as tags apontam para o servidor do Vite (porta 5173) e a página recarrega sozinha ao editar CSS.
6. Em produção, o Dockerfile roda o build do Vite na etapa Node e copia `dist/` para a imagem Python; `collectstatic` junta os arquivos e o Caddy os entrega com cache longo (E27).

## Ambiente de desenvolvimento no Windows

O dono do projeto desenvolve no Windows. Duas opções, em ordem de preferência:

1. **WSL2 + Docker Desktop**: repositório dentro do sistema de arquivos do WSL, `docker compose up` sobe banco e app, editor (VS Code) conectado ao WSL. Mais próximo da produção.
2. **Nativo**: Python e Node instalados no Windows; PostgreSQL via Docker Desktop; `python manage.py runserver` e `npm run dev` em terminais separados. Funciona, mas caminhos e permissões de arquivo às vezes divergem da produção.

O `Makefile` prevê ambas: `make dev` (compose) e `make dev-native`.

Na prática (E01), o desenvolvimento começou no modo **nativo**:

- **make** instalado com `winget install ezwinports.make`. No Windows ele executa os comandos pelo `cmd`, por isso as receitas do `Makefile` são chamadas simples ao `uv`, sem sintaxe de shell. Lógica mais elaborada (como a de `make release`) vai para scripts Python.
- **Python 3.13** fixado em `backend/.python-version`; o `uv` baixa essa versão sozinho, sem interferir no Python instalado no sistema. É a versão da imagem Docker de produção.
- Ruff, djlint e pre-commit ficam no grupo `dev` do `backend/pyproject.toml`; o pre-commit usa essas mesmas versões via `uv run`.

## Histórico

- 2026-09-12: versão inicial.
- 2026-09-12: `VERSION` e `CHANGELOG.md`; sem `emails/`; apps ajustadas às decisões.
- 2026-09-12: E01 executada; notas sobre make no Windows e Python 3.13.
- 2026-09-12: E04: fontes de CSS/JS em `frontend/src/`; fontes tipográficas via Fontsource no build.
- 2026-09-14: E27: `infra/backup/` com scripts em Python no lugar de `backup.sh`/`restore.sh`; `healthcheck.py`; `.env.producao.example`; estáticos entregues pelo Caddy.
