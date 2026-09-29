# Como contribuir

Obrigado pelo interesse! O Jornal Escolar é mantido por um professor para o jornal da escola dele, mas o código é aberto (licença MIT) e pode ser adaptado por outras escolas.

## Antes de começar

- O planejamento completo está em [`docs/`](docs/README.md). As etapas ficam em [`docs/26`](docs/26-plano-de-desenvolvimento.md) e as decisões já tomadas em [`docs/27`](docs/27-decisoes-pendentes-e-perguntas.md).
- Para ideias grandes, abra uma issue antes de escrever código.
- Código, comentários, commits e documentação em **português do Brasil**.

## Rodar o projeto

Com Docker instalado, `docker compose up` e abra http://localhost:8000. Detalhes no [README](README.md).

## Antes de enviar um pull request

1. `make test` e `make lint` passando (ou, no Docker, `docker compose exec web uv run pytest`).
2. Testes para o que mudou.
3. Uma linha no `CHANGELOG.md`, seção `[Não lançado]`.
4. Regras de negócio em `services.py`, consultas em `selectors.py`, permissões só em `apps/editorial/permissions.py`, views finas. Mais convenções em [`CLAUDE.md`](CLAUDE.md).

## Privacidade

Nunca inclua dados reais de alunos, fotos de pessoas, nomes de escolas ou senhas em código, testes, issues ou pull requests. Use dados fictícios (o comando `seed_demo` cria um jornal de exemplo).
