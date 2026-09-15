# 09 — Design system

## Direção visual: "Pátio"

**Um mural de pátio bem diagramado: jovem, colorido, com energia, e ainda assim editorial e legível.** Em 2026-09-15 o dono do projeto viu o site pronto e achou o design "muito sério" para o público: alunos do ensino médio ([27](27-decisoes-pendentes-e-perguntas.md), quarta rodada). A direção anterior ("uma revista escolar bem diagramada", tema claro com cor usada com parcimônia) foi substituída por esta, mantendo o que ela tinha de bom: tipografia forte, leitura confortável, cor com função.

Referências de tom: revistas juvenis de ciência e cultura, cartazes de grêmio bem feitos, sites de festivais e de escolas de design. Cinco palavras: **vivo, colorido, ágil, claro, nosso.**

O que isso significa na prática:

- **Duas vozes tipográficas.** Títulos e interface em uma grotesca expressiva e pesada (Bricolage Grotesque); corpo de leitura em serifa confortável (Newsreader). O contraste entre as duas é a personalidade do site.
- **Cor de verdade.** Um acento vivo (framboesa), um marca-texto amarelo para destacar palavras e blocos, e as oito cores de área em três intensidades: escura para texto, clara para fundos e viva para blocos e formas. Gradientes discretos entre a versão clara e o papel são permitidos em faixas e cabeçalhos.
- **Formas macias.** Pílulas em botões, chips e etiquetas; cards com cantos de 16px; hero com 24px. Sombras suaves e coloridas no hover.
- **Movimento com propósito.** Cards levantam, imagens dão zoom leve, seções entram com fade escalonado, o masthead encolhe ao rolar. Tudo curto (150 a 250ms) e desligado com `prefers-reduced-motion`.
- **Ainda editorial.** Hierarquia clara, espaço em branco, uma coluna de leitura de 68 caracteres. O jornal continua sendo para ler.

O que **não** muda (continua proibido):

- **Infantilização**: nada de mascote, fontes "arredondadas de criança", emojis como ícones ou excesso de ícones.
- Contraste **AA em todo texto**, AAA no corpo de leitura.
- O nome da escola em qualquer lugar do site.
- Cor escrita direto no template: só tokens (`bg-paper`, `text-area-verde`, `bg-sun`).

## Marca

- **Nome:** Jornal Escolar (padrão de `site.name`, editável no painel). **Tagline:** "Jornal digital da comunidade escolar". O nome da escola não aparece em lugar nenhum do site.
- **Wordmark:** "Jornal Escolar" em Bricolage Grotesque 800, com a última palavra em `accent` e um traço de marca-texto (`sun`) inclinado atrás dela (classe `wordmark-accent`, em `app.css`). O wordmark é texto, não imagem, para acompanhar `site.name` se o nome mudar; o context processor separa a última palavra (`wordmark_head`, `wordmark_accent`).
- **Glifo:** um **avião de papel dobrado de uma página de jornal**, em traço único com duas linhas de "texto" na asa, monocromático, `currentColor`. Vive em `templates/components/glyph.html` (parâmetro `class` para tamanho e cor). No masthead fica em `accent`, 28 a 32px; no hover do link da marca ele inclina (`.masthead-logo`). No rodapé, em `accent-soft`, 40px.
- **Favicon e ícones:** `static/img/favicon.svg` (glifo branco sobre quadrado arredondado no acento), `favicon.ico` (32px), `apple-touch-icon.png` (180), `icon-192.png`, `icon-512.png`, `logo.png` (512, usado no JSON-LD) e `og-default.png` (1200×630, imagem padrão de compartilhamento: glifo no acento sobre papel com um traço de marca-texto). `static/manifest.json` descreve nome, cores e ícones para a tela inicial do celular. Os PNGs, o ICO e o manifest são gerados por `scripts/brand.py` (Pillow) a partir da mesma geometria do SVG: ao mudar o desenho, mudar nos três lugares (glyph.html, favicon.svg, brand.py) e rodar `uv run --directory backend python ../scripts/brand.py`.
- **Não usar:** fotos ilustrativas na marca, o glifo em tamanho grande como ilustração de página (só em estados vazios, dentro de um "adesivo"), nem versões em outras cores além de `accent`, `ink` e branco.

