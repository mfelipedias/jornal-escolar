# 12 — Páginas de navegação

Todas públicas. Camada **MVP**, exceto onde indicado.

## Lista de publicações com filtros

Rota: `/publicacoes/` · Nome: `publications:list` · Fase 1 (filtros completos na Fase 3)

**Objetivo.** Ser a única página de "listar tudo" com filtros combináveis. Área, disciplina, tipo e professor são atalhos que chegam aqui com filtro pré-aplicado, mas têm cabeçalhos próprios (abaixo).

**Estrutura.**
- Cabeçalho: "Publicações" + contagem ("128 publicações").
- Barra de filtros (`filter-bar`): chips ativos removíveis; botão "Filtrar" abre painel com: área (rádio), disciplina (checkbox, filtradas pela área), tipo (checkbox), professor (autocomplete), período (predefinidos: 30 dias, semestre, ano; ou intervalo), ordem (mais recentes, mais lidas).
- Grade de cards `standard` (3 colunas desktop, 1 no celular), 12 por página, "Carregar mais".
- URL reflete o estado (`?area=natureza&tipo=projeto&ordem=lidas`), compartilhável, e a página funciona sem JS (formulário GET).

**Comportamento HTMX.** Mudar um filtro faz GET em `/x/articles/?...` e substitui a grade; `hx-push-url` mantém o histórico.

## Página de área

Rota: `/areas/<slug>/` · Nome: `taxonomy:area`

- Cabeçalho na cor da área: nome, descrição curta, lista de disciplinas como chips (link para cada uma).
- Destaque: publicação mais recente da área em card `hero` (se tiver capa).
- Grade das demais, com a mesma barra de filtros pré-fixada na área (chip "Área: Ciências da Natureza" não removível).
- Bloco "Professores desta área": avatares e nomes.

## Página de disciplina

Rota: `/disciplinas/<slug>/` · Nome: `taxonomy:discipline`

- Cabeçalho: nome, área (link), descrição.
- Grade de publicações com filtro fixo.
- "Professores de Física": avatares.
- Estado vazio específico ([09](09-design-system.md)).

## Página de tipo

Rota: `/tipos/<slug>/` · Nome: `taxonomy:type`

- Idêntica à lista, com tipo fixo. Ex.: `/tipos/entrevistas/`, `/tipos/projetos/`.

## Página de tópico (Evolução, Fase 3)

Rota: `/topicos/<slug>/` · Nome: `taxonomy:topic`

- Nome, disciplinas relacionadas, publicações com o tópico. Não aparece na navegação principal; chega-se por etiquetas.

## Agenda

Rota: `/agenda/` · Nome: `publications:agenda`

- Lista cronológica de publicações com `event_at`, separadas em "Próximos" e "Já aconteceram".
- Cada item: dia e mês em destaque, título, local, área. Link para a publicação.
- Botão "Assinar agenda" gera `.ics` com todos os eventos futuros (Evolução, Fase 6).

## Quem escreve

Rota: `/professores/` · Nome: `accounts:teacher_list`

- Grade de cards da equipe: avatar (ou iniciais), nome, cargo, headline, disciplinas (chips), número de publicações.
- Filtro por área e por cargo (chips no topo): Professores, Monitores, Coordenação e direção, Outros.
- Ordenação padrão: publicação mais recente primeiro; alternativa alfabética.
- Só perfis com `is_public = true`. Alunos não têm conta e não aparecem.

## Busca

Rota: `/busca/?q=` · Nome: `search:results` · Fase 3

Ver [19](19-busca-e-filtros.md). Resumo da tela:
- Campo de busca grande no topo com o termo.
- Resultados agrupados: "Publicações" (lista com trecho destacado), "Professores" (cards pequenos), "Disciplinas e tópicos" (chips).
- Filtros laterais iguais aos da lista.
- Estado vazio com sugestões de áreas.

## Páginas estáticas

Rotas: `/sobre/`, `/privacidade/`, `/colaborar/` · Nome: `core:page`

- Conteúdo de `StaticPage`, editado no admin com o mesmo editor das publicações.
- Layout de coluna de leitura, sem sidebar.
- "Como participar" (`/colaborar/`) explica que alunos participam entregando textos a um professor, que a equipe entra pelo admin, e como pedir remoção de nome ou comentário; inclui o e-mail de contato do rodapé. Não menciona o nome da escola.
- "Privacidade" explica cookies, comentários (nome público), créditos de alunos e ausência de rastreadores.

## Páginas de erro

- 404: "Não encontramos esta página" + campo de busca + links de áreas.
- 410: "Esta publicação foi retirada do ar" + link para a área.
- 500: nome do jornal + "Algo deu errado do nosso lado" + link para a home.

## Histórico

- 2026-09-12: versão inicial.
- 2026-09-12: "Quem escreve" com cargos; páginas estáticas ajustadas.
- 2026-09-12: E21 implementada: `/publicacoes/`, `/areas/<slug>/`, `/disciplinas/<slug>/`, `/tipos/<slug>/` e `/agenda/` (`publications/listing.py`, `taxonomy/views.py`). Na prática:
  - Filtros da E21: área (uma), disciplina e tipo (várias, combinadas com "ou" dentro do mesmo campo e "e" entre campos). O painel abre num `<details>` com formulário GET, sem JavaScript; chips removíveis mostram o que está aplicado. Professor, período, ordem, HTMX na troca de filtro e folha inferior no celular ficam na E37.
  - Com uma área escolhida, o formulário só oferece as disciplinas dela e disciplinas de outra área vindas pela URL são ignoradas. Remover o chip da área remove também as disciplinas.
  - "Carregar mais" usa a própria página (`?pagina=N` com HTMX), como a home; `/x/articles/` continua reservado para a E37.
  - Página de área: "Professores desta área" virou "Quem escreve sobre a área", com quem marcou a área ou uma disciplina dela no perfil ou já publicou nela; sem link até o perfil público existir (E22). O destaque `hero` só aparece sem filtros e com capa.
  - Agenda: próximos (todos) e "Já aconteceram" com 20 por página, numerada.
- 2026-09-14: E22 implementada: `/professores/` ("Quem escreve"). Na prática:
  - Filtros são links (chips) com `?area=`, `?cargo=` (`professores`, `monitores`, `coordenacao`, `outros`; sala de leitura entra em "Outros") e `?ordem=nome`. O filtro por área usa o mesmo critério da página de área: marcou a área ou uma disciplina dela no perfil, ou já publicou nela.
  - Número de publicações conta toda publicação publicada com o nome nos créditos (respeitando "mostrar crédito como revisor"), como a aba "Todas" do perfil.
  - Sem paginação: a equipe de uma escola cabe numa página.
  - Nomes em "Quem escreve sobre a área", na home e em "Quem fez" da publicação levam ao perfil (se público); a home e a página de área ganharam "Ver toda a equipe". "Quem escreve" entrou no cabeçalho.
  - Cabeçalho ganhou a linha de áreas (nome curto, ponto na cor da área, sublinhado na área atual), Agenda e Sobre; no celular a linha rola na horizontal em vez de abrir menu.
