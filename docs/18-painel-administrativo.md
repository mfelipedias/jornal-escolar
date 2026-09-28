# 18 — Painel administrativo

Duas camadas:

1. **Editorial** (`/painel/editorial/`): para editores, dentro do painel, com a cara do jornal. Fase 2.
2. **Administração** (`/admin/`): Django Admin, para o administrador. Fase 1.

Decisão: **não construir um painel administrativo customizado**. O Django Admin, bem configurado (list_display, filtros, buscas, inlines, ações), resolve taxonomia, usuários, configurações e fontes com uma fração do esforço. Só o que o editor usa diariamente ganha tela própria.

## Editorial (editor+)

Rota: `/painel/editorial/` · Nome: `editorial:overview`

### Visão geral
- Contadores por estado: rascunhos (com autor), em revisão, alterações sugeridas, publicados nos últimos 30 dias, arquivados; comentários pendentes no total.
- Alertas: revisões paradas há mais de 5 dias; comentários pendentes há mais de 3 dias; publicações com crédito de aluno sem autorização marcada (não deveria existir; indica dado antigo).

### Todas as publicações
- Tabela com filtros por estado, tipo, área, autor, revisor, período. Busca por título.
- Ações em massa: arquivar, reatribuir revisor.
- Clique leva à revisão.

### Destaques da home
- Lista ordenável (arrastar ou setas) dos até 3 destaques atuais; botão "Adicionar" com busca entre publicadas. Exige capa.
- Pré-visualização pequena de como fica o bloco de destaque.

### Créditos e correções
- Editor pode abrir qualquer publicação no editor e ajustar créditos, disciplinas ou texto; gera evento `edited_by_third_party` com nota obrigatória e notifica o autor.
- Anonimizar crédito de aluno em um clique ("aluno da 2ª série") quando uma família pedir.

### Comentários
- Fila com todos os pendentes do jornal (não só das próprias publicações), com as mesmas ações da fila do autor.

### Páginas estáticas
- Editar "Sobre", "Como colaborar", "Privacidade" com o mesmo editor.

## Administração (Django Admin)

### Usuários e perfis
- `User`: lista com e-mail, nome, papel, cargo, ativo, último login, método de login; filtros por papel, cargo e ativo; ações: desativar, reativar, **gerar link de primeiro acesso / redefinição de senha** (mostra o link para copiar), exportar dados (JSON), anonimizar (substitui nome por "Usuário removido", apaga e-mail, foto, bio; mantém créditos como "ex-membro da equipe"). Inline de `TeacherProfile`.
- Criar usuário: e-mail institucional, nome, papel, cargo. A conta fica ativa e entra pelo Microsoft ou por link.
- `AccessLink`: lista de links gerados, usados e expirados.

### Taxonomia
- `KnowledgeArea`, `Discipline` (inline na área), `Topic` (com aprovação de sugeridos e edição de `keywords`), `ArticleType`.
- Ordenação por campo `order` (arrastar com `django-admin-sortable2` é Evolução).
- Tudo editável: o seed é só ponto de partida.

Seed inicial (`seed_taxonomy`), baseado na BNCC e no currículo da rede estadual de SP para o ensino médio:

| Área | Cor | Disciplinas |
|---|---|---|
| Linguagens e suas Tecnologias | coral | Língua Portuguesa, Leitura e Produção de Texto, Arte, Educação Física, Língua Inglesa |
| Artes | magenta | Artes Visuais, Música, Teatro, Dança |
| Matemática e suas Tecnologias | azul | Matemática, Educação Financeira |
| Tecnologia | grafite | Programação, Robótica, Cultura Digital |
| Ciências da Natureza e suas Tecnologias | verde | Biologia, Física, Química |
| Ciências Humanas e Sociais Aplicadas | âmbar | História, Geografia, Filosofia, Sociologia |
| Formação e Projetos | violeta | Projeto de Vida, Tecnologia e Inovação, Orientação de Estudos, Eletivas, Itinerários Formativos |
| Escola e Comunidade | petróleo | Grêmio Estudantil, Eventos e Cultura, Gestão e Coordenação, Sala de Leitura, Monitoria |

Tipos: Notícia, Reportagem, Artigo de opinião, Entrevista, Projeto, Produção de aluno, Divulgação científica, Evento, Curiosidade, Resenha.

