# 30 — Versionamento

## Esquema

**Versionamento semântico** (SemVer): `MAIOR.MENOR.CORREÇÃO`, por exemplo `1.2.3`.

| Parte | Incrementa quando | Exemplo |
|---|---|---|
| MAIOR | Muda algo que altera a experiência de forma estrutural ou exige migração de dados não trivial; ou quando o jornal entra no ar pela primeira vez | `0.x` → `1.0.0` (MVP no ar); `1.x` → `2.0.0` (IA ou API pública) |
| MENOR | Uma fase ou um conjunto de funcionalidades novas é entregue sem quebrar o que existe | `1.0.0` → `1.1.0` (revisão opcional) |
| CORREÇÃO | Correções de bug, ajustes de texto, dependências | `1.1.0` → `1.1.1` |

Enquanto o sistema não está no ar, a versão fica em `0.MENOR.CORREÇÃO`, e cada etapa relevante pode subir a menor.

## Mapa de versões planejadas

| Versão | Marco |
|---|---|
| `0.0.1` | Repositório criado (E01) |
| `0.1.0` | Fase 0 concluída: fundação, site "em breve" no ar |
| `0.2.0` | Login, taxonomia e perfil funcionando (E07 a E10) |
| `0.3.0` | Editor e publicação funcionando (E11 a E17) |
| `0.4.0` | Páginas públicas completas (E18 a E26) |
| `0.9.0` | Deploy de produção e checklist (E27, E28), período de testes com colegas |
| `1.0.0` | Jornal no ar com uso real |
| `1.1.0` | Fase 2 |
| `1.2.0` | Fase 3 |
| `1.3.0` | Fase 4 |
| `2.0.0` | Fase 5 (IA) ou API pública, o que vier primeiro |

## Onde a versão aparece

- Rodapé de todas as páginas, discreto: `v1.2.3`, em `text-meta` e `ink-3`, à direita. Link para a página `/sobre/#versao` que lista as últimas mudanças em linguagem simples (opcional).
- `/healthz/` devolve a versão (útil para confirmar um deploy).
- Cabeçalho `X-App-Version` nas respostas (ajuda a depurar cache da Cloudflare).
- Painel: canto inferior do menu lateral.

## Mecânica

1. Arquivo `VERSION` na raiz do repositório com o número (`1.2.3`), sem `v`.
2. `config/settings/base.py` lê o arquivo para `APP_VERSION`; um context processor expõe `app_version` aos templates.
3. `CHANGELOG.md` na raiz, no formato Keep a Changelog, com seções `Adicionado`, `Alterado`, `Corrigido`, `Removido`, e uma seção `[Não lançado]` no topo onde as mudanças vão sendo anotadas a cada etapa.
4. `make release VERSION=1.2.0`:
   - verifica que a árvore está limpa e os testes passam;
   - escreve `VERSION`;
   - move `[Não lançado]` para `[1.2.0] - 2027-01-15` no `CHANGELOG.md`;
   - faz commit `release: v1.2.0` e cria a tag git `v1.2.0`;
   - lembra de fazer `git push --tags` e `make deploy`.
5. A imagem Docker recebe a tag da versão (`jornal:1.2.0`) além de `latest`.
6. Tags no GitHub geram "Releases" automáticas (workflow simples que copia a seção do changelog).

### Implementação

`scripts/release.py` (chamado por `make release VERSION=x.y.z`). Não roda os testes sozinho: o CI e `docker compose exec web uv run pytest` fazem isso antes. Também não faz push; depois de lançar, `git push --follow-tags`.

**Primeira versão lançada:** `v0.3.0`, reunindo os marcos 0.1.0 e 0.2.0, que não foram lançados separadamente. O site "em breve" da Fase 0 ainda depende do túnel da Cloudflare (E06) e ficará registrado numa versão de correção ou menor quando for publicado.

## Regras

- Nunca editar uma versão já lançada; corrigir com uma versão de correção.
- A versão no ar deve ser sempre uma tag existente no git.
- Migrações de banco que apagam ou transformam dados exigem ao menos uma versão MENOR e nota no changelog.

## Histórico

- 2026-09-12: criado a pedido do dono do projeto.
