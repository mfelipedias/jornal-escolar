# 19 — Busca e filtros

Camada: **MVP** · Fase 3

## Decisão

PostgreSQL full-text search é suficiente ([D5](05-arquitetura-tecnica.md)). Volume esperado: centenas a poucos milhares de publicações, dezenas de professores. Meilisearch ou similar só se houver problema medido.

## O que é pesquisável

| Alvo | Campos | Peso |
|---|---|---|
| Publicação | `title` | A |
| | `subtitle` | B |
| | nomes de disciplinas, tópicos e contribuidores (concatenados em `search_meta`) | B |
| | `body_text` | C |
| Equipe | `display_name`, `headline`, nomes de disciplinas | busca separada por similaridade de trigramas |
| Comentários | — | Não são pesquisáveis |
| Disciplina e tópico | `name` | correspondência por prefixo e trigramas |

Só publicações `published` entram na busca pública. O painel tem busca própria por título nos rascunhos do usuário.

## Implementação

### Índice

- Campo `search_vector` (`SearchVectorField`) em `Article`, com índice GIN.
- Atualizado no `save()` do service de publicação (não por sinal), montando `SearchVector('title', weight='A', config='portuguese') + ... `.
- Extensões: `unaccent` (função imutável `f_unaccent` para poder indexar), `pg_trgm`.
- Configuração de texto: `portuguese` com `unaccent` encadeado (dicionário criado por migração: `CREATE TEXT SEARCH CONFIGURATION pt_unaccent (COPY = portuguese); ALTER ... MAPPING ... WITH unaccent, portuguese_stem`).

### Consulta

- `SearchQuery(q, config='pt_unaccent', search_type='websearch')`: permite aspas para frase e `-` para excluir.
- Ranking por `SearchRank` com pesos `[0.1, 0.2, 0.4, 1.0]` e desempate por `published_at`.
- Trechos com `SearchHeadline` sobre `body_text` (até 200 caracteres, termo em `<mark>`).
- Fallback: se zero resultados, tenta similaridade de trigramas no título (`TrigramSimilarity > 0.3`) para tolerar erros de digitação.
- Professores: `TrigramSimilarity` em `display_name` e `headline`, limite 0.25, até 5 resultados.
- Disciplinas e tópicos: `name__unaccent__icontains`.

### Tela de resultados

Ver [12](12-paginas-de-navegacao.md). Três grupos, filtros laterais iguais aos da lista de publicações, aplicáveis sobre a busca.

## Filtros

Parâmetros de querystring aceitos por `/publicacoes/`, páginas de área/disciplina/tipo e `/busca/`:

| Parâmetro | Valores | Notas |
|---|---|---|
| `q` | texto | só em `/busca/` |
| `area` | slug | um |
| `disciplina` | slug, repetível | vários (OR) |
| `tipo` | slug, repetível | vários (OR) |
| `topico` | slug, repetível | vários (OR) |
| `professor` | slug | um |
| `de`, `ate` | `AAAA-MM-DD` | |
| `ordem` | `recentes` (padrão), `lidas` | `lidas` usa `reads_count` |
| `pagina` | inteiro | 12 por página |

- Filtros combinados com AND entre parâmetros diferentes.
- O formulário funciona por GET sem JavaScript; com HTMX, substitui a grade e atualiza a URL.
- Contagem de resultados é exibida; contagens por opção de filtro (facetas) são Evolução.

## Performance

- Consultas de listagem: `select_related('type', 'cover')`, `prefetch_related('disciplines', 'contributors__user')`.
- Cache de 60s por combinação de filtros nas páginas públicas (chave normalizada da querystring), invalidado ao publicar/arquivar.
- Alvo: busca em menos de 100ms para 5 mil publicações.

## Evolução

- Sugestões ao digitar (`/x/search/suggest/`): 5 títulos por prefixo + trigramas, com debounce de 250ms.
- Facetas com contagens.
- Busca semântica por embeddings (Fase 5, congelada).

## Histórico

- 2026-09-12: versão inicial.