Tópicos iniciais (30, com palavras-chave): Inteligência Artificial, Programação, Ciência de Dados, Robótica, Meio Ambiente, Mudanças Climáticas, Saúde, Alimentação, Astronomia, Energia, Literatura, Cinema, Música, Esportes, Olimpíadas do Conhecimento, ENEM e Vestibular, Profissões, Direitos Humanos, Política e Cidadania, Economia, História do Brasil, Cultura Afro-brasileira e Indígena, Educação Financeira, Empreendedorismo, Redes Sociais, Jogos, Fotografia, Teatro, Matemática no cotidiano, Divulgação científica.

### Conteúdo
- `Article`: apenas leitura de campos técnicos, filtros por estado; ações de arquivar e reindexar busca. Edição de texto é pelo editor do painel, não pelo admin.
- `MediaAsset`: lista com miniatura, tamanho, `has_people`, `consent_ok`, publicação; ação para apagar órfãos.

### Configurações
- `SiteSetting`: nome, tagline, crédito do rodapé, e-mail de contato, política editorial, política de nome de aluno, contagens, comentários ligados, clima ligado.
- `StaticPage`.
- `ErrorLog`: últimos erros 500 (não há e-mail para o admin).
- `Comment`: todos os comentários, com filtros e exclusão definitiva.

### Curadoria (Fase 4)
- `NewsSource`: cadastro, teste de feed (botão "Buscar agora"), `trust_level`, tópicos e disciplinas padrão, último erro.
- `NewsItem`: lista com fonte, data, classificações; ação ocultar.
- `StoryIdea`: leitura.

### IA (Fase 5)
- `AIJob`: consulta de execuções, custo e erros.
- Configuração de provedor e modelos via variáveis de ambiente, não pelo admin (evita expor chaves).

### Auditoria
- `AuditLog`: somente leitura, filtros por ação e ator (E34: também por data; o alvo aparece como `app.modelo #id`).
- `EditorialEvent`: somente leitura.

## Operação

Comandos de gerenciamento para o admin:

| Comando | Função | Fase |
|---|---|---|
| `seed_taxonomy` | Carrega áreas, disciplinas, tópicos e tipos iniciais | 1 |
| `create_admin` | Cria o primeiro superusuário a partir de variáveis de ambiente | 1 |
| `access_link <email>` | Gera link de primeiro acesso ou redefinição | 1 |
| `rebuild_search_index` | Recalcula `search_vector` | 3 |
| `cleanup` | Apaga leituras antigas e comentários rejeitados, e limpa dados técnicos dos comentários (worker, todo dia às 4h30) | 3 → 4 |
| `notify_pending_comments` | Avisa os editores de comentários de leitores pendentes há mais de 3 dias (worker, todo dia às 7h) | 3 → 4 |
| `notify_stale_reviews` | Avisa revisor e autores de revisões paradas há mais de 5 dias (worker, todo dia às 7h10) | 4 |
| `seed_news_sources` | Cadastra as fontes de notícias sugeridas em [21](21-curadoria-de-noticias.md); pode repetir | 4 |
| `fetch_news` | Coleta as fontes de notícias ativas agora (`--fonte ID`, `--vencidas`); o worker faz o mesmo a cada 30 minutos | 4 |
| `export_user_data <email>` | Exporta dados de um usuário | 2 |
| `anonymize_user <email>` | Anonimiza | 2 |

## Contas novas (Fase 4b)

`/painel/editorial/contas/` (`editorial:accounts`), aba "Contas novas" do editorial, para editor e admin: cadastros próprios aguardando aprovação, com nome, e-mail, data, apresentação e disciplinas do perfil. **Aprovar** libera escrever e publicar e avisa a pessoa no sino e por e-mail; **Recusar** apaga a conta (ela ainda não tem nada no jornal) e deixa o e-mail livre. Cada cadastro gera aviso no sino de editores e admin; o item "Editorial" do menu e a visão geral mostram quantos esperam. No Django Admin, a lista de usuários filtra por "aprovada" e tem a ação "Aprovar contas do cadastro próprio". Auditoria: `user_signed_up`, `user_approved`, `user_rejected`.

## Histórico

