# AGENTS.md

Instruções para assistentes de código neste repositório.

## Contexto

Jornal Escolar: jornal digital de uma escola estadual de SP. Só a equipe da escola tem conta; alunos são créditos sem conta. O dono do projeto é professor, forte em Python e backend, pouco familiarizado com frontend e infraestrutura. Escreva código, comentários, commits e documentação em **português do Brasil**, e explique infraestrutura em linguagem simples.

O nome da escola **nunca** aparece no site, nos dados estruturados ou nas configurações. A marca é "Jornal Escolar" (`site.name`).

## Fonte da verdade

- `docs/` contém o planejamento. Antes de uma etapa, leia os documentos citados nela.
- `docs/26-plano-de-desenvolvimento.md` define as etapas (E01, E02, ...). Implemente **uma etapa por vez**, só o escopo dela.
- Se uma decisão de `docs/` se mostrar errada na prática, pare, proponha a mudança no documento e registre-a no "Histórico" do arquivo.
- `docs/27` registra as decisões do dono do projeto; não as reverta sem perguntar.

## Ciclo de cada etapa

1. Ler os documentos de referência.
2. Propor em poucas linhas o que será feito.
3. Implementar com testes.
4. `make test` e `make lint` passando.
5. Anotar em `CHANGELOG.md`, seção `[Não lançado]`.
6. Commit `EXX: descrição curta`. Ao fechar uma fase, `make release` (docs/30).

## Comandos

```
docker compose up   # forma preferida pelo dono do projeto: db (5433), web (8000), vite (5173)
make dev            # o mesmo que docker compose up
make install        # uv sync + npm install
make db             # PostgreSQL de dev no Docker (porta 5433)
make dev-native     # Django em http://localhost:8000
make assets-dev     # Vite (porta 5173)
make assets         # build de produção do frontend
make test           # pytest
make lint           # ruff check, ruff format --check, djlint
make format
```

Dentro de `backend/`: `uv run python manage.py <comando>`, `uv run pytest caminho::teste`.

## Arquitetura e convenções

- Django monolítico: templates + HTMX (servidor) + Alpine (estado local). Sem SPA, sem API pública no MVP.
- Apps em `backend/apps/<app>/` com label curto (`core`, `accounts`, ...). Regras de negócio em `services.py`, consultas em `selectors.py`, views finas.
- Permissões editoriais só em `apps/editorial/permissions.py` (a partir da E12).
- `accounts.User`: login por e-mail em minúsculas; `role` (`staff`, `editor`, `admin`) decide permissões; `is_staff`/`is_superuser` são derivados de `role` no `save()`; `staff_kind` é só exibição.
- Settings em `config/settings/{base,dev,test,prod}.py`, variáveis via `django-environ` a partir de `infra/env/.env`.
- Identidade do site nos templates é `{{ jornal.name }}`, `{{ jornal.tagline }}` etc. (context processor `apps.core.context_processors.site`). Não use `site`: o allauth e o Django sobrescrevem essa variável. Valores vêm de `apps/core/site_settings.py` (`get_setting("chave")`), editáveis no admin.
- Login: `django-allauth` com cadastro fechado; adaptadores em `apps/accounts/adapters.py`. Login Microsoft identifica pelo `userPrincipalName`, nunca pelo `mail`.
- Versão em `VERSION` (raiz) → `settings.APP_VERSION`, `/healthz/`, cabeçalho `X-App-Version`, rodapé.
- Templates: `layouts/` esqueletos, `components/` peças com `{% include ... with %}`, `<app>/partials/` fragmentos HTMX. Nenhuma cor escrita direto no template: use os tokens do Tailwind (`bg-paper`, `text-ink-2`, `text-accent`, `bg-area-verde-soft`).
- Frontend: fontes em `frontend/src/` (não em `backend/static/src/`); saída em `backend/static/dist/` (gitignored).
- URLs públicas em português (`/quem-escreve/`); nomes de rota em inglês (`publications:detail`).
- Testes com pytest-django, fábricas em `backend/tests/factories.py`, fixtures em `backend/conftest.py` (`staff_user`, `editor_user`, `admin_user`, `admin_client`).
- Linha máxima de 100 caracteres (ruff). Migrações geradas no Windows saem com CRLF; o pre-commit corrige, então re-adicione ao git se o hook alterar arquivos.

## Ambiente (Windows)

- Shell padrão é PowerShell 5.1: sem `&&`; `git commit -m` com aspas quebra, use `git commit -F arquivo`.
- `make` é GNU Make do winget e executa receitas no `cmd`: mantenha receitas como comandos simples; lógica complexa vai para scripts Python.
- A porta 5432 é de um PostgreSQL local; o banco do projeto usa 5433.
