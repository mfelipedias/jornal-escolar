# 09 — Design system

## Direção visual

**Uma revista escolar bem diagramada, não um portal de notícias.** Referências de tom: cadernos de cultura de jornais impressos, revistas de divulgação científica, sites editoriais com tipografia forte e poucas imagens por tela. Tema **claro e colorido**, conforme pedido do dono do projeto: fundo claro, tipografia escura, e cor usada com intenção (acento rosa e uma cor por área do conhecimento).

Cinco palavras: editorial, claro, legível, colorido com critério, escolar sem ser infantil.

O que isso significa na prática:

- **Tipografia faz o trabalho.** Títulos em serifa com peso, corpo de texto em serifa confortável, interface em sans. Poucas imagens, bem tratadas.
- **Papel, não tela.** Fundo levemente quente, texto quase preto, linhas finas como separadores. Sem sombras pesadas, sem gradientes.
- **Cor com função.** O rosa de acento marca ações, links e a marca. As cores de área aparecem em etiquetas, filetes dos cards, títulos de seção da home e no cabeçalho das páginas de área: é isso que dá o "colorido" sem virar arco-íris.
- **Espaço em branco generoso.** A home não precisa mostrar tudo; precisa convidar a ler.
- **Sem infantilização.** Nada de mascotes, ícones em excesso, fontes arredondadas.

## Marca

- **Nome:** Jornal Escolar (padrão de `site.name`, editável no painel). **Tagline:** "Jornal digital da comunidade escolar". O nome da escola não aparece em lugar nenhum do site.
- **Wordmark:** "Jornal Escolar" em Newsreader 600, com "Escolar" na cor de acento. O wordmark é texto, não imagem, para acompanhar `site.name` se o nome mudar.
- **Glifo:** uma folha de jornal dobrada em traço único, monocromática, 24 a 32px, usada como favicon, ao lado do wordmark no masthead e como marca d'água nas imagens padrão de compartilhamento. Desenhado em SVG na etapa E04.
- **Não usar:** fotos ilustrativas na marca, gradientes, o glifo em tamanho grande como ilustração.

## Tokens

Definidos como variáveis CSS em `static/src/css/app.css` e expostos ao Tailwind 4 via `@theme`. Os valores abaixo são a proposta decidida; ajustes finos acontecem na etapa E04 olhando a tela.

### Cores base

| Token | Valor | Uso |
|---|---|---|
| `--color-paper` | `#FBF9F5` | Fundo da página |
| `--color-paper-2` | `#F1EDE6` | Fundos de seção, cabeçalho de tabela, campos |
| `--color-ink` | `#1B1A21` | Texto principal, títulos |
| `--color-ink-2` | `#4B4955` | Texto secundário, subtítulos |
| `--color-ink-3` | `#6B6875` | Metadados, legendas, placeholders (era `#7B7885`, ver Histórico) |
| `--color-line` | `#E0DBD2` | Bordas e separadores |
| `--color-accent` | `#A8174F` | Rosa da marca: links, botões primários, foco, "Escolar" no wordmark |
| `--color-accent-2` | `#8A1140` | Hover do acento |
| `--color-accent-soft` | `#FBE4EC` | Fundo de destaque suave, seleção |
| `--color-warn` | `#B45309` | Avisos |
| `--color-danger` | `#B42318` | Erros, ações destrutivas |
| `--color-ok` | `#1F7A4D` | Sucesso, publicado |

Contraste: `ink` sobre `paper` é cerca de 16:1; `accent` sobre `paper` é cerca de 6.5:1; `ink-3` sobre `paper` é cerca de 5.2:1 e sobre `paper-2` cerca de 4.7:1.

### Cores por área do conhecimento

Cada `KnowledgeArea` escolhe uma cor entre estas oito, mais vivas que em um jornal tradicional. Usadas em etiquetas (texto escuro sobre fundo claro), filete superior dos cards, título da faixa da área na home e cabeçalho da página de área (fundo claro da cor, texto escuro).

| Nome | Escuro (texto) | Claro (fundo) | Sugestão de área |
|---|---|---|---|
| coral | `#B23A1F` | `#FDE6DF` | Linguagens e suas Tecnologias |
| verde | `#2F7A3E` | `#E2F3E4` | Ciências da Natureza |
| azul | `#1D5FB8` | `#E1EBFA` | Matemática e suas Tecnologias |
| âmbar | `#8F5A00` | `#FBEFD3` | Ciências Humanas e Sociais Aplicadas |
| violeta | `#6A3FB5` | `#ECE4FA` | Formação e Projetos |
| petróleo | `#1C6F6B` | `#DDF2F0` | Escola e Comunidade |
| magenta | `#A8174F` | `#FBE4EC` | Reservada (mesma do acento; usar só se uma área precisar) |
| grafite | `#4A4F5A` | `#E9EAEE` | Reservada / Geral |

### Tipografia

| Papel | Fonte | Fallback | Onde |
|---|---|---|---|
| Display e títulos | **Newsreader** (variável, eixo óptico) | Georgia, serif | Títulos de página, de publicação, de card |
| Corpo de leitura | **Newsreader** 400, tamanho 18 a 19px, entrelinha 1.6 | Georgia, serif | Corpo da publicação |
| Interface | **Inter** (variável) | system-ui, sans-serif | Navegação, botões, formulários, metadados, painel |