- 2026-09-12: versão inicial.
- 2026-09-12: links de acesso no lugar de convites; seed completo da escola; comentários; log de erros.
- 2026-09-14: E25 adiantou dois itens do editorial para a Fase 1, fora de `/painel/editorial/` (que continua na Fase 2), com itens próprios no menu do painel só para editor+:
  - Destaques em `/painel/destaques/`: ordenação por setas (arrastar fica para depois). A capa é exigida só de quem entra; um destaque antigo sem capa pode ser reordenado. Ao arquivar, a publicação sai dos destaques.
  - Páginas estáticas em `/painel/paginas/`, com o editor das publicações sem imagens (figuras são descartadas no servidor) e botão para pôr no ar ou tirar do ar. No admin, `StaticPage` edita só título, linha fina e publicação, com link para o editor.
- 2026-09-14: E33 implementou a visão geral e "Todas as publicações". Decisões de detalhe:
  - Menu: um item "Editorial" (editor+) no lugar de "Destaques" e "Páginas"; as quatro telas (visão geral, todas as publicações, destaques, páginas) compartilham abas. `/painel/destaques/` e `/painel/paginas/` mantêm os endereços.
  - Contadores: rascunhos, em revisão, alterações sugeridas, publicados nos últimos 30 dias, arquivados e comentários da revisão abertos (fora dos arquivados). "Rascunhos (com autor)" virou a lista "Rascunhos por autor", com link para a lista filtrada. Comentários públicos pendentes entram na Fase 3.
  - Alertas calculados na hora (somem quando a condição deixa de valer), em `apps/editorial/alerts.py`, onde novas fontes entram numa lista: alunos sem autorização e imagens de pessoas sem autorização em publicações no ar (a checklist impede; indica dado antigo); revisão parada (em revisão há mais de 5 dias sem nenhum evento: comentário, edição, troca de revisor); comentários da revisão sem resposta há mais de 3 dias em textos em revisão ou com alterações sugeridas, que substitui até a Fase 3 o alerta de comentários públicos pendentes. O início do painel mostra ao editor quantos alertas há.
  - Todas as publicações: filtros por título, estado, tipo, área, autor, revisor e período (última atualização em 7, 30, 90 ou 365 dias). O título leva à tela de revisão; cada linha tem Revisar, Editar e Ver no jornal. Ações em massa: arquivar (motivo sempre obrigatório, vai no aviso) e trocar o revisor (só textos em revisão; o novo revisor não herda o "pode publicar por mim"; avisa o novo revisor, o antigo e os autores).
- 2026-09-14: E34. "Anonimizar crédito de aluno em um clique" ficou só com o admin, como na matriz de docs/02 ("Configurações, auditoria, anonimização") e em docs/23: botão "Anonimizar" nos créditos de aluno do editor e em cada crédito do alerta "Alunos sem autorização" (sem mostrar o nome). Em Usuários, "Exportar dados" baixa o JSON de uma conta ou um ZIP com um JSON por conta; "Anonimizar" pede confirmação numa página própria; conta anonimizada não pode ser reativada. Comandos `export_user_data <email> [--zip --output arquivo]` e `anonymize_user <email> [--yes]`.
- 2026-09-14: E39. Comando `cleanup` criado (em `apps/core`); por enquanto apaga só os registros diários de leitura com mais de 90 dias. As outras limpezas entram com as etapas delas.
- 2026-09-15: E41. Visão geral ganha o contador "Comentários de leitores pendentes" (link para a fila) e o alerta "Comentários de leitores pendentes" (há mais de 3 dias, um item por publicação, com link para a fila filtrada). A fila do editor é a mesma `/painel/comentarios/` da equipe, que para editores já mostra todas as publicações; não há aba "Comentários" dentro do editorial. Comando `notify_pending_comments`.
- 2026-09-15: áreas "Artes" e "Tecnologia" no seed e no menu, a pedido do dono (a disciplina "Arte" de Linguagens e "Tecnologia e Inovação" de Projetos continuam onde estão). As cores magenta e grafite deixam de ser reservadas.
- 2026-09-17: E44. `cleanup` e `notify_pending_comments` passam a rodar sozinhos no worker; novo comando `notify_stale_reviews` para o aviso de revisão parada. Notificações lidas, rascunhos vazios e erros antigos continuam fora do `cleanup` (ainda não há regra definida para eles).
- 2026-09-17: E45. "Curadoria de notícias" no admin: `NewsSource` com botão e ação "Buscar agora" (coleta na hora e mostra o resultado), aviso e filtro para fontes com 5 falhas seguidas; `NewsItem` só leitura, com ações "Ocultar das sugestões" e "Mostrar de novo" (classificações entram na E47). Comandos `seed_news_sources` e `fetch_news`.
- 2026-09-28: C2: aba "Contas novas" no painel editorial.
