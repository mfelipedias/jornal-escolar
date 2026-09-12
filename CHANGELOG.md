# Changelog

Todas as mudanças relevantes do Jornal Escolar ficam registradas aqui.

O formato segue o [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e o projeto usa [Versionamento Semântico](https://semver.org/lang/pt-BR/). Detalhes em [docs/30](docs/30-versionamento.md).

## [Não lançado]

### Adicionado

- Projeto Django 5.2 com configurações por ambiente (`base`, `dev`, `test`, `prod`) lidas de variáveis de ambiente (E02).
- `infra/env/.env.example` e Compose de desenvolvimento com PostgreSQL 17 (porta 5433) e Django.
- App `core` com `/healthz/` (banco, migrações e versão) e cabeçalho `X-App-Version` em todas as respostas.
- pytest e pytest-django, com testes do `/healthz/`.
- Comandos `make dev`, `dev-native`, `db`, `down`, `logs`, `test`, `migrate`, `makemigrations`, `shell`, `superuser` e `secret-key`.
- Usuário customizado `accounts.User` com login por e-mail (sempre em minúsculas), papel (`role`), cargo (`staff_kind`) e senhas em Argon2 (E03).
- Cadastro de usuários no Django Admin; só o papel `admin` acessa o Django Admin.
- `make db-reset` para recriar o banco de desenvolvimento.

### Corrigido

- `make format` formata antes de aplicar correções do ruff e não para quando o djlint altera templates.

## [0.0.1] - 2026-09-12

### Adicionado

- Documentação de planejamento em `docs/`.
- Estrutura do repositório (E01): `backend/`, `frontend/`, `infra/`.
- Ferramentas de qualidade: `uv`, ruff, djlint, pre-commit e `.editorconfig`.
- `Makefile` com `install`, `lint`, `format` e `hooks`.
- Arquivo `VERSION` e este changelog.
