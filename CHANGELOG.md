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
- Frontend com Vite, Tailwind 4, HTMX e Alpine via `django-vite`; fontes Newsreader e Inter auto-hospedadas (E04).
- Tokens do design system, glifo e wordmark "Jornal Escolar", favicon.
- `base.html`, `layouts/public.html`, masthead, rodapé com crédito e versão, página inicial provisória.
- Comandos `make assets-install`, `assets-dev` e `assets`.
- factory-boy com `UserFactory` e fixtures compartilhadas (`staff_user`, `editor_user`, `admin_user`, `admin_client`) (E05).
- GitHub Actions: lint, checagem de migrações, testes com PostgreSQL e build do frontend.
- `README.md` com preparação do computador e comandos; `CLAUDE.md` com instruções para assistentes de código (E06).
- Serviço `vite` no Compose de desenvolvimento; `docker compose up` na raiz sobe banco, Django e Vite, sem `.env` nem outras ferramentas instaladas.
- Taxonomia: áreas do conhecimento (com cor do design system), disciplinas, tópicos (palavras-chave e disciplinas sugeridas) e tipos de publicação, editáveis no Django Admin (E07).
- Comando `seed_taxonomy` com 6 áreas, 24 disciplinas, 30 tópicos e 10 tipos; só cria o que falta.
- Configurações do site no banco (`SiteSetting`) com cache e formulário por tipo no Django Admin; nome, frase, crédito, e-mail e data do cabeçalho passam a ser editáveis (E08).
- Páginas institucionais `/sobre/`, `/colaborar/` e `/privacidade/` (`StaticPage`), com links no rodapé só para as publicadas.
- Comando `seed_site`: cria configurações e textos iniciais; Privacidade nasce despublicada até revisão da direção.
- Login em `/entrar/` com `django-allauth`: senha de reserva e botão "Entrar com a conta da escola" (Microsoft), que aparece quando `MS_CLIENT_ID`/`MS_CLIENT_SECRET` estão configurados (E09).
- Login Microsoft só para domínios permitidos e contas cadastradas e ativas, identificando a pessoa pelo `userPrincipalName`.
- Limite de tentativas de login (5 por e-mail e 30 por IP a cada 15 minutos); sessão de 14 dias sem uso; senha mínima de 10 caracteres.
- Layout `auth.html`, telas de sair, conta desativada, cadastro fechado e erros de login; cabeçalho com "Entrar" ou nome, "Admin" e "Sair".
- Configuração "Login com a conta Microsoft da escola ligado" no admin.

### Alterado

- O `/admin/login/` redireciona para `/entrar/`; telas do allauth sem uso (cadastro, recuperação de senha por e-mail, e-mails) respondem 404.
- Variável de template da identidade do site renomeada de `site` para `jornal`, que o allauth sobrescrevia.

- Compose de desenvolvimento movido de `infra/docker-compose.dev.yml` para `compose.yaml` na raiz.

### Corrigido

- `make format` formata antes de aplicar correções do ruff e não para quando o djlint altera templates.

## [0.0.1] - 2026-09-12

### Adicionado

- Documentação de planejamento em `docs/`.
- Estrutura do repositório (E01): `backend/`, `frontend/`, `infra/`.
- Ferramentas de qualidade: `uv`, ruff, djlint, pre-commit e `.editorconfig`.
- `Makefile` com `install`, `lint`, `format` e `hooks`.
- Arquivo `VERSION` e este changelog.