## Tokens

Definidos como variáveis CSS em `frontend/src/css/app.css` e expostos ao Tailwind 4 via `@theme`. Contrastes medidos com `scripts` de apoio (WCAG 2.x, relação de luminância); a tabela abaixo é o valor atual.

### Cores base

| Token | Valor | Uso | Contraste |
|---|---|---|---|
| `--color-paper` | `#FFFDF7` | Fundo da página | — |
| `--color-paper-2` | `#F6F1E4` | Fundos de seção, cabeçalho de tabela, campos, etiqueta de tipo | — |
| `--color-paper-3` | `#EDE6D3` | Blocos mais marcados (adesivos, faixas neutras) | — |
| `--color-ink` | `#17151F` | Texto principal, títulos | 17,7:1 sobre paper; 14,5:1 sobre paper-3 |
| `--color-ink-2` | `#47454F` | Texto secundário, linha fina | 9,3:1 sobre paper; 7,6:1 sobre paper-3 |
| `--color-ink-3` | `#67646F` | Metadados, legendas, placeholders (13px) | 5,7:1 sobre paper; 4,7:1 sobre paper-3 e accent-soft |
| `--color-line` | `#E6E0D2` | Bordas e separadores | — |
| `--color-accent` | `#C41260` | Framboesa da marca: links, botões primários, foco, "Escolar" no wordmark | 5,7:1 sobre paper; 4,7:1 sobre paper-3; branco sobre ele 5,8:1 |
| `--color-accent-2` | `#9C0D4D` | Hover do acento, texto pequeno em accent | 8,0:1 sobre paper |
| `--color-accent-soft` | `#FFE1EE` | Fundo de destaque suave, chip ativo | — |
| `--color-sun` | `#FFD23F` | Marca-texto: fundo atrás de palavras, adesivos, barras. **Nunca como texto.** | ink sobre ele 12,5:1 |
| `--color-sun-soft` | `#FFF3C4` | Seleção de texto, fundos de aviso leve | — |
| `--color-warn` | `#B45309` | Avisos | |
| `--color-danger` | `#B42318` | Erros, ações destrutivas | |
| `--color-ok` | `#1F7A4D` | Sucesso | |

O briefing propôs `accent #D6156A`; ficou em `#C41260` porque o original dava 4,0:1 sobre `paper-3` e 4,1:1 sobre `accent-soft`, abaixo de AA. A versão `#D6156A` sobrevive como `area-magenta-bright`.

### Cores por área do conhecimento

Cada `KnowledgeArea` escolhe uma cor entre estas oito. Três intensidades por cor:

- **escura** (`area-x`): texto sobre fundos claros, pontos do menu, barras finas;
- **clara** (`area-x-soft`): fundo de etiquetas, faixas da home, cabeçalho da página de área;
- **viva** (`area-x-bright`): blocos, formas decorativas, marcadores, gradientes com a versão clara. O texto sobre a viva é `ink` ou branco, o que passar 4,5:1 (`on_bright` em `taxonomy.AREA_COLOR_CLASSES`).

| Nome | Escura (texto) | Clara (fundo) | Viva (blocos) | Texto sobre a viva | Sugestão de área |
|---|---|---|---|---|---|
| coral | `#B23A1F` | `#FDE6DF` | `#E4552F` | ink (4,9:1) | Linguagens e suas Tecnologias |
| verde | `#2F7A3E` | `#E2F3E4` | `#2FA65A` | ink (5,8:1) | Ciências da Natureza |
| azul | `#1D5FB8` | `#E1EBFA` | `#2563EB` | branco (5,2:1) | Matemática e suas Tecnologias |
| âmbar | `#8F5A00` | `#FBEFD3` | `#F5A524` | ink (8,8:1) | Ciências Humanas e Sociais Aplicadas |
| violeta | `#6A3FB5` | `#ECE4FA` | `#A78BFA` | ink (6,1:1) | Formação e Projetos |
| petróleo | `#1C6F6B` | `#DDF2F0` | `#14B8A6` | ink (7,3:1) | Escola e Comunidade |
| magenta | `#C41260` | `#FFE1EE` | `#D6156A` | branco (5,0:1) | Reservada (mesma do acento) |
| grafite | `#4A4F5A` | `#E9EAEE` | `#64748B` | branco (4,8:1) | Reservada / Geral |

