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

- Campos `search_vector` (`SearchVectorField`, índice GIN) e `search_meta` (texto) em `Article`. Código em `apps/publications/search.py`.
- Atualizado pelos services (não por sinal) sempre que muda algo que entra no vetor: criar, duplicar, editar título/linha fina/corpo, metadados, créditos, revisor, publicar, anonimizar crédito ou conta, atualizar nome nos créditos e correção pelo admin. Monta `SearchVector('title', weight='A', config='pt_unaccent') + ...`. Única exceção por sinal: disciplina ou tópico renomeado reindexa as publicações ligadas.
- Todas as publicações têm vetor (qualquer estado); a consulta pública filtra `published`.
- `manage.py reindex_search` refaz tudo e é idempotente (após restaurar backup ou mudar a configuração).
- Extensões: `unaccent` (função imutável `f_unaccent` para poder indexar), `pg_trgm`.
- Configuração de texto: `portuguese` com `unaccent` encadeado (dicionário criado por migração: `CREATE TEXT SEARCH CONFIGURATION pt_unaccent (COPY = portuguese); ALTER ... MAPPING ... WITH unaccent, portuguese_stem`). Vetor e consulta usam a mesma configuração `pt_unaccent`.

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
| `periodo` | `30-dias`, `semestre`, `ano` | relativo a hoje; ignorado se houver `de` ou `ate` |
| `de`, `ate` | `AAAA-MM-DD` | inclusivos; invertidos são trocados |
| `ordem` | `recentes` (padrão), `lidas`; na busca `relevancia` (padrão) e `recentes` | `lidas` usa `reads_count` (a partir da E39) |
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
- 2026-09-14 (E35): o vetor usa `pt_unaccent`, não `portuguese` (com configurações diferentes, "fisica" não encontraria "Física"); `search_meta` virou campo; lista dos pontos que atualizam o índice e o comando `reindex_search`.
- 2026-09-14 (E36): página `/busca/`. Trecho com `SearchHeadline` usando marcas de uso privado do Unicode no lugar de `<mark>`; o HTML é montado em Python depois de escapar o texto (`search.highlight`), porque o PostgreSQL devolve o corpo como está (tags não reconhecidas, como `<img src=x onerror=...>`, passam). Fallback de títulos: além de `TrigramSimilarity > 0.3` no título inteiro, `TrigramWordSimilarity > 0.5` (um erro de digitação numa palavra de título longo não passava de 0.3); ambos sem acento (`f_unaccent`). Pessoas: nome com similaridade > 0.25 ou similaridade de palavra > 0.5, apresentação curta com similaridade de palavra > 0.5 (a similaridade do texto inteiro de "Professora de Biologia" com "biologia" fica abaixo de 0.25) ou disciplina do perfil que contenha o termo; só perfis públicos de contas ativas, até 5. Grupo de taxonomia também traz áreas; tópico (sem página própria) leva à busca pelo nome dele. Termo com até 100 caracteres; limite de 60 buscas por minuto por IP (`SEARCHES_PER_MINUTE`). Cache de 60s por filtros fica para a E37, com os demais filtros.
- 2026-09-14 (E37): filtros `professor` (endereço do perfil; conta créditos visíveis, como a aba "Todas" do perfil, só perfis públicos de contas ativas), `periodo` (predefinidos relativos a hoje, para a URL compartilhada continuar valendo; semestre = janeiro a junho ou julho a dezembro), `de`/`ate` e `ordem`. "Mais lidas" fica fora até a E39; na busca a ordem padrão é relevância. Cache de 60s implementado em `publications/listing.py`: a chave usa a página, os filtros já normalizados (não a querystring crua, então parâmetros repetidos, fora de ordem ou desconhecidos caem na mesma chave), o termo e o número da página, com a versão de `publications/cache.py`; guarda o total e os cards montados.
