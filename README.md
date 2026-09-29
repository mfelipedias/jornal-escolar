# Jornal Escolar

[![CI](https://github.com/mfelipedias/jornal-escolar/actions/workflows/ci.yml/badge.svg)](https://github.com/mfelipedias/jornal-escolar/actions/workflows/ci.yml)
[![Licença: MIT](https://img.shields.io/badge/licen%C3%A7a-MIT-blue.svg)](LICENSE)

Jornal digital da comunidade escolar: professores e equipe publicam textos, alunos aparecem como autores creditados e qualquer pessoa lê, busca, reage e comenta (com moderação).

- Endereço: `https://jornal.projetosrosa.com.br` (em preparação)
- Planejamento completo: [`docs/`](docs/README.md)
- Plano de desenvolvimento por etapas: [`docs/26`](docs/26-plano-de-desenvolvimento.md)
- Histórico de versões: [`CHANGELOG.md`](CHANGELOG.md) (versão atual no arquivo `VERSION`)

## O que o jornal faz

- **Leitura pública:** página inicial com destaques, áreas, disciplinas, tópicos, agenda, busca sem acento, feed RSS, "Leia também", reações, contagem de leituras e comentários moderados.
- **Painel da equipe:** editor de textos com imagens e créditos de alunos (com autorização), revisão opcional por colegas, avisos no sino, moderação de comentários e painel editorial com alertas.
- **Curadoria de pautas:** o sistema lê feeds de fontes confiáveis, classifica as notícias por tópico e sugere a cada professor as que combinam com o perfil dele. Uma sugestão vira pauta no quadro da redação, e a pauta vira rascunho já com a fonte citada.
- **Contas:** o professor cria a própria conta com o e-mail `@prof` ou `@professor.educacao.sp.gov.br`, confirma com um código enviado por e-mail e espera a aprovação de um editor. O admin também cria contas (coordenação, monitores). "Esqueci minha senha" funciona por código no e-mail.

## Tecnologias

Django 5.2 com templates, HTMX e Alpine.js; Tailwind CSS 4 e Vite; PostgreSQL 17; Docker Compose. Detalhes e motivos em [`docs/05`](docs/05-arquitetura-tecnica.md).

## Rodar o projeto (só com Docker)

Precisa apenas do **Docker** (Docker Desktop no Windows e no Mac, ou Docker Engine no Linux). Na pasta do projeto:

```
docker compose up
```

Abra http://localhost:8000. Pronto.

Sobe quatro containers, agrupados no Docker Desktop como `jornal_escolar_dev`:

| Container | Função | Endereço |
|---|---|---|
| `db` | PostgreSQL 17 | `localhost:5433` |
| `web` | Django, recarrega ao salvar arquivos Python e templates | http://localhost:8000 |
| `vite` | CSS e JS, recarrega ao salvar templates e estilos | `localhost:5173` (usado pelas páginas) |
| `worker` | Tarefas agendadas: coleta de notícias, limpezas e avisos (`apps/core/tasks.py`, `apps/curation/tasks.py`). Não recarrega sozinho: `docker compose restart worker` | — |

- A primeira vez demora alguns minutos (baixa imagens e instala dependências); depois é rápido.
- Pronto quando o log mostrar `Starting development server at http://0.0.0.0:8000/`.
- Salvou um arquivo? O site se atualiza sozinho; não precisa reiniciar.
- Para parar: `Ctrl+C`. Os dados do banco ficam guardados para a próxima vez.
- Não precisa de `.env`: o `compose.yaml` já traz valores de desenvolvimento. Para personalizar, copie `infra/env/.env.example` para `infra/env/.env`.
- No desenvolvimento os e-mails não saem de verdade: o código de cadastro e o de "Esqueci minha senha" aparecem em `docker compose logs web`.

Cada serviço tem seu próprio container, como em produção: dá para atualizar o Django sem tocar no banco, e backups ficam simples.

### Comandos Docker úteis

| Comando | Faz |
|---|---|
| `docker compose up` | Sobe tudo (mostra os logs; `Ctrl+C` para parar) |
| `docker compose up -d` | Sobe tudo em segundo plano |
| `docker compose logs -f web` | Acompanha os logs do Django |
| `docker compose logs -f worker` | Acompanha as tarefas agendadas |
| `docker compose down` | Para e remove os containers (o banco fica guardado) |
| `docker compose exec web uv run python manage.py createsuperuser` | Cria um administrador |
| `docker compose exec web uv run python manage.py access_link email@escola` | Gera um link para a pessoa criar ou redefinir a senha |
| `docker compose exec web uv run python manage.py seed_site` | Cria as configurações do site e as páginas Sobre, Como participar e Privacidade |
| `docker compose exec web uv run python manage.py seed_taxonomy` | Cria áreas, disciplinas, tópicos e tipos iniciais (pode repetir; não apaga edições) |
| `docker compose exec web uv run python manage.py seed_news_sources` | Cadastra as fontes de notícias sugeridas para as pautas (pode repetir) |
| `docker compose exec web uv run python manage.py fetch_news` | Coleta as notícias das fontes agora, sem esperar o worker |
| `docker compose exec web uv run python manage.py classify_news` | Classifica de novo as notícias guardadas (depois de mudar palavras-chave dos tópicos) |
| `docker compose exec web uv run python manage.py send_test_email voce@exemplo.com` | Manda um e-mail de teste com a configuração de e-mail em uso |
| `docker compose exec web uv run python manage.py seed_demo` | **Só no desenvolvimento:** equipe e publicações fictícias, capas, agenda e destaques para ver o site cheio. Recusa rodar em produção |
| `docker compose exec web uv run python manage.py seed_demo --apagar` | Apaga tudo o que o `seed_demo` criou (pessoas fictícias, publicações e imagens) |
| `docker compose exec web uv run pytest` | Roda os testes |
| `docker compose down -v` | **Apaga tudo**, inclusive o banco |

## Ferramentas opcionais para desenvolver

Nada disso é necessário para rodar o site. Serve para rodar lint e testes direto no computador (Windows ou Linux), ou ativar a verificação automática antes de cada commit.

| Programa | Para quê | Como instalar |
|---|---|---|
| uv | Python e dependências do backend | https://docs.astral.sh/uv/ |
| Node.js 24 | Build de CSS e JS fora do Docker | https://nodejs.org |
| GNU Make | Atalhos de comando | Windows: `winget install ezwinports.make`; Linux: já vem instalado |

Com elas instaladas: `make install` e `make hooks` uma vez; `make dev-native` e `make assets-dev` rodam Django e Vite fora do Docker.

Se a pasta do projeto mudar de nome ou de lugar, o ambiente Python antigo para de funcionar (`Failed to spawn: pytest`). Recrie com `rm -rf backend/.venv` (no Windows, apague a pasta `backend\.venv`) e depois `make install` e `make hooks`.

Lista completa de atalhos com `make`:

| Comando | Faz |
|---|---|
| `make test` | Roda os testes (o banco precisa estar ligado: `make db`) |
| `make lint` | Verifica o código sem alterar nada |
| `make format` | Formata o código Python e os templates (confira o `git diff` depois: o formatador de templates pode mexer em arquivos que você não tocou) |
| `make superuser` | Cria um administrador |
| `make migrate` / `make makemigrations` | Banco de dados |
| `make logs` | Mostra os logs dos containers |
| `make down` | Para os containers |
| `make db-reset` | Apaga e recria o banco de desenvolvimento |

Verificação rápida: http://localhost:8000/healthz/ deve responder `{"status": "ok", "version": "..."}`.

## Colocar no ar

O passo a passo para o servidor (túnel da Cloudflare, backup no R2, aviso de queda) está em [docs/34-guia-deploy.md](docs/34-guia-deploy.md). No servidor, atualizar o site é `make deploy`; o backup e a restauração estão em [docs/31-guia-backup.md](docs/31-guia-backup.md).

Depois do site no ar, configure o **e-mail de envio** para ligar o cadastro de professores e o "Esqueci minha senha". Crie uma senha de app no Gmail e cole em **Administração → E-mail de envio**, que tem um botão de teste. Guia em [docs/35-guia-email.md](docs/35-guia-email.md). Sem isso, o site funciona, mas só o admin cria contas.

## Estrutura

```
backend/    Django (config/, apps/, templates/, static/)
frontend/   Vite e Tailwind (src/css, src/js)
infra/      Produção: Dockerfile, Compose, Caddy, backup e modelos de .env
docs/       Planejamento e decisões
```

## Contribuir e segurança

- Como contribuir: [`CONTRIBUTING.md`](CONTRIBUTING.md).
- Encontrou uma falha de segurança? Não abra issue pública; siga [`SECURITY.md`](SECURITY.md).

## Licença e créditos

Código sob a licença [MIT](LICENSE): pode usar, adaptar e redistribuir, mantendo o crédito.

Desenvolvido por Professor Marcos Felipe A. D. da Silva.
