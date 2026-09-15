# 10 — Página inicial

Rota: `/` · Nome: `core:home` · Camada: **MVP** · Fase 1 (filtros na Fase 3)

## Objetivo

Convidar a ler e mostrar, em uma tela, que o jornal é vivo e organizado por conhecimento. Um leitor que chega pela primeira vez deve entender em cinco segundos: o que é isto, o que há de novo, como navegar por área.

Não é um portal com dezenas de chamadas. É uma capa de revista com sumário.

## Estrutura (desktop)

```
┌──────────────────────────────────────────────────────────────┐
│ MASTHEAD  Nome do jornal · data ·           [busca] [Entrar] │
│ Linguagens · Matemática · Natureza · Humanas · Tecnologia ·  │
│ Artes · Agenda · Quem escreve · Sobre                        │
├──────────────────────────────────────────────────────────────┤
│ DESTAQUE                                                     │
│ ┌──────────────────────────┐  ┌───────────────────────────┐  │
│ │ card hero (imagem 16:9)  │  │ card standard (2º destaque)│  │
│ │ TIPO · ÁREA              │  ├───────────────────────────┤  │
│ │ Título display           │  │ card standard (3º destaque)│  │
│ │ Linha fina · byline      │  └───────────────────────────┘  │
│ └──────────────────────────┘                                 │
├───────────────────────────────────────┬──────────────────────┤
│ ÚLTIMAS PUBLICAÇÕES                   │ HOJE NA ESCOLA       │
│ card compact                          │ ☁ 23° · Nublado      │
│ card compact                          │ mín 17° · máx 26°    │
│ card compact                          ├──────────────────────┤
│ card compact                          │ AGENDA               │
│ card compact                          │ ▸ 18 set · Feira...  │
│ card compact                          │ ▸ 25 set · Sarau...  │
│ card compact                          │ ver agenda →         │
│ card compact                          ├──────────────────────┤
│ card compact                          │ QUEM ESCREVE         │
│ card compact                          │ avatares + nomes     │
│ [Carregar mais]                       │ ver todos →          │
├───────────────────────────────────────┴──────────────────────┤
│ POR ÁREA                                                     │
│ Ciências da Natureza ───────────────────────── ver tudo →    │
│ card standard │ card standard │ card standard                │
│ Linguagens ─────────────────────────────────── ver tudo →    │
│ card standard │ card standard │ card standard                │
│ (uma faixa por área ativa que tenha ao menos uma publicação) │
├──────────────────────────────────────────────────────────────┤
│ RODAPÉ                                                       │
└──────────────────────────────────────────────────────────────┘
```

No celular a ordem é: masthead, destaque (hero + dois compactos), clima em uma linha, últimas (cinco), agenda (três), faixas por área (dois cards cada, rolagem horizontal), quem escreve, rodapé.

## Blocos

### Destaque

- Até 3 publicações com `is_featured = true`, ordenadas por `featured_order`. Definidas por editor+ ([18](18-painel-administrativo.md)).
- Se não houver destaques marcados, usa as 3 mais recentes.
- O hero exige imagem de capa; se o primeiro destaque não tiver capa, usa layout tipográfico (título display sobre fundo `paper-2` com filete da área).

### Últimas publicações

- Publicadas, ordenadas por `published_at desc`, excluindo as do destaque. 6 por vez, "Carregar mais" via HTMX (`/x/articles/?pagina=2`).
- Card `compact`: etiqueta de tipo, título, byline, data, tempo de leitura, contagem de leituras discreta (só se > 10).

### Hoje na escola (Fase 3)

- Bloco pequeno com o tempo atual na escola, via Open-Meteo com cache de 30 minutos ([29](29-clima.md)). Some silenciosamente se a API falhar ou se `weather.enabled` estiver desligado.

### Agenda

- Publicações do tipo com `has_event_date` e `event_at >= hoje`, ordenadas por data, 4 itens. Link para `/agenda/`.
- Se não houver eventos futuros, o bloco mostra o último evento passado com rótulo "Aconteceu" ou some se não houver nenhum.