A escura sobre a clara da mesma cor passa 4,5:1 em todas (mínimo: magenta 4,8:1, verde 4,6:1).

### Tipografia

| Papel | Fonte | Fallback | Onde |
|---|---|---|---|
| Display, títulos e interface | **Bricolage Grotesque** (variável, eixos opsz/wdth/wght) | "Bricolage Fallback" (Arial com métricas ajustadas), system-ui | Títulos de página, de publicação, de card; navegação, botões, formulários, metadados, painel |
| Corpo de leitura | **Newsreader** 400, 18px, entrelinha 1.6 | "Newsreader Fallback" (Georgia com métricas ajustadas) | Corpo da publicação, linha fina, citações |

Classes: `font-display` (títulos: `font-variation-settings: "opsz" 96`, tracking -0.02em, `text-wrap: balance`), `font-sans` (interface, a mesma fonte) e `font-serif` (leitura). Inter saiu na R1: uma grotesca só para display e interface deixa o site mais coeso e carrega menos.

Fontes auto-hospedadas (licença OFL), `font-display: swap`, dos pacotes `@fontsource-variable/bricolage-grotesque` e `@fontsource-variable/newsreader`, servidas pelo próprio site a partir do build do Vite. Sem Google Fonts.

Escala (desktop; o celular reduz os maiores em `app.css`, `@media (width < 40rem)`):

| Token | Desktop | Celular | Uso |
|---|---|---|---|
| `text-display` | 52px (3.25rem) | 36px | Título da publicação em destaque na home |
| `text-h1` | 36px | 30px | Título da publicação, título de página |
| `text-h2` | 32px | 26px | Seções da home, subtítulos internos |
| `text-h3` | 22px | 22px | Título de card |
| `text-lead` | 21px | | Linha fina |
| `text-body` | 18px | | Corpo de leitura |
| `text-ui` | 15px | | Interface |
| `text-meta` | 13px | | Metadados, etiquetas |

### Carregamento sem salto

O dono reclamou de ver "um emoji e uma página toda quebrada" até a página se montar. Causa: o CSS era importado pelo JavaScript, então o HTML aparecia sem estilo até o script rodar (no modo dev do Vite isso é bem visível). Regras desde a R1:

- `src/css/app.css` é uma **entrada própria do Vite** e `base.html` a carrega com `<link rel="stylesheet" href="{% vite_asset_url 'src/css/app.css' %}">` **antes** do JavaScript. Em dev o link aponta para o servidor do Vite (que responde CSS para o navegador); em produção, para o arquivo do build.
- `{% font_preloads %}` (`apps/core/templatetags/assets.py`) pré-carrega as duas fontes da primeira tela (Bricolage e Newsreader, alfabeto latino, eixo óptico) a partir dos nomes com hash do build. Em dev não faz nada.
- Fallbacks com métricas (`size-adjust`, `ascent-override`, `descent-override`) para Arial e Georgia, para o texto ocupar quase o mesmo espaço enquanto a fonte de verdade chega.
- `[x-cloak] { display: none }` está no CSS carregado por `<link>`, então componentes do Alpine não piscam abertos.

### Espaçamento e grade

- Escala de 4px: 4, 8, 12, 16, 24, 32, 48, 64, 96.
- Largura máxima do site: 1200px. Coluna de leitura: 68 caracteres (cerca de 700px).
- Grade de 12 colunas no desktop, 6 no tablet, 4 no celular. Gutter 24px (16px no celular).
- Margens laterais mínimas: 16px no celular, 32px no tablet, 48px no desktop (`.site-container`).

### Raios, bordas, sombras