Fontes auto-hospedadas (licença OFL), com `font-display: swap`, vindas dos pacotes `@fontsource-variable/newsreader` (eixo óptico, com itálico) e `@fontsource-variable/inter` e servidas pelo próprio site a partir do build do Vite. Sem Google Fonts em produção: evita requisição externa e rastreamento.

Escala (desktop; mobile reduz um passo nos maiores):

| Token | Tamanho | Uso |
|---|---|---|
| `text-display` | 44/48px | Título da publicação em destaque na home |
| `text-h1` | 36px | Título da publicação, título de página |
| `text-h2` | 28px | Seções da home, subtítulos internos |
| `text-h3` | 22px | Título de card |
| `text-lead` | 21px | Linha fina |
| `text-body` | 18px | Corpo de leitura |
| `text-ui` | 15px | Interface |
| `text-meta` | 13px | Metadados, etiquetas |

### Espaçamento e grade

- Escala de 4px: 4, 8, 12, 16, 24, 32, 48, 64, 96.
- Largura máxima do site: 1200px. Coluna de leitura: 68 caracteres (cerca de 700px).
- Grade de 12 colunas no desktop, 6 no tablet, 4 no celular. Gutter 24px (16px no celular).
- Margens laterais mínimas: 16px no celular, 32px no tablet, 48px no desktop.

### Raios, bordas, sombras

- Raio: 4px em campos e botões; 8px em imagens e cards; sem raio em separadores.
- Bordas: 1px `line`. Cards não têm borda em todos os lados; usam filete superior de 3px na cor da área e separadores horizontais.
- Sombra: apenas em menus suspensos e diálogos (`0 8px 24px rgba(23,25,30,.12)`).

### Movimento

- Transições de 150ms em hover e foco. Nada de animação de entrada em conteúdo. Respeitar `prefers-reduced-motion`.

## Navegação

### Cabeçalho público (masthead)

Duas linhas no desktop, uma no celular.

- **Linha 1**: glifo + wordmark "Jornal Escolar" (Newsreader, 28px) à esquerda; à direita: busca (ícone que expande campo), "Entrar" ou avatar do usuário.
- **Linha 2**: áreas do conhecimento como links de texto, na ordem configurada, cada uma com um ponto na cor da área antes do nome; "Agenda"; "Quem escreve"; "Sobre". Área ativa sublinhada na cor da área.
- No celular: glifo + wordmark + ícone de busca + menu.
- Data por extenso pequena abaixo do nome, opcional via configuração.

### Rodapé

Três linhas, todas em `text-meta`:

1. Links: Sobre · Privacidade · Como participar · RSS.
2. Crédito (configurável em `site.footer_credit`): "Desenvolvido por Professor Marcos Felipe A. D. da Silva · marcossilva06@professor.educacao.sp.gov.br". O e-mail é um link `mailto:` e é o contato para pedidos de privacidade.
3. À direita, a versão do sistema (`v1.2.3`, `ink-3`).

Sem nome, endereço ou logotipo da escola.

### Painel

Barra lateral fixa no desktop (colapsa em ícones no tablet, vira menu no celular): Início, Minhas publicações, Nova publicação, Revisões, Comentários, Sugestões (Fase 4), Pautas (Fase 4), Perfil, Conta. Editor+ vê "Editorial". Admin vê `/admin/`. Sino de notificações no cabeçalho. Versão no rodapé do menu.

## Componentes

| Componente | Descrição | Variantes |
|---|---|---|
| `card` | Publicação: filete de área, etiqueta de tipo, título, linha fina, byline, metadados (data, tempo de leitura), imagem opcional | `hero` (imagem grande, título display), `standard` (imagem 3:2 acima), `compact` (sem imagem, lista), `mini` (título + data, para sidebar) |
| `byline` | Avatares empilhados (até 3) + nomes com papel: "Por Carla Souza e Rafael S." | com/sem avatar |
| `tag` | Etiqueta de área (colorida), disciplina (contorno), tipo (preenchida neutra), tópico (texto com `#` discreto) | tamanho `sm`/`md` |
| `status-badge` | Estado editorial: rascunho (cinza), em revisão (ocre), alterações (terracota), aprovado (azul), publicado (verde), arquivado (grafite) | |
| `filter-bar` | Chips de filtro ativos + botão "Filtrar" que abre painel; no celular é uma folha inferior | |
| `pagination` | "Carregar mais" via HTMX no público; numeração no painel | |
| `empty-state` | Ilustração em linha (traço simples), título curto, uma frase, uma ação | |
| `toast` | Feedback de ação no canto inferior; some em 4s; acessível via `aria-live` | sucesso, erro, info |
| `dialog` | Confirmações (arquivar, publicar); `<dialog>` nativo | |
| `form-field` | Rótulo acima, ajuda abaixo, erro em `danger`, contador de caracteres quando há limite | |
| `button` | `primary` (acento), `secondary` (contorno), `ghost` (texto), `danger` | tamanhos `sm`/`md` |
| `reaction-bar` | Quatro botões com emoji e contagem; estado ativo com fundo `paper-2` | |
| `editor-toolbar` | Botões do TipTap: parágrafo/títulos, negrito, itálico, link, lista, citação, imagem, separador, desfazer | |
| `comment-thread` | Comentário editorial com trecho citado, respostas, botão resolver | |
| `public-comment` | Comentário de leitor: nome, data, texto, resposta da equipe destacada com filete no acento | público, moderação (com botões) |
| `comment-form` | Nome + texto + honeypot + aviso de moderação | |
| `weather` | Ícone em linha, temperatura, condição, mín/máx | |
| `notification-bell` | Ícone com contador; lista suspensa | |
| `timeline` | Eventos editoriais em lista vertical com data | |
| `stat` | Número grande + rótulo, para painel | |

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
- Erros de servidor: página 500 com o nome do jornal e um link para a home; nada de stack trace.
- 404 com busca embutida.
- Publicações arquivadas respondem 410 com mensagem "Esta publicação foi retirada do ar".

