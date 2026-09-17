# 11 — Página de publicação

Rota: `/publicacoes/<slug>/` · Nome: `publications:detail` · Camada: **MVP** · Fase 1 (reações e leituras na Fase 3)

## Objetivo

Leitura confortável, crédito claro a quem fez, e caminhos para continuar lendo. Esta é a página mais visitada do site e a que define a percepção de qualidade.

## Estrutura

```
┌──────────────────────────────────────────────────────────────┐
│ MASTHEAD                                                     │
├──────────────────────────────────────────────────────────────┤
│              [ÁREA] [TIPO]              ← etiquetas          │
│              Título (h1, Bricolage 800, display)             │
│              Linha fina (lead, ink-2)                        │
│              ● ● Por Carla Souza e Rafael S. · 12 set 2026   │
│              6 min de leitura · Física, Matemática           │
├──────────────────────────────────────────────────────────────┤
│              ┌────────────────────────────────────┐          │
│              │ imagem de capa (3:2 ou 16:9)       │          │
│              └────────────────────────────────────┘          │
│              legenda · crédito da foto                       │
│                                                              │
│              Corpo do texto em coluna de 68 caracteres       │
│              h2, parágrafos, imagens com legenda, citações,  │
│              listas, links, separadores                      │
│                                                              │
│              ─────────                                       │
│              Fontes e referências (se houver)                │
│              1. Título — Publicação, data. link              │
│                                                              │
│              👍 24  💡 12  ❤️ 8  👏 3     · 143 leituras     │
│              [Compartilhar: link · WhatsApp]                 │
├──────────────────────────────────────────────────────────────┤
│ QUEM FEZ                                                     │
│ ┌ avatar ─ Carla Souza ─ Professora de Biologia ─ ver perfil │
│   Rafael S. ─ Aluno, 2ª série B                              │
│ Com colaboração de: Prof. Carlos (fotos)                     │
│ Revisão: Prof. Marcos                                        │
├──────────────────────────────────────────────────────────────┤
│ COMENTÁRIOS (4)                        (Fase 3)              │
│ Mariana · 12 set                                             │
│ Adorei a parte sobre os sensores!                            │
│    ↳ Resposta de Carla Souza (autora)                        │
│ ...                                                          │
│ Deixe um comentário  [nome] [texto] [Enviar]                 │
│ "Seu comentário aparece depois que o autor aprovar."         │
├──────────────────────────────────────────────────────────────┤
│ LEIA TAMBÉM                                                  │
│ card standard │ card standard │ card standard                │
├──────────────────────────────────────────────────────────────┤
│ RODAPÉ                                                       │
└──────────────────────────────────────────────────────────────┘
```

## Componentes e dados

| Bloco | Dados | Regras |
|---|---|---|
| Etiquetas | Área principal (da primeira disciplina) e tipo | Clicáveis |
| Título e linha fina | `title`, `subtitle` | |
| Byline | Contribuições `author` e `coauthor` na ordem | Equipe linka ao perfil; alunos e créditos sem conta não têm link |
| Metadados | `published_at`, `reading_minutes`, disciplinas (todas, clicáveis) | Se `updated` após publicação, mostra "Atualizado em" |
| Evento | `event_at`, `event_location` | Só para tipos com data; bloco em destaque acima do corpo com botão "Adicionar ao calendário" (arquivo .ics) |
| Capa | `cover` com `srcset`, `cover_caption`, `credit` | |
| Corpo | `body_html` | Renderizado no servidor; imagens com `figure`/`figcaption`; links externos com `rel="noopener"` |
| Fontes | `sources` | Lista numerada; obrigatória quando `origin_news_item` existe |
| Reações | `reactions_count` + estado do visitante | Ver [20](20-reacoes-leituras-comentarios.md) |
| Leituras | `reads_count` | Exibido só se ≥ 10 e se o autor não desligou, texto "143 leituras" em `ink-3` |
| Compartilhar | Copiar link; WhatsApp (`https://wa.me/?text=`); Web Share API no celular | Sem SDKs de redes sociais |
| Quem fez | Todas as contribuições com `show_in_credits` | Equipe com link e headline; alunos com "Aluno" e turma; sem link |
| Comentários (Fase 3) | `Comment` aprovados, mais formulário | Só se `comments_enabled`; ver [20](20-reacoes-leituras-comentarios.md) |
| Leia também | 3 publicações que compartilham disciplina ou tópico, excluindo a atual, mais recentes | Fase 3 refina com pontuação por tópicos em comum |

## Ações

| Ação | Quem | Como |
|---|---|---|
| Reagir | Todos | POST HTMX, troca a barra |
| Comentar | Todos | POST; resposta "Recebido, aguardando aprovação" |
| Compartilhar | Todos | JS local |
| Editar | Autores, editor+ | Botão discreto no topo, só para logados com permissão; leva ao editor |
| Ver histórico editorial | Editor+ | Link no botão de edição |

## Comportamentos