- Raios: `radius-field` 12px em campos, botões e chips (pílulas usam `radius-pill` 999px); `radius-card` 16px em imagens e cards; `radius-hero` 24px no destaque da home e nos cabeçalhos coloridos; sem raio em separadores.
- Bordas: 1px `line`. O "filete superior de 3px na cor da área" dos cards sai na R3; a área passa a aparecer como etiqueta pílula ou barra lateral arredondada.
- Sombras: `shadow-popover` (`0 12px 32px rgb(23 21 31 / .14)`) em menus e diálogos; `shadow-card-hover` (`0 12px 32px rgb(196 18 96 / .18)`, o acento a 18%) em cards no hover.

### Movimento

Regras gerais (implementação na R5, exceto o que R2 a R4 já usarem):

- Curva padrão `--ease-snappy` (`cubic-bezier(.2,.8,.2,1)`), 200ms em transformações e 150ms em cor. Foco e hover sempre com transição.
- **Cards:** `translateY(-4px)` + `shadow-card-hover` + imagem `scale(1.04)` no hover. **Links de texto:** sublinhado que desliza (`background-size`). **Botões:** levantam 1px no hover e encolhem para `scale(.97)` ao pressionar.
- **Entrada:** seções da home e cards aparecem com fade + `translateY(12px)`, escalonados por `nth-child` (até 6), quando entram na tela (`IntersectionObserver` em `app.js` adiciona `is-visible`). Sem JavaScript nada fica escondido.
- **Masthead:** `position: sticky`, fundo `paper` a 85% com `backdrop-filter: blur(12px)`; encolhe depois de rolar (`is-scrolled` via JS).
- **Reações:** `scale(1.15)` com bounce curto ao pressionar. **Toasts:** deslizam de baixo. **Filtros no celular:** a folha inferior desliza.
- **Entre páginas:** `@view-transition { navigation: auto }` e `htmx.config.globalViewTransitions = true` (fade curto onde o navegador suporta).
- **`prefers-reduced-motion: reduce` desliga tudo isso** (transições e animações a 0.01ms; conteúdo já visível).

## Navegação

### Cabeçalho público (masthead)

Duas linhas, fixas no topo (`.masthead`: `position: sticky`, fundo `paper` a 85% com `backdrop-filter: blur(12px)`; todo elemento com `id` tem `scroll-margin-top` para âncoras não sumirem atrás dele).

- **Linha 1**: glifo (avião, `accent`) + wordmark à esquerda; à direita: data por extenso (opcional via configuração), busca (ícone que abre um campo em popover), "Entrar" (pílula) ou, com sessão, "Escrever", sino, Painel, nome e Sair.
- **Linha 2**: barra de chips (`.nav-chip`): cada área do conhecimento é um chip com um ponto na cor da área (`solid_bg`), na ordem configurada; "Agenda"; "Quem escreve"; "Sobre". Hover: fundo `paper-2`. Chip ativo (`aria-current`): fundo `area-x-soft` e texto `area-x` (ou `accent-soft`/`accent-2` para os fixos), peso 600.
- No celular: glifo + wordmark + busca + "Entrar"; a linha 2 rola na horizontal, sem barra de rolagem, com as bordas esmaecidas (`mask-image`). Busca e sino usam `.icon-btn` (40px, redondo). Com sessão aberta, "Escrever" e "Admin" ficam só no painel para a linha 1 caber em 390px.
- Encolhe ao rolar: `.masthead.is-scrolled` reduz o padding da linha da marca (classe pronta; o JS que a liga é da R5).

### Rodapé

Faixa escura: fundo `ink`, texto `paper` (secundário a 70%, versão a 50%), links em `accent-soft` com hover `sun`; wordmark com `.wordmark-accent--on-dark`. Conteúdo:

1. Glifo grande em `accent` + wordmark + tagline.
2. Links: Sobre · Privacidade · Como participar · RSS (a partir da E43).
3. Crédito (configurável em `site.footer_credit`): "Desenvolvido por Professor Marcos Felipe A. D. da Silva · marcossilva06@professor.educacao.sp.gov.br". O e-mail é um link `mailto:` e é o contato para pedidos de privacidade.
4. À direita, a versão do sistema (`v1.2.3`, discreta).

Sem nome, endereço ou logotipo da escola.

### Painel