### Quem escreve

- 8 membros da equipe com perfil público, ordenados por publicação mais recente. Avatar + nome + headline curto. Link para `/professores/`.

### Por área

- Uma faixa por área ativa com ao menos 1 publicação, na ordem configurada. 3 cards `standard` mais recentes da área. Título da faixa na cor da área, com "ver tudo" para `/areas/<slug>/`.
- Limite de 5 faixas na home; as demais ficam na navegação.

## Filtros na home

Decisão: **a home não tem barra de filtros**. Filtrar é uma tarefa de quem já sabe o que procura; para isso existem a busca, as páginas de área/disciplina e a lista `/publicacoes/` com filtros completos ([12](12-paginas-de-navegacao.md)). Colocar filtros na home a transformaria em listagem. A navegação por áreas no masthead é o filtro principal.

## Dados e consultas

Uma única view monta o contexto com 5 consultas (destaques, últimas, agenda, professores, faixas por área com `prefetch_related`). Cache de fragmento de 5 minutos por bloco no `template` (invalidado ao publicar). Alvo: TTFB abaixo de 200ms no servidor.

## Ações disponíveis

| Ação | Quem |
|---|---|
| Abrir publicação, área, professor, agenda | Todos |
| Buscar | Todos |
| Entrar | Todos |
| Ir ao painel (se logado) | Usuários |

Editores não editam a home "in place"; usam o painel editorial. Isso mantém a home sem estado.

## SEO e compartilhamento

- `<title>` = nome do jornal + tagline. Meta description configurável.
- Open Graph com imagem padrão do jornal.
- JSON-LD `WebSite` com `SearchAction`.

## Estados

- **Sem nenhuma publicação**: estado vazio único no lugar de todos os blocos ("O jornal está sendo preparado").
- **Poucas publicações** (< 6): esconde as faixas por área e mostra só destaque + últimas.

## Métricas de sucesso da página

- Taxa de clique em ao menos uma publicação por visita acima de 60%.
- Tempo de carregamento no celular (LCP) abaixo de 2,5s em 4G.

## Histórico

- 2026-09-12: versão inicial.
- 2026-09-12: bloco de clima adicionado.
- 2026-09-12: E20 implementada (`apps/publications/home.py`, `templates/core/home.html`). Ajustes na prática:
  - Com 1 ou 2 destaques marcados, os lugares restantes são completados pelas mais recentes (antes: só "sem nenhum destaque").
  - "Carregar mais" das últimas usa a própria home (`/?pagina=2` com HTMX), não `/x/articles/`, que é o endpoint de filtros da Fase 3. O parâmetro de página é `pagina` em todo o site.
  - Faixas por área agrupam pela área principal (a da primeira disciplina), a partir das 60 publicações mais recentes, sem as do destaque: uma consulta para todas as faixas.
  - Cache: destaque, agenda, quem escreve e faixas ficam 5 minutos em cache com uma "versão do conteúdo público" que sobe ao publicar, editar, arquivar ou mudar créditos de algo que já foi ao ar (`publications/cache.py`). "Últimas" é sempre consultada (paginada).
  - Sem link "ver tudo", "ver agenda" e perfis até as páginas existirem (E21, E22). Clima fica para a Fase 3.
  - No celular, "Quem escreve" vem logo depois da agenda (antes das faixas), e o 2º e o 3º destaques usam o card `standard`.
  - `<title>` = nome · tagline; `h1` visualmente oculto com o nome do jornal. Lighthouse acessibilidade 100.
- 2026-09-14: E26: meta description vem da nova configuração `site.description` (se vazia, a tagline). JSON-LD `WebSite` sem `SearchAction` por enquanto: a busca (`/busca/`) só existe na Fase 3, e apontar para uma URL inexistente seria erro. Acrescentar o `SearchAction` junto com a busca. Open Graph com `static/img/og-default.png`.
- 2026-09-14: E36: JSON-LD `WebSite` ganhou o `SearchAction` (`/busca/?q={search_term_string}`).
