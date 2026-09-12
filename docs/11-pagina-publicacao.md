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
│              Título (h1, Newsreader 36px)                    │
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
- `h2` 28px com espaço de 48px acima; `h3` 22px.
- Citações: filete esquerdo 3px na cor da área, itálico, `ink-2`.
- Imagens no corpo: largura da coluna; opção "larga" (até 900px) marcada no editor.
- Links sublinhados na cor de acento.
- Vídeos incorporados (Evolução): `iframe` do YouTube com `loading="lazy"` e fachada de clique para não carregar antes.

## Acessibilidade específica

- `article` com `aria-labelledby` do título.
- Legenda em `figcaption`; `alt` vindo do `MediaAsset`.
- Reações são botões com `aria-pressed` e rótulo textual.
- Tamanho de toque mínimo 44px nos botões de reação e compartilhamento.

## Histórico

- 2026-09-12: versão inicial.
- 2026-09-12: bloco de comentários públicos; créditos de aluno sem conta.