Barra lateral fixa no desktop (colapsa em ícones no tablet, vira menu no celular): Início, Minhas publicações, Nova publicação, Revisões, Comentários, Sugestões (Fase 4), Pautas (Fase 4), Perfil, Conta. Editor+ vê "Editorial". Admin vê `/admin/`. Sino de notificações no cabeçalho. Versão no rodapé do menu. Herda fontes e tokens; itens do menu viram pílulas (R5).

## Componentes

| Componente | Descrição | Variantes |
|---|---|---|
| `card` | Publicação: etiqueta de área (pílula `soft`, é onde a cor da área aparece), etiqueta de tipo, título em Bricolage, linha fina, byline, metadados; o filete superior de 3px saiu | `hero` (imagem `radius-hero`, título display; sem capa, bloco com gradiente `soft`→`paper-3` da área), `standard` (cartão branco `.card` com imagem 3:2 em `.card-media`; levanta 4px, sombra `shadow-card-hover` e zoom da imagem no hover; sem capa, bloco na cor da área com o glifo), `compact` (linha `.card-row` com barra lateral de 4px na cor da área, fundo `paper-2` no hover), `mini` (`.card-row--mini`: título + data) |
| `byline` | Avatares empilhados (até 3) + nomes com papel: "Por Carla Souza e Rafael S." | com/sem avatar |
| `tag` | Etiqueta de área (pílula `soft` + texto `area-x`), disciplina (contorno), tipo (pílula `paper-2`), tópico (texto com `#` discreto) | tamanho `sm`/`md` |
| `status-badge` | Estado editorial: rascunho (cinza), em revisão (ocre), alterações (terracota), aprovado (azul), publicado (verde), arquivado (grafite) | |
| `filter-bar` | Chips de filtro ativos + botão "Filtrar" (pílula) que abre painel; no celular é uma folha inferior com cantos `radius-hero` | |
| `pagination` | "Carregar mais" (pílula) via HTMX no público; numeração no painel | |
| `empty-state` | "Adesivo" (`components/sticker.html`: círculo `sun-soft` com o glifo), título curto em Bricolage, uma frase, uma ação | `compact`; `heading="h1"` quando é a página inteira |
| `toast` | Feedback de ação no canto inferior, com borda esquerda na cor do nível; entra deslizando de baixo; some em 4s; acessível via `aria-live` | sucesso, erro, aviso, info |
| `dialog` | Confirmações (arquivar, publicar); `<dialog>` nativo | |
| `form-field` | Rótulo acima, ajuda abaixo, erro em `danger`, contador de caracteres quando há limite; campo com `radius-field` | |
| `button` | Pílulas (`.btn-*`): `primary` (accent, texto branco), `secondary` (contorno), `ghost` (texto), `danger`; levantam 1px no hover e encolhem a 97% ao pressionar. `.icon-btn`: botão redondo só com ícone | tamanhos `sm`/`md` |
| `reaction-bar` | Título "O que você achou?" com marca-texto e quatro pílulas com emoji e contagem; ativa com fundo `accent-soft`; bounce ao pressionar (R5). Na publicação, fica num `.panel` junto com leituras e compartilhar | |
| `editor-toolbar` | Botões do TipTap: parágrafo/títulos, negrito, itálico, link, lista, citação, imagem, separador, desfazer | |
| `comment-thread` | Comentário editorial com trecho citado, respostas, botão resolver | |
| `public-comment` | Comentário de leitor em `.panel--flush` (cartão branco): inicial em `sun-soft`, nome em Bricolage, data, texto; resposta da equipe em `.comment-reply` (barra de 4px `accent`, fundo rosado claro, nome de quem respondeu em `accent-2`); contador de aprovados em pílula `paper-2` ao lado do título | público, moderação (com botões) |
| `comment-form` | Cartão `.panel`: título em Bricolage, aviso de moderação logo abaixo, nome + texto (`.field`) + honeypot, botão primário "Enviar comentário" | |
| `weather` | Cartãozinho com fundo `area-azul-soft`, ícone em `accent`, temperatura em Bricolage, condição, mín/máx e chance de chuva; no celular, uma pílula em linha | `aside`, `line` |
| `notification-bell` | Ícone com contador; lista suspensa | |
| `timeline` | Eventos editoriais em lista vertical com data | |
| `stat` | Número grande em Bricolage 800 + rótulo, para painel; com link, levanta no hover | |
| `glyph` | Avião de papel da marca | parâmetro `class` |
| `event-item` | Item de agenda: dia grande em Bricolage sobre bloco `paper-2` (vira `sun-soft` no hover), mês em caixa alta, título, horário e local | `sm`, `md` |
| `chip` | Opção de filtro (`.chip` + `.chip-label`): pílula branca; marcada em `accent-soft`; `.nav-chip` no masthead | |
| `field` | Campo de formulário (`.field`): raio 12px, foco com anel `accent` a 25% | |