## Responsividade

| Breakpoint | Largura | Comportamento |
|---|---|---|
| celular | < 640px | Uma coluna; cards `compact`; menu; filtros em folha inferior; editor com toolbar fixa no rodapé |
| tablet | 640 a 1023px | Duas colunas na home; painel com sidebar em ícones |
| desktop | ≥ 1024px | Grade completa; painel com sidebar aberta |

Imagens sempre com `srcset` das variantes (480, 960, 1600) e `loading="lazy"` fora da primeira dobra.

## Acessibilidade

- Contraste mínimo AA em todo texto; AAA no corpo de leitura.
- Navegação por teclado completa; foco visível (anel de 2px na cor de acento).
- Um `h1` por página; ordem lógica de títulos.
- Texto alternativo obrigatório nas imagens (o editor exige ou marca como decorativa).
- `aria-live` para toasts e resultados de filtro.
- Tamanho de fonte respeita zoom do navegador (unidades `rem`).
- Skip link para o conteúdo.
- Formulários com rótulos reais, não placeholders.

## Modo escuro

Fora do escopo por decisão do dono do projeto. Preparação sem custo: todas as cores são tokens, nenhum valor de cor é escrito direto nos templates. Quando houver pedido, basta um bloco `[data-theme="dark"]` redefinindo os tokens (`paper` → `#15141A`, `ink` → `#ECE9E2`, `line` → `#2B2A33`, áreas com fundo escuro dessaturado).

## Histórico

- 2026-09-12: versão inicial.
- 2026-09-12: nome e marca "Jornal da Rosa"; acento rosa; áreas mais vivas com nomes da escola; componentes de comentário, clima e notificação; versão no rodapé; modo escuro fora do escopo.
- 2026-09-12: nome genérico "Jornal Escolar" a pedido do dono do projeto; glifo trocado de rosa para folha de jornal; a cor de acento rosa se mantém.
- 2026-09-12: E18: Lighthouse mostrou que `ink-3 #7B7885` tinha contraste 4,1:1 (não 4,6:1) em texto de 13px; token escurecido para `#6B6875`.
- 2026-09-12: E19: componentes em `templates/components/` (`card`, `byline`, `tag`, `status_badge`, `empty_state`, `pagination`, `toast`) e vitrine em `/dev/components/` (aberta com `DEBUG` ou para o papel admin). O card recebe um `ArticleCard` (`publications/presentation.py`), não o modelo. Toast: sucesso e informação somem em 4s; **erro e aviso ficam até fechar** (sumir sozinho faria quem lê devagar perder a mensagem); mensagens do Django em respostas HTMX viram toast pelo `HtmxMessagesMiddleware`. Âmbar de área escurecido de `#9A6200` para `#8F5A00` (4,46:1 → 5,07:1 sobre `ambar-soft`). Status "publicado" usa o verde de área em vez de `ok` sobre fundo claro.
- 2026-09-12: E20: card `hero` com imagem 16:9 em cima e texto embaixo (cabe na coluna de 2/3 da home); sem capa, vira bloco tipográfico em `paper-2` com filete da área. Paginação usa `?pagina=N` (tag `page_url`).
- 2026-09-12: E04 implementada. Tokens em `frontend/src/css/app.css` (cores de área como `area-coral`, `area-coral-soft` etc.); glifo em `templates/components/glyph.html` e `static/img/favicon.svg`. Masthead provisório sem busca, "Entrar" e linha de áreas (chegam em E36, E09 e E21); rodapé sem a linha de links até as páginas existirem. Data do masthead em minúsculas ("sábado, 12 de setembro de 2026").
- 2026-09-14: E36: busca no masthead é um ícone que abre um campo em popover abaixo da linha da marca, em qualquer largura (sem JavaScript, o ícone leva a `/busca/`). No celular, com sessão aberta, "Escrever" e "Admin" saem da linha 1 (continuam no painel) para caber em 390px. Termo encontrado no trecho usa `<mark>` com `accent-soft` (classe `search-snippet`).
