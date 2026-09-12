# Jornal Escolar

Jornal digital da comunidade escolar: professores e equipe publicam textos, alunos aparecem como autores creditados e qualquer pessoa lê, busca, reage e comenta (com moderação).

- Endereço: `https://jornal.projetosrosa.com.br` (em preparação)
- Planejamento completo: [`docs/`](docs/README.md)
- Plano de desenvolvimento por etapas: [`docs/26`](docs/26-plano-de-desenvolvimento.md)
- Histórico de versões: [`CHANGELOG.md`](CHANGELOG.md)

## Tecnologias

Django 5.2 com templates, HTMX e Alpine.js; Tailwind CSS 4 e Vite; PostgreSQL 17; Docker Compose. Detalhes e motivos em [`docs/05`](docs/05-arquitetura-tecnica.md).

## Rodar o projeto (só com Docker)

Precisa apenas do **Docker Desktop** aberto. Na pasta do projeto:

```
docker compose up
```

Abra http://localhost:8000. Pronto.

Sobe três containers, agrupados no Docker Desktop como `jornal_escolar_dev`:

| Container | Função | Endereço |
|---|---|---|
| `db` | PostgreSQL 17 | `localhost:5433` |
| `web` | Django, recarrega ao salvar arquivos Python e templates | http://localhost:8000 |
| `vite` | CSS e JS, recarrega ao salvar templates e estilos | `localhost:5173` (usado pelas páginas) |

- A primeira vez demora alguns minutos (baixa imagens e instala dependências); depois é rápido.
- Pronto quando o log mostrar `Starting development server at http://0.0.0.0:8000/`.
- Salvou um arquivo? O site se atualiza sozinho; não precisa reiniciar.
- Para parar: `Ctrl+C`. Os dados do banco ficam guardados para a próxima vez.
- Não precisa de `.env`: o `compose.yaml` já traz valores de desenvolvimento. Para personalizar, copie `infra/env/.env.example` para `infra/env/.env`.

Cada serviço tem seu próprio container, como em produção: dá para atualizar o Django sem tocar no banco, e backups ficam simples.

### Comandos Docker úteis

| Comando | Faz |
|---|---|
| `docker compose up` | Sobe tudo (mostra os logs; `Ctrl+C` para parar) |
| `docker compose up -d` | Sobe tudo em segundo plano |
| `docker compose logs -f web` | Acompanha os logs do Django |
| `docker compose down` | Para e remove os containers (o banco fica guardado) |
| `docker compose exec web uv run python manage.py createsuperuser` | Cria um administrador |
| `docker compose exec web uv run python manage.py seed_taxonomy` | Cria áreas, disciplinas, tópicos e tipos iniciais (pode repetir; não apaga edições) |
| `docker compose exec web uv run pytest` | Roda os testes |
| `docker compose down -v` | **Apaga tudo**, inclusive o banco |

## Ferramentas opcionais para desenvolver

Nada disso é necessário para rodar o site. Serve para rodar lint e testes direto no Windows, ou ativar a verificação automática antes de cada commit.

| Programa | Para quê | Como instalar |
|---|---|---|
| uv | Python e dependências do backend | https://docs.astral.sh/uv/ |
| Node.js 24 | Build de CSS e JS fora do Docker | https://nodejs.org |
| GNU Make | Atalhos de comando | `winget install ezwinports.make` |

Com elas instaladas: `make install` e `make hooks` uma vez; `make dev-native` e `make assets-dev` rodam Django e Vite no Windows.

Lista completa de atalhos com `make`:

| Comando | Faz |
|---|---|
| `make test` | Roda os testes (o banco precisa estar ligado: `make db`) |
| `make lint` | Verifica o código sem alterar nada |
| `make format` | Formata o código |
| `make superuser` | Cria um administrador |
| `make migrate` / `make makemigrations` | Banco de dados |
| `make logs` | Mostra os logs dos containers |
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