### Utilitários de layout (R3)

| Classe | Uso |
|---|---|
| `.page-header` | Cabeçalho de página em faixa colorida: só o espaçamento; a cor vem do template (`bg-linear-to-b` + `from_soft` da área, ou `from-accent-soft`/`from-sun-soft` nas páginas sem área, até `to-paper`) |
| `.band` | Faixa de borda a borda com fundo `soft` da área (faixas por área da home) |
| `.title-marker` | Marca-texto `sun` atrás do título de seção, que acompanha as quebras de linha (`box-decoration-break: clone`). Uso: `<h2><span class="title-marker">…</span></h2>`. É o único recurso de título de seção do site |
| `.card`, `.card-media`, `.card-media--blank`, `.card-row`, `.card-row--mini` | Cards (ver `card` acima) |
| `.btn-sm` | Botão pequeno ("ver todas", "ver tudo") |
| `.link-arrow` | Link em acento com seta que desliza no hover ("Ver agenda completa", "Ver toda a equipe") |
| `.panel`, `.panel--flush` | Cartão branco com contorno `line` (R4): `radius-hero` e padding generoso; `--flush` com `radius-card` e padding menor. Créditos, reações, formulário de comentário, comentários, telas de entrada e 500 |
| `.comment-reply` | Resposta da equipe a um comentário (R4) |
| `.status-code` | Código de erro gigante e decorativo (`aria-hidden`), em accent a 14% (R4) |
| `.auth-backdrop` | Gradiente suave `accent-soft` → `sun-soft` → `paper` das telas de entrada e do 500 (R4) |

Classes por área usadas nesses blocos ficam escritas por extenso em `AREA_COLOR_CLASSES` (`apps/taxonomy/models.py`), porque o Tailwind só gera o que encontra no código: `text`, `soft_bg`, `solid_bg`, `border`, `bright_bg`, `from_soft` (início do gradiente) e `on_bright`.

## Estados vazios (textos de referência)

| Onde | Título | Texto | Ação |
|---|---|---|---|
| Home sem publicações | "O jornal está sendo preparado" | "As primeiras publicações aparecem aqui em breve." | — |
| Disciplina sem publicações | "Ainda não há publicações em Física" | "Professores desta disciplina podem ser os primeiros." | "Ver outras disciplinas" |
| Busca sem resultado | "Nada encontrado para 'x'" | "Tente termos mais gerais ou navegue por área." | Lista de áreas |
| Minhas publicações vazia | "Você ainda não escreveu nada" | "Comece por um rascunho. Ele fica só com você até publicar." | "Nova publicação" |
| Revisões vazia | "Nenhuma revisão pedida a você" | "Quando um colega pedir sua leitura, aparece aqui." | — |
| Comentários vazia | "Nenhum comentário aguardando" | "Comentários novos das suas publicações aparecem aqui para você aprovar." | — |
| Publicação sem comentários | "Ainda não há comentários" | "Seja a primeira pessoa a comentar." | Formulário |
| Sugestões vazias | "Sem sugestões por enquanto" | "Adicione interesses ao seu perfil para receber pautas." | "Editar interesses" |

## Feedback e erros