- **Beacon de leitura** dispara após `reads.min_seconds` (padrão 15s) e rolagem de ao menos 25% do corpo. Ver [20](20-reacoes-leituras-comentarios.md).
- **Rascunhos e não publicados**: acessíveis pela mesma rota apenas para quem tem permissão, com faixa amarela "Pré-visualização — não publicado" no topo. Isso permite revisar com o mesmo layout final.
- **Arquivada**: 410 com mensagem e links para a área.
- **Slug alterado**: nunca ocorre após publicação. Antes disso, não há URL pública.

## SEO e compartilhamento

- `<title>` = título + nome do jornal.
- Meta description = linha fina ou primeiros 160 caracteres do `body_text`.
- Open Graph e Twitter Card com capa (variante 1600).
- JSON-LD `NewsArticle` ou `Article` conforme o tipo, com autores (equipe com URL do perfil; alunos como `Person` sem URL), `datePublished`, `dateModified`, `publisher` (= `site.name`, por padrão "Jornal Escolar", nunca o nome da escola).
- URL canônica.

## Tipografia do corpo

- Largura de 68 caracteres. Parágrafos em Newsreader 18px/1.6; primeiro parágrafo sem capitular (evitar afetação).
- `h2` 32px em Bricolage 800 com espaço acima; `h3` 22px em Bricolage 700.
- Citações: barra esquerda de 4px em `accent`, aspas grandes decorativas em `accent-soft`, itálico, `ink-2`.
- Separador: filete curto (64px) em `sun`, centralizado.
- Imagens no corpo: largura da coluna; opção "larga" (até 900px) marcada no editor.
- Links em `accent-2` (8,0:1, AAA) com sublinhado de 2px em `accent`; hover com fundo `sun-soft`.
- Vídeos incorporados (Evolução): `iframe` do YouTube com `loading="lazy"` e fachada de clique para não carregar antes.

## Acessibilidade específica

- `article` com `aria-labelledby` do título.
- Legenda em `figcaption`; `alt` vindo do `MediaAsset`.
- Reações são botões com `aria-pressed` e rótulo textual.
- Tamanho de toque mínimo 44px nos botões de reação e compartilhamento.

## Histórico

- 2026-09-12: versão inicial.
- 2026-09-12: bloco de comentários públicos; créditos de aluno sem conta.
- 2026-09-14: E26 implementada (`apps/core/seo.py`, `apps/publications/seo.py`, `templates/components/seo.html`). Na prática:
  - Cada view pública monta um `PageMeta` ("seo" no contexto); o `base.html` gera description, canônico, Open Graph, Twitter Card e JSON-LD a partir dele. Endereços absolutos usam `SITE_URL`, não o Host da requisição.
  - `NewsArticle` para os tipos Notícia, Reportagem, Entrevista e Evento; `Article` para os demais. `publisher` é `NewsMediaOrganization` com `site.name` e o logo `static/img/logo.png` (glifo, sem texto).
  - Autores = autores e coautores com "mostrar nos créditos". Equipe com `url` só se o perfil for público; alunos e convidados só com `name` (sem turma, sem URL). Sem autor, o jornal assina.
  - `og:image` = variante 1600 da capa (WebP) com largura, altura e `alt`; sem capa, a imagem padrão `static/img/og-default.png` (1200×630, glifo sem texto, para não fixar o nome do jornal).
  - Pré-visualização: `noindex`, sem canônico e sem JSON-LD.
  - Compartilhar virou o componente Alpine `share` (`frontend/src/js/app.js`): cópia pela Clipboard API com plano B (campo com o link selecionado) fora de HTTPS; WhatsApp funciona sem JavaScript.
- 2026-09-15: **R4 (redesign "Pátio", [09](09-design-system.md))**: cabeçalho em faixa com o gradiente suave da área (sem área, `accent-soft`), etiquetas pílula, título display em Bricolage, byline e data na mesma linha no desktop, disciplinas como etiquetas, evento com bloco de calendário; capa com cantos de 24px. Reações, contador de leituras e compartilhar ficam num cartão branco logo depois do texto (e das fontes); "Quem fez" em cartão branco com duas colunas no desktop; comentários como cartões, resposta da equipe com barra em `accent`, contador em pílula, formulário em cartão; "Leia também" em faixa `paper-2`. "Editar" para quem pode editar vira botão pequeno. Publicação retirada (410) com adesivo e botões. Estrutura e ordem dos blocos não mudaram.
- 2026-09-17: **E43**: "Leia também" refinado como previsto. Pontuação: cada tópico em comum vale 2 e cada disciplina em comum vale 1; empate pela mais recente. Decisão nova: quando há menos de 3, completa com as mais recentes da mesma área (nunca de outra área, para não sugerir algo sem relação); sem disciplina nem tópico, o bloco some. Cards em cache de 60s com a versão do conteúdo público (`publications/cache.py`), que agora também sobe ao mudar os tópicos de uma publicação ou editar um tópico. Tópicos ativos aparecem como etiquetas `#tópico` abaixo das disciplinas e levam à página de tópico. Feed RSS 2.0 em `/feed/` (`publications/feeds.py`, `publications:feed`): 20 mais recentes, `description` = linha fina ou 300 caracteres do texto, `dc:creator` com a byline da página, disciplinas e tipo em `category`, endereços com `SITE_URL` (o framework "sites" do allauth diria example.com); `<link rel="alternate">` no `base.html` e link "RSS" no rodapé; cache de 60s.
