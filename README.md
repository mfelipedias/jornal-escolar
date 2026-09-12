# Jornal Escolar

Jornal digital da comunidade escolar: professores e equipe publicam textos, alunos aparecem como autores creditados e qualquer pessoa lê, busca, reage e comenta (com moderação).

- Endereço: `https://jornal.projetosrosa.com.br` (em preparação)
- Planejamento completo: [`docs/`](docs/README.md)
- Plano de desenvolvimento por etapas: [`docs/26`](docs/26-plano-de-desenvolvimento.md)
- Histórico de versões: [`CHANGELOG.md`](CHANGELOG.md)

## Tecnologias

Django 5.2 com templates, HTMX e Alpine.js; Tailwind CSS 4 e Vite; PostgreSQL 17; Docker Compose. Detalhes e motivos em [`docs/05`](docs/05-arquitetura-tecnica.md).

## Preparar o computador (Windows)

Precisa ter instalado:

| Programa | Para quê | Como instalar |
|---|---|---|
| Git | Versionar o código | https://git-scm.com |
| uv | Python e dependências do backend | https://docs.astral.sh/uv/ |
| Node.js 24 | Build de CSS e JS | https://nodejs.org |
| Docker Desktop | Banco de dados | https://www.docker.com/products/docker-desktop/ |
| GNU Make | Atalhos de comando | `winget install ezwinports.make` |

Depois, uma única vez:

```
make install
make hooks
copy infra\env\.env.example infra\env\.env
make secret-key
```

Cole a chave gerada em `SECRET_KEY` dentro de `infra/env/.env`.

## Rodar no dia a dia

Em dois terminais:

```
make dev-native     # banco no Docker + Django em http://localhost:8000
make assets-dev     # Vite: CSS e JS com recarga automática
```

Outros comandos úteis (lista completa com `make`):

| Comando | Faz |
|---|---|
| `make test` | Roda os testes (o banco precisa estar ligado: `make db`) |
| `make lint` | Verifica o código sem alterar nada |
| `make format` | Formata o código |
| `make superuser` | Cria um administrador |
| `make migrate` / `make makemigrations` | Banco de dados |
| `make dev` | Alternativa: sobe banco e Django no Docker |
| `make down` | Para os containers |
| `make db-reset` | Apaga e recria o banco de desenvolvimento |

Verificação rápida: http://localhost:8000/healthz/ deve responder `{"status": "ok", "version": "..."}`.

## Estrutura

```
backend/    Django (config/, apps/, templates/, static/)
frontend/   Vite e Tailwind (src/css, src/js)
infra/      Docker Compose e variáveis de ambiente
docs/       Planejamento e decisões
```

## Créditos

Desenvolvido por Professor Marcos Felipe A. D. da Silva.