- Toda ação com POST devolve um toast ou uma mudança visível no fragmento (ex.: botão de reação muda de estado).
- Erros de validação aparecem ao lado do campo, e o primeiro recebe foco.
- Erros de servidor: página 500 (`templates/500.html`) independente do resto: o Django a renderiza sem request e sem context processors, então ela não consulta o banco, não usa `{{ jornal }}` (por isso não cita o nome do jornal, que é editável) e carrega o CSS pela tag `{% stylesheet_url_or_empty %}`, que devolve vazio se o build do Vite faltar. Cartão branco sobre `.auth-backdrop`, adesivo, "Algo deu errado" e botão para a home; nada de stack trace.
- 404 e 403 (`components/status_hero.html`): faixa colorida, código gigante decorativo (`.status-code`), adesivo por cima, título display; 404 com busca embutida e botão para a home.
- Publicações arquivadas respondem 410 com o mesmo topo, sem código, "Esta publicação foi retirada do ar" e botões para a área e para as mais recentes.
- Telas de entrada (login, sair, link de acesso, avisos do allauth, 429): `layouts/auth.html` com `.auth-backdrop`, marca acima e o conteúdo num `.panel` com `shadow-popover`; botão principal largo. Com o login Microsoft ligado, ele é o primário e "Entrar com senha" fica secundário.

## Responsividade

| Breakpoint | Largura | Comportamento |
|---|---|---|
| celular | < 640px | Uma coluna; cards `compact`; menu; filtros em folha inferior; editor com toolbar fixa no rodapé; títulos um passo menores |
| tablet | 640 a 1023px | Duas colunas na home; painel com sidebar em ícones |
| desktop | ≥ 1024px | Grade completa; painel com sidebar aberta |

Imagens sempre com `srcset` das variantes (480, 960, 1600) e `loading="lazy"` fora da primeira dobra.

## Acessibilidade

- Contraste mínimo AA em todo texto; AAA no corpo de leitura. Cores vivas (`bright`, `sun`) só com o texto medido acima ou como decoração.
- Navegação por teclado completa; foco visível (anel de 2px na cor de acento).
- Um `h1` por página; ordem lógica de títulos.
- Texto alternativo obrigatório nas imagens (o editor exige ou marca como decorativa).
- `aria-live` para toasts e resultados de filtro.
- Tamanho de fonte respeita zoom do navegador (unidades `rem`).
- Skip link para o conteúdo.
- Formulários com rótulos reais, não placeholders.
- Todo movimento respeita `prefers-reduced-motion`; nada pisca, nada rola sozinho.

## Modo escuro

Fora do escopo por decisão do dono do projeto. Preparação sem custo: todas as cores são tokens, nenhum valor de cor é escrito direto nos templates. Quando houver pedido, basta um bloco `[data-theme="dark"]` redefinindo os tokens (`paper` → `#15141A`, `ink` → `#ECE9E2`, `line` → `#2B2A33`, áreas com fundo escuro dessaturado).

## Histórico

- 2026-09-12: versão inicial.
- 2026-09-12: nome e marca "Jornal da Rosa"; acento rosa; áreas mais vivas com nomes da escola; componentes de comentário, clima e notificação; versão no rodapé; modo escuro fora do escopo.
- 2026-09-12: nome genérico "Jornal Escolar" a pedido do dono do projeto; glifo trocado de rosa para folha de jornal; a cor de acento rosa se mantém.
- 2026-09-12: E18: Lighthouse mostrou que `ink-3 #7B7885` tinha contraste 4,1:1 (não 4,6:1) em texto de 13px; token escurecido para `#6B6875`.
- 2026-09-12: E19: componentes em `templates/components/` e vitrine em `/dev/components/`. Toast: sucesso e informação somem em 4s; erro e aviso ficam até fechar. Âmbar de área escurecido para `#8F5A00`. Status "publicado" usa o verde de área.
- 2026-09-12: E20: card `hero` com imagem 16:9 em cima e texto embaixo; sem capa, vira bloco tipográfico em `paper-2`. Paginação usa `?pagina=N`.
- 2026-09-12: E04 implementada: tokens em `frontend/src/css/app.css`; glifo em `templates/components/glyph.html` e `static/img/favicon.svg`.
- 2026-09-14: E36: busca no masthead é um ícone que abre um campo em popover. No celular, com sessão aberta, "Escrever" e "Admin" saem da linha 1. Termo encontrado no trecho usa `<mark>` com `accent-soft`.
- 2026-09-15: **R1 (Fase 3b, redesign "Pátio")**, a pedido do dono ([27](27-decisoes-pendentes-e-perguntas.md), quarta rodada; plano em [26](26-plano-de-desenvolvimento.md)). Direção visual reescrita; revogadas as regras "nada de animação de entrada", "sem gradientes" e "sem sombras pesadas". Tipografia: Bricolage Grotesque para display e interface (Inter removida), Newsreader continua na leitura; classe `font-display` nos títulos; escala com display 52px e h2 32px. Tokens: `paper` mais claro, `paper-3` novo, acento framboesa `#C41260` (o `#D6156A` do briefing falhava AA sobre `paper-3` e `accent-soft`), `sun`/`sun-soft`, cores vivas `area-x-bright` com `on_bright` medido, raios 12/16/24 e pílula, `shadow-card-hover`, `--ease-snappy`. Marca nova: avião de papel de jornal (glifo, favicon SVG/ICO, ícones PNG, manifest, `og-default.png` e `logo.png` gerados por `scripts/brand.py`); wordmark com marca-texto. Carregamento sem salto: CSS como entrada própria do Vite carregada por `<link>` antes do JS, preload das fontes (`{% font_preloads %}`), fallbacks com métricas. `theme-color` passa a `#FFFDF7`.
- 2026-09-15: **R2**: masthead fixo e translúcido com barra de chips (`.nav-chip`), botões de ícone (`.icon-btn`), busca em pílula; rodapé em faixa escura com marca, tagline e links; botões, chips, campos, etiquetas, selos e paginação em pílulas com hover que levanta e `active` que encolhe; reação ativa em `accent-soft`; toast com borda colorida deslizando de baixo; estado vazio com "adesivo" (`sun-soft` + glifo); avatares maiores com iniciais em `sun-soft`; clima como cartão `area-azul-soft`; `scroll-margin-top` em todo `id`. Vitrine `/dev/components/` com seção de tokens (cores, áreas soft/bright, tipografia), botões, chips, campos, agenda, clima, números e compartilhar.
- 2026-09-15: **R3**: cards sem filete superior (cor da área na etiqueta e, nas listas, numa barra lateral), `standard` como cartão branco que levanta com zoom na imagem e bloco com o glifo quando não há capa; `hero` com `radius-hero`. Utilitários `.page-header`, `.band`, `.title-marker`, `.card*`, `.btn-sm`, `.link-arrow`; `from_soft` em `AREA_COLOR_CLASSES`. Títulos de seção passam de caixa alta pequena para Bricolage 800 com marca-texto.
- 2026-09-15: **R4**: página da publicação com cabeçalho em faixa (gradiente `soft` da área → `paper`, alinhado à coluna de leitura), título display, disciplinas como etiquetas, evento com bloco de calendário, capa com `radius-hero`; reações, leituras e compartilhar num `.panel`; "Quem fez" em `.panel` com marca-texto; comentários e formulário em cartões (`.panel--flush`, `.comment-reply`); "Leia também" em `.band`. Corpo: intertítulos em Bricolage, links em `accent-2` (8,0:1, AAA) com sublinhado `accent` e hover `sun-soft`, citação com barra `accent` de 4px e aspas grandes em `accent-soft`, separador como filete curto `sun`. Corpo continua AAA: `ink` 17,7:1, `ink-2` (citações) 9,3:1 sobre `paper`. Institucionais com `.page-header` em `accent-soft`. 404/403/410 com `status_hero`, 500 independente (`stylesheet_url_or_empty`), telas de entrada com `.auth-backdrop` e `.panel`. Adesivo extraído para `components/sticker.html`.
- 2026-09-15: clima no masthead, embaixo da data (pedido do dono): uma linha `text-meta` com ícone de 16px no acento; abaixo de 1024px só ícone e graus; no celular abre a barra de chips. Com sessão aberta, nome e "Admin" só a partir de 1280px e "Sair" some no celular (fica no painel), para a linha 1 não estourar em 390px e 1024px.
