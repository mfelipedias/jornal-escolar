# Changelog

Todas as mudanças relevantes do Jornal Escolar ficam registradas aqui.

O formato segue o [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e o projeto usa [Versionamento Semântico](https://semver.org/lang/pt-BR/). Detalhes em [docs/30](docs/30-versionamento.md).

## [Não lançado]

### Adicionado

- Base da busca (E35): extensões `unaccent` e `pg_trgm`, função `f_unaccent` e configuração `pt_unaccent` criadas por migração (também no banco de testes e na imagem postgres:17). Publicações ganham `search_vector` com índice GIN e pesos (título; linha fina e nomes de disciplinas, tópicos e créditos; corpo), atualizado pelos services ao criar, editar, mexer em metadados e créditos, publicar e anonimizar; renomear disciplina ou tópico também reindexa. Selector `search_published` (sem acento, por radical, aspas e `-palavra`, ranking com desempate pela data): "fisica" encontra "Física". Comando `reindex_search`, idempotente. Nome anonimizado sai do índice.
- Página de busca `/busca/` (E36): publicações com trecho do corpo e o termo destacado (texto escapado, só `<mark>`), filtros de área, disciplina e tipo sobre a busca e "Carregar mais"; pessoas da equipe com perfil público (nome, apresentação ou disciplina, tolerante a erro de digitação); áreas, disciplinas e tópicos. Sem resultado exato, mostra títulos parecidos por trigramas ("astronomai" encontra "Astronomia"). Sem nada, sugere áreas. Página com `noindex`; limite de 60 buscas por minuto por IP.
- Busca no cabeçalho (ícone que abre o campo) e na página 404; JSON-LD da home com `SearchAction`.
- Filtros completos nas listas e na busca (E37): "Quem escreveu" (perfis públicos com crédito visível em publicação no ar), período (últimos 30 dias, este semestre, este ano ou intervalo de datas) e ordem (na busca, "Mais relevantes" ou "Mais recentes"; "Mais lidas" chega com as leituras). Com JavaScript, mudar um filtro ou remover um chip troca só a lista e põe a URL no histórico (voltar desfaz o filtro); sem JavaScript tudo continua por GET e a mesma URL mostra o mesmo resultado. No celular o painel abre como folha inferior.
- Cache de 60 segundos por combinação de filtros (contagem e cards de cada página) em `/publicacoes/`, áreas, disciplinas, tipos e busca, invalidado ao publicar, editar ou arquivar.
- Reações (E38): "Interessante", "Aprendi algo", "Gostei" e "Parabéns" no fim da publicação, uma por pessoa (clicar de novo remove, outro tipo troca), sem mostrar quem reagiu e sem número quando zero. Botões com `aria-pressed`, toque de 44px e foco mantido depois da troca; com HTMX troca só a barra, sem JavaScript o formulário volta para a publicação. Visitantes reagem pelo cookie anônimo `jv` (código aleatório, 1 ano), descrito na página de Privacidade; quem entrou reage com a conta, e essas reações entram na exportação de dados. Limites de 30 reações por minuto por IP e 10 por pessoa (resposta 429). Reagir não invalida o cache da home e das listas. Linha "Reagir" da matriz de permissões testada (`can_react`, respeitando `reactions.require_login`).
- Contador de leituras (E39): a página da publicação envia uma leitura quando a pessoa fica o tempo de `reads.min_seconds` (padrão 15s) com a aba visível e rola 25% do texto. Conta no máximo uma por pessoa, por publicação, por dia (recarregar não soma); não conta o autor, visitantes sem o cookie nem robôs sem JavaScript; 60 por minuto por IP. Os registros diários não guardam quem leu (hash com chave secreta e dia). "143 leituras" aparece a partir de 10, se nenhum autor desligou a opção no perfil.
- Ordem "Mais lidas" nas listas e na busca.
- Painel: "Leituras em 30 dias" nos números, leituras e reações em "Suas últimas publicadas" e coluna "Leituras" em "Minhas publicações".
- Comando `cleanup`: apaga registros diários de leitura com mais de 90 dias.
- Comentários públicos (E40): no fim da publicação, leitores comentam sem conta, só com nome e texto. Todo comentário nasce pendente e fica invisível até a aprovação (fila de moderação na E41). Links e e-mails são removidos do texto (marca `had_links`), honeypot contra robôs, 10 envios por hora por IP e 3 pendentes por pessoa por publicação (429). Com HTMX troca só o formulário; sem JavaScript volta para a publicação. Aprovados aparecem do mais recente para o mais antigo, com a resposta da equipe ("Resposta de Carla Souza (autoria do texto)"), que autores, coautores, editores e admin escrevem na própria página. Comentários fechados na publicação mantêm os aprovados; `comments.enabled` desligado esconde o bloco. Linhas "Comentar" e "Responder comentários como autor" da matriz de permissões testadas.
- Painel: número "Comentários aprovados" no início. Admin: consulta e exclusão de comentários.
- Moderação de comentários (E41): item "Comentários" no menu do painel com contador e fila em `/painel/comentarios/` (abas Pendentes, Aprovados e Rejeitados, filtro por publicação). Editores veem os comentários de todas as publicações; autores e coautores, só das suas. Aprovar, rejeitar, editar o nome e responder e aprovar sem recarregar a página; marcar vários e aprovar ou rejeitar em lote; marcas "tinha links" e "mesmo IP enviou N". Toda moderação fica na auditoria. Linha "Moderar comentários públicos" da matriz de permissões testada.
- Avisos de comentários: autores e coautores recebem um aviso por publicação com o total de pendentes (atualizado, sem empilhar), que sai do sino quando tudo é moderado. Comando `notify_pending_comments` avisa os editores de pendentes há mais de 3 dias.
- Painel: "N comentários aguardam sua aprovação" nas pendências do início, coluna "Comentários pendentes" e "Fechar/Abrir comentários" em "Minhas publicações". Editorial: contador e alerta de comentários de leitores pendentes.
- `cleanup` também apaga comentários rejeitados há mais de 30 dias e o hash do IP e o código anônimo dos comentários com mais de 30 dias. Exportação de dados inclui as respostas a comentários; anonimizar tira o nome delas.
- Clima "Hoje na escola" (E42): bloco discreto na página inicial com a temperatura, a condição (ícone em linha e rótulo em português), mínima, máxima e chance de chuva do dia, do Open-Meteo, para Osasco, SP (`WEATHER_LAT` e `WEATHER_LON` no `.env`; `WEATHER_API_BASE` para auto-hospedar). A consulta é feita pelo servidor, sem chave e sem dados do visitante, com cache de 30 minutos e timeout de 3 segundos; em falha, o último valor bom vale por até 6 horas e, sem nada, o bloco some. No desktop fica na coluna lateral, acima da Agenda; no celular, em uma linha abaixo do destaque. Desliga em "Mostrar o clima na página inicial" no admin. Os testes nunca chamam a API.

### Redesign visual (Fase 3b)

- R1, fundações: o site ganha a direção visual "Pátio" (docs/09), pedida pelo dono do projeto para o jornal ficar mais atraente aos alunos. Títulos e interface passam para a fonte Bricolage Grotesque (a Inter saiu); o corpo de leitura continua em Newsreader. Cores novas: papel mais claro, acento framboesa, amarelo "marca-texto" e uma versão viva de cada cor de área para blocos, todas com contraste medido. Marca nova: um avião de papel dobrado de uma página de jornal, no cabeçalho, no favicon (SVG e ICO), nos ícones da tela inicial do celular (`manifest.json`) e na imagem padrão de compartilhamento; o wordmark tem um traço de marca-texto atrás de "Escolar". A página deixa de aparecer "quebrada" enquanto carrega: o CSS vem por `<link>` antes do JavaScript (também no modo de desenvolvimento), as duas fontes principais são pré-carregadas e as fontes substitutas têm métricas ajustadas para o texto não pular.
- R2, cabeçalho, rodapé e peças básicas: o cabeçalho fica fixo no topo, translúcido, com as seções em chips (a seção atual ganha a cor da área) e a busca em uma pílula; o rodapé vira uma faixa escura com a marca, a frase do jornal e os links. Botões, filtros, etiquetas, campos de formulário e paginação viram pílulas arredondadas que reagem ao toque; a reação escolhida fica rosa; os avisos (toasts) entram deslizando com uma borda colorida; os estados vazios ganham um "adesivo" com o avião de papel; o clima vira um cartão azul-claro. A vitrine interna `/dev/components/` mostra todas as cores e fontes.
- R3, página inicial e páginas de navegação: o destaque da página inicial fica numa faixa colorida com a cor da área da matéria principal, e cada área ganha a sua faixa de ponta a ponta com cartões brancos. Os cartões de publicação levantam e dão um zoom na imagem ao passar o mouse; os que não têm capa mostram um bloco colorido com o avião de papel. Nas listas, a cor da área vira uma barra ao lado do título. Títulos de seção ganham o traço amarelo de marca-texto. Publicações, áreas, disciplinas, tipos, agenda, busca, "Quem escreve" e perfis ganham cabeçalho colorido e título grande. Corrigido: na agenda, eventos que ainda vão acontecer apareciam com o selo "Aconteceu".
- R4, página da publicação, páginas institucionais, erros e entrada: a publicação abre com uma faixa na cor da área, título grande e as etiquetas em pílulas; a capa ganha cantos arredondados. No texto, os intertítulos usam a fonte dos títulos, as citações ganham aspas grandes cor-de-rosa e os links um sublinhado mais visível (o texto continua com o contraste máximo recomendado). Reações, número de leituras e botões de compartilhar ficam juntos num cartão branco; "Quem fez" e os comentários viram cartões, e a resposta da equipe aparece destacada em rosa. "Sobre", "Privacidade" e as outras páginas institucionais ganham cabeçalho colorido. As páginas de erro (não encontrada, sem acesso, publicação retirada e erro no servidor) mostram o avião de papel e um caminho de volta; a de erro no servidor funciona mesmo quando o banco ou os arquivos do site falham. As telas de entrada (login, criar senha, sair) ficam num cartão branco sobre um fundo em degradê rosa e amarelo.

- Áreas "Artes" (Artes Visuais, Música, Teatro, Dança) e "Tecnologia" (Programação, Robótica, Cultura Digital) no seed da taxonomia e no menu, a pedido do dono do projeto. Em sites já instalados, `manage.py seed_taxonomy` cria só o que falta.

### Alterado

- No celular, com sessão aberta, "Escrever" e "Admin" saem do cabeçalho (ficam no painel) para a linha caber em 390px.
- Texto padrão da página de Privacidade descreve o cookie `jv` e os comentários; `seed_site` atualiza os textos da E28 e da E38 se ninguém os editou.
- Limite de comentários por IP subiu de 10 para 60 por hora, para não bloquear uma turma inteira atrás do IP da escola; entrou o limite de 10 comentários por pessoa por hora.
- Produção: cache do Django numa tabela do PostgreSQL, compartilhada pelos workers do Gunicorn, para os limites por minuto e a limpeza de cache ao publicar valerem em todos eles (`createcachetable` no entrypoint).

## [1.1.0] - 2026-09-14

### Adicionado

- Revisão por colega (E29): estados "Em revisão" e "Alterações sugeridas". No editor, o autor pede a leitura de um colega (com nota e "pode publicar por mim"), cancela o pedido ou reenvia depois das sugestões; o revisor designado, editores e admin sugerem alterações (com nota), aprovam e devolvem, aprovam e publicam (quando permitido) ou recusam a revisão. O painel lateral mostra com quem está a revisão, a nota, as alterações sugeridas e o selo "Revisado por".
- Notificações no painel para pedido de revisão, alterações sugeridas, aprovação, pedido cancelado, revisão recusada e edição do autor durante a revisão.
- Histórico editorial (`EditorialEvent`): toda mudança de estado registra quem, quando, de qual estado para qual e a nota (inclusive o motivo de arquivar); também revisor designado ou removido, aprovação, créditos alterados (sem nome de aluno), edição depois de publicar e edição por terceiro. "Atualizar créditos anteriores" no perfil passa a gravar evento. No admin, só leitura.
- "Minhas publicações" mostra os chips "Em revisão" e "Alterações sugeridas".
- `seed_demo` cria uma publicação em revisão e uma com alterações sugeridas.
- Matriz de permissões completa (E30): `permissions.py` ganha entrar, ver e editar perfil, acesso ao Django Admin, duplicar e comentário interno da revisão. Teste parametrizado célula a célula a partir de uma cópia da tabela de `docs/02`, que falha se a tabela do documento mudar sem o teste; linhas de recursos futuros ficam marcadas como fora do escopo.
- Tag de template `{% can "acao" objeto as variavel %}` (`{% load permissions %}`), usada no cabeçalho e no link "Editar" da página da publicação.
- Tela de revisão (E31) em `/painel/publicacoes/<id>/revisar/`: o texto como ficará publicado, nota do pedido, autores, "Editar texto", "Sugerir alterações" (comentário obrigatório, bloqueado na tela e no serviço), "Aprovar" com "Aprovar e publicar" quando permitido, "Recusar revisão", "Arquivar" para editor com motivo, conferência e histórico legível dos eventos. Editores veem a lista de versões. Autores acompanham pela mesma tela, sem decisões.
- "Revisões" no menu do painel, com contador: abas "Pedidas a mim", "Que eu pedi" e, para editores, "Todas em revisão".
- Comentários editoriais (E32) na tela de revisão: selecionar um trecho do texto mostra "Comentar"; também há comentário geral. Trechos comentados ficam marcados no texto (clicar leva ao comentário e vice-versa), respostas em um nível, "Resolver" e "Reabrir" (resolvidos ficam recolhidos). A âncora guarda o trecho com o contexto e é reencontrada a cada leitura: editar outro parágrafo não a perde; se o trecho mudar, o comentário aparece como "trecho alterado". No celular, botão flutuante "Comentários" com contador. Comentários entram no histórico e geram avisos (resposta avisa quem está na conversa; autor comentando avisa o revisor). O painel lateral do editor mostra os comentários abertos com link para a tela.
- Painel editorial (E33) em `/painel/editorial/`, só para editor e admin: contadores por estado (com publicados nos últimos 30 dias e comentários da revisão abertos), rascunhos por autor e alertas que somem quando a condição deixa de valer: revisão parada há mais de 5 dias, comentários da revisão sem resposta há mais de 3 dias, publicações no ar com aluno ou imagem de pessoas sem autorização. O início do painel mostra ao editor quantos alertas há.
- "Todas as publicações" (`/painel/editorial/publicacoes/`): filtros por título, estado, tipo, área, autor, revisor e período; o título abre a tela de revisão; ações em massa "Arquivar" (com motivo) e "Trocar o revisor" de textos em revisão, com evento no histórico e avisos ao novo revisor, ao antigo e aos autores.
- Auditoria (E34): `AuditLog` registra entradas no sistema, criação de conta, troca de papel, desativação e reativação, anonimização, exportação de dados, pedido de exclusão, links de acesso, configurações alteradas, imagens apagadas no admin, créditos de aluno anonimizados, ações em massa do painel editorial, mudanças nos destaques e páginas institucionais postas no ar ou tiradas do ar. Sem nomes nos detalhes; IP guardado como hash com sal mensal. Leitura só no Django Admin.
- "Conta" completa: "Baixar meus dados" em JSON ou ZIP (com a foto de perfil) e "Pedir exclusão da conta", que avisa os administradores no painel.
- Anonimizar conta da equipe (ação do admin com confirmação e comando `anonymize_user`): créditos viram "Ex-membro da equipe", perfil público sai do ar, foto apagada, login desativado de vez; histórico editorial e auditoria ficam, com o nome trocado. Exportar dados pelo admin (uma conta em JSON ou várias em ZIP) e pelo comando `export_user_data`.
- Anonimizar crédito de aluno (só admin), no editor e no alerta "Alunos sem autorização": o nome vira "Aluno da 2ª série", a turma sai e o crédito deixa de exigir autorização.

### Alterado

- O menu do painel troca "Destaques" e "Páginas" por "Editorial"; as duas telas viram abas do editorial e mantêm os endereços.
- O revisor designado edita o texto enquanto a revisão está com ele, mas não altera créditos. O crédito de revisão só entra e sai pelo fluxo de revisão.
- No celular, "Pedir revisão" e "Arquivar" ficam na folha "Detalhes" do editor.
- O selo de estado usa "Alterações sugeridas" (antes "Alterações pedidas").
- "Sugerir alterações" passa a exigir ao menos um comentário aberto; a nota opcional vira um comentário geral e o aviso aos autores diz quantos comentários estão abertos.
- O revisor designado não duplica mais o texto que revisa: duplicar fica com autores e editores.
- Cabeçalho, página de perfil, login Microsoft, menu do painel e telas de dev consultam só `permissions.py`, sem testar `role` ou `is_staff` direto.
- No editor, "Revisar" abre a tela de revisão. Avisos de pedido de revisão, edição durante a revisão e alterações sugeridas abrem a tela de revisão; pedido cancelado abre a lista de revisões.

## [1.0.0] - 2026-09-14

### Adicionado

- Seed de demonstração (E28): `manage.py seed_demo` cria 8 pessoas fictícias da equipe (sem senha), 19 publicações de 10 tipos e 6 áreas (com rascunhos, uma arquivada, créditos de alunos com autorização), capas e fotos de perfil desenhadas localmente, eventos na agenda e os 3 destaques da home. Idempotente, recusa rodar sem `DEBUG=True` e não troca destaques escolhidos de verdade. `seed_demo --apagar` remove tudo o que criou, inclusive os arquivos.
- Cabeçalhos de segurança em todas as páginas: `Content-Security-Policy` (scripts e estilos só do próprio site, sem `unsafe-inline` para scripts, `frame-ancestors 'none'`) e `Permissions-Policy`. No desenvolvimento com o servidor do Vite a CSP fica desligada; com `VITE_DEV_MODE=False` ela liga como em produção.
- Checklist de segurança antes de ir ao ar marcada em `docs/23`, com testes em `backend/tests/test_security_checklist.py` (cabeçalhos, CSRF, telas de cadastro fechadas, HTML limpo, configurações e `check --deploy` de produção).
- Texto completo da página Privacidade (dados de leitores, alunos, equipe e comentários, onde ficam os dados e direitos pela LGPD). Continua fora do ar até a aprovação da direção; `seed_site` troca o rascunho antigo se ele nunca foi editado.
- Produção (E27): imagem Docker própria em `infra/Dockerfile` (build do Vite, dependências com uv, usuário sem privilégios, `collectstatic`, healthcheck) para x86 e ARM; Compose de produção em `infra/docker-compose.yml` com banco, site (Gunicorn), Caddy entregando `/static/` e `/media/` com cache, `cloudflared` no perfil `tunel` e container de backup. Modelo `infra/env/.env.producao.example`.
- Backup diário às 3h (`infra/backup/`): `pg_dump` conferido com `pg_restore --list`, fotos espelhadas com as apagadas guardadas por 6 meses, tudo criptografado pelo rclone e enviado ao Cloudflare R2 (ou a uma pasta local); retenção de 7 dias, 4 semanas e 6 meses. Restauração com `make restore FILE=mais-recente`, inclusive em servidor novo.
- Atalhos `make build`, `deploy`, `prod-check`, `prod-logs`, `prod-down`, `prod-superuser`, `backup`, `backups` e `restore`.
- Guia `docs/34-guia-deploy.md`: servidor, túnel, primeiro administrador, backup, teste de restauração, UptimeRobot e problemas comuns, em linguagem simples.
- `manage.py check --deploy` avisa quando `SITE_URL` aponta para localhost, não usa https ou tem caminho.
- CI monta as imagens do site e do backup para amd64 e arm64 (sem publicar).
- SEO do site (E26): título, descrição, endereço canônico, Open Graph e Twitter Card nas páginas públicas; JSON-LD `NewsArticle`/`Article` nas publicações (autores da equipe com link do perfil, alunos só com o nome), `Person` no perfil público e `WebSite` na home, sempre com o nome do jornal como quem publica. Imagem padrão de compartilhamento e logo com o glifo.
- `/sitemap.xml` só com páginas públicas e `/robots.txt` fechando painel, login, admin e pré-visualizações; telas de login com `noindex`.
- Configuração "Descrição para buscadores" (`site.description`) para a página inicial.
- Compartilhar: "Copiar link" funciona também sem a Clipboard API (mostra o link selecionado) e o link do WhatsApp sai com o endereço oficial do jornal.
- Destaques da home `/painel/destaques/` (E25, só editor e admin): lista dos até 3 destaques com setas para subir, descer e remover, busca entre as publicações no ar com capa para adicionar e prévia do bloco como a home mostra. Novos destaques exigem capa; a mudança aparece na home na hora.
- Páginas institucionais no painel `/painel/paginas/` (E25, só editor e admin): Sobre, Como participar e Privacidade escritas com o mesmo editor das publicações (sem imagens), com salvamento automático e botões para pôr no ar ou tirar do ar. O admin passa a apontar para esse editor.
- Painel da equipe (E24): layout com menu lateral (aberto no computador, só ícones no tablet, gaveta no celular), sino de notificações no cabeçalho e versão no rodapé do menu. Mostra só os itens da Fase 1; "Administração" só para admin. Perfil, Conta, Notificações e Nova publicação passaram a usar esse layout, e o cabeçalho do jornal ganhou o link "Painel".
- Início do painel `/painel/`: pendências (notificações não lidas e "Complete seu perfil"), continuar escrevendo (3 rascunhos), suas últimas publicadas e números de publicadas e rascunhos.
- "Minhas publicações" `/painel/publicacoes/`: tabela no computador e lista no celular com título, tipo, estado, meu papel e última atualização; filtro por estado (Todos, Rascunhos, Publicados, Arquivados); ações Abrir, Ver no jornal, Duplicar como rascunho (com cópia das imagens), Arquivar e Restaurar.
- Assistente de primeiro acesso em três passos puláveis (E23): quem é você (foto, nome de exibição, apresentação), o que você ensina ou faz (disciplinas por área ou, para outros cargos, áreas) e o que interessa a você (tópicos, com os ligados às disciplinas primeiro, e "Sobre mim"). Aparece depois do link de primeiro acesso e no primeiro login.
- Tela "Meu perfil" `/painel/perfil/`: apresentação, foto com recorte quadrado, atuação, interesses com busca e sugestão de tópico (vai para aprovação do admin), formação, links, preferências, troca de endereço com aviso e opção de atualizar o nome nos créditos anteriores. Aviso "Complete seu perfil" enquanto faltarem foto, disciplinas/áreas ou bio.
- Tela "Conta" `/painel/conta/`: forma de entrar, alteração de senha e "Sair de todas as outras sessões".
- "Editar perfil" no perfil público também para o próprio dono; nome no cabeçalho leva a "Meu perfil".
- Perfil público de cada membro da equipe em `/professores/<endereço>/` (E22): foto ou iniciais na cor da área, apresentação com cargo, áreas e disciplinas, sobre, formação, interesses, links e publicações em abas (Todas, Como autor(a), Colaborações) com "Carregar mais". Perfil oculto só aparece para o próprio dono; conta desativada mantém só o crédito histórico.
- Página "Quem escreve" `/professores/` com toda a equipe de perfil público, filtros por área e cargo, ordem por publicação mais recente ou por nome, e "Quem escreve" no cabeçalho.
- Nomes da equipe na home, nas páginas de área e disciplina e em "Quem fez" levam ao perfil.
- Página pública da publicação `/publicacoes/<endereço>/` (E18): etiquetas de área e tipo, assinatura, data, tempo de leitura, disciplinas, bloco de evento, capa com `srcset`, corpo, fontes, compartilhar (copiar link, WhatsApp, compartilhamento do celular), "Quem fez" e "Leia também". Acessibilidade 100 no Lighthouse.
- Pré-visualização para autores e editores (rascunhos em `/publicacoes/previa/<id>/`), com faixa de aviso e sem indexação; botões "Pré-visualizar" e "Ver no site" no editor; link "Editar" na página.
- Publicação arquivada responde 410; página 404 própria.
- Modelo de termo de autorização de uso de nome e imagem de alunos, com revogação e processo para a secretaria, em `docs/33` (E06b; falta aprovação da direção).
- Componentes do design system (E19): card de publicação em quatro variantes (destaque, padrão, compacto e mini), assinatura com avatares, etiquetas de área, disciplina, tipo e tópico, estado editorial, estado vazio, paginação ("Carregar mais" e numerada) e toasts.
- Lista de publicações `/publicacoes/` com filtros por área, disciplina e tipo que funcionam sem JavaScript, filtros aplicados em etiquetas removíveis e "Carregar mais" (E21).
- Páginas de área, disciplina e tipo, com o filtro já aplicado; a de área mostra as disciplinas, a publicação mais recente com capa em destaque e quem escreve sobre a área.
- Agenda `/agenda/` com próximos eventos e os que já aconteceram.
- Linha de áreas, Agenda e Sobre no cabeçalho; nome curto da área editável no admin.
- Links da home para a agenda, para todas as publicações e para cada área; etiquetas e disciplinas da publicação levam às suas páginas.
- Página inicial completa (E20): destaques (marcados no admin ou os mais recentes), últimas publicações com "Carregar mais", agenda de eventos (ou o último que aconteceu), quem escreve e faixas por área; estado vazio quando não há publicações. Blocos em cache por 5 minutos, renovados ao publicar ou arquivar.
- Vitrine dos componentes em `/dev/components/`, aberta em desenvolvimento e para administradores.
- Mensagens do sistema aparecem como toast no canto da tela, inclusive em ações sem recarregar a página; erros e avisos ficam até serem fechados.

### Alterado

- O TipTap e o HTMX não injetam mais `<style>` na página (bloqueado pela CSP): os estilos-base do editor foram para `app.css`.
- `check --deploy` sem avisos em produção: os avisos de HSTS para subdomínios e "preload" foram silenciados de propósito, porque valeriam para o domínio inteiro.
- `Referrer-Policy: strict-origin-when-cross-origin` em todos os ambientes.
- `/healthz/` aceita também HEAD, usado por monitores externos.
- Em produção, erros e avisos do Django vão para o log do container.
- `/static/` em produção é entregue pelo Caddy, não pelo WhiteNoise; backup criptografado pelo rclone em vez do `age` (docs/24, Histórico).
- Cor `ink-3` escurecida (`#6B6875`) para atingir contraste AA em textos pequenos.
- Cor de área âmbar escurecida (`#8F5A00`) para atingir contraste AA nas etiquetas.
- "Leia também" e o cabeçalho da publicação usam os novos componentes.

### Corrigido

- Celular: o início do painel e a barra do editor de publicação não passam mais da largura da tela.

## [0.3.0] - 2026-09-12

### Adicionado

- Projeto Django 5.2 com configurações por ambiente (`base`, `dev`, `test`, `prod`) lidas de variáveis de ambiente (E02).
- `infra/env/.env.example` e Compose de desenvolvimento com PostgreSQL 17 (porta 5433) e Django.
- App `core` com `/healthz/` (banco, migrações e versão) e cabeçalho `X-App-Version` em todas as respostas.
- pytest e pytest-django, com testes do `/healthz/`.
- Comandos `make dev`, `dev-native`, `db`, `down`, `logs`, `test`, `migrate`, `makemigrations`, `shell`, `superuser` e `secret-key`.
- Usuário customizado `accounts.User` com login por e-mail (sempre em minúsculas), papel (`role`), cargo (`staff_kind`) e senhas em Argon2 (E03).
- Cadastro de usuários no Django Admin; só o papel `admin` acessa o Django Admin.
- `make db-reset` para recriar o banco de desenvolvimento.
- Frontend com Vite, Tailwind 4, HTMX e Alpine via `django-vite`; fontes Newsreader e Inter auto-hospedadas (E04).
- Tokens do design system, glifo e wordmark "Jornal Escolar", favicon.
- `base.html`, `layouts/public.html`, masthead, rodapé com crédito e versão, página inicial provisória.
- Comandos `make assets-install`, `assets-dev` e `assets`.
- factory-boy com `UserFactory` e fixtures compartilhadas (`staff_user`, `editor_user`, `admin_user`, `admin_client`) (E05).
- GitHub Actions: lint, checagem de migrações, testes com PostgreSQL e build do frontend.
- `README.md` com preparação do computador e comandos; `CLAUDE.md` com instruções para assistentes de código (E06).
- Serviço `vite` no Compose de desenvolvimento; `docker compose up` na raiz sobe banco, Django e Vite, sem `.env` nem outras ferramentas instaladas.
- Taxonomia: áreas do conhecimento (com cor do design system), disciplinas, tópicos (palavras-chave e disciplinas sugeridas) e tipos de publicação, editáveis no Django Admin (E07).
- Comando `seed_taxonomy` com 6 áreas, 24 disciplinas, 30 tópicos e 10 tipos; só cria o que falta.
- Configurações do site no banco (`SiteSetting`) com cache e formulário por tipo no Django Admin; nome, frase, crédito, e-mail e data do cabeçalho passam a ser editáveis (E08).
- Páginas institucionais `/sobre/`, `/colaborar/` e `/privacidade/` (`StaticPage`), com links no rodapé só para as publicadas.
- Comando `seed_site`: cria configurações e textos iniciais; Privacidade nasce despublicada até revisão da direção.
- Login em `/entrar/` com `django-allauth`: senha de reserva e botão "Entrar com a conta da escola" (Microsoft), que aparece quando `MS_CLIENT_ID`/`MS_CLIENT_SECRET` estão configurados (E09).
- Login Microsoft só para domínios permitidos e contas cadastradas e ativas, identificando a pessoa pelo `userPrincipalName`.
- Limite de tentativas de login (5 por e-mail e 30 por IP a cada 15 minutos); sessão de 14 dias sem uso; senha mínima de 10 caracteres.
- Layout `auth.html`, telas de sair, conta desativada, cadastro fechado e erros de login; cabeçalho com "Entrar" ou nome, "Admin" e "Sair".
- Configuração "Login com a conta Microsoft da escola ligado" no admin.
- Links de acesso (`/acesso/<código>/`): uso único, 7 dias, criar ou redefinir senha e entrar; gerar um novo cancela os anteriores (E10).
- No admin de Usuários: ação "Gerar link de acesso" com o endereço para copiar, "Desativar" e "Reativar" contas, coluna "entra com" e perfil editável junto do usuário; lista somente leitura de links.
- Comando `access_link <email>`.
- Perfil (`TeacherProfile`) criado automaticamente para cada conta, com endereço único derivado do nome.
- Upload de imagens (`MediaAsset`, `POST /x/media/`): só JPEG, PNG e WebP pelo conteúdo real, até 10 MB e 6000 px, sem EXIF/GPS, rotação da câmera aplicada, variantes WebP de 480, 960 e 1600 px, cota de 1 GB e 60 envios por hora por pessoa (E11).
- `GET/PATCH /x/media/<id>/` para texto alternativo, crédito, licença, pessoas na foto e autorização; admin de imagens com miniatura; foto de perfil (`avatar`) no usuário.
- Publicações (`Article`), créditos (`ArticleContributor`, inclusive alunos sem conta com turma e autorização) e versões (`ArticleRevision`), com estados rascunho, publicado e arquivado (E12).
- Regras em `publications/services.py`: criar, editar, publicar, arquivar e restaurar; checklist de publicação; endereço definitivo na primeira publicação; versão a cada publicação e edição de texto publicado.
- `apps/editorial/permissions.py`: única fonte das permissões (equipe publica só o próprio texto; editor e admin, qualquer um; nota obrigatória para arquivar texto alheio); política de nome de aluno "Rafael S.".
- Admin de publicações com créditos, versões e ação de arquivar.
- Renderizador `publications/rendering.py`: documento do editor → HTML e texto com lista fechada de nós e marcas, links só `http(s)`/`mailto`/internos, figuras com `srcset` e tamanho, segunda limpeza com `nh3`, tempo de leitura (E13).
- Salvar o corpo gera HTML, texto e tempo de leitura e liga as imagens à publicação; só entram imagens enviadas pela própria pessoa ou já da publicação (editores usam qualquer uma).
- Editor de publicações com TipTap 3 (`/painel/publicacoes/nova/` e `/painel/publicacoes/<id>/editar/`): título, linha fina, barra de ferramentas (parágrafo, H2, H3, negrito, itálico, link, listas, citação, separador, desfazer), contagem de palavras (E14).
- Salvamento automático (`PUT /x/articles/<id>/body/`) 2 s após parar de digitar ou a cada 30 s, com indicador, novas tentativas, cópia local se a conexão cair e aviso de conflito quando outra pessoa salvou.
- Estilos do corpo das publicações (`.article-body`) compartilhados entre editor e página pública; botão "Escrever" no cabeçalho; página 403.
- Painel lateral do editor (E15): tipo (com data e local para eventos), disciplinas por área, tópicos, fontes, comentários abertos; créditos de colegas (busca), alunos (turma e autorização) e outros; checklist ao vivo; botões Publicar, Arquivar (com motivo) e Restaurar. No celular, o painel abre em "Detalhes".
- Aviso de conflito só quando outra pessoa salvou (`last_edited_by`); edições seguidas de texto publicado agrupadas numa única versão por 15 minutos.
- Imagens no editor (E16): botão, arrastar e soltar ou colar; progresso do envio; diálogo com texto alternativo (ou decorativa), legenda, crédito, tamanho, pessoas na imagem e autorização; duplo clique reabre o diálogo.
- Capa da publicação no painel lateral: enviar nova ou escolher entre as imagens do texto, com legenda; a lista se atualiza após cada salvamento.
- O documento salvo guarda o endereço de cada imagem calculado pelo servidor, para o editor exibi-la ao reabrir.
- Notificações no painel (E17): sino com contador e lista das últimas 20, "marcar todas como lidas", página `/painel/notificacoes/`. Avisos quando alguém publica um texto seu, ou quando editor/admin edita ou arquiva (com motivo) um texto seu; salvamentos repetidos atualizam o mesmo aviso não lido.
- `make release VERSION=x.y.z` (`scripts/release.py`): atualiza `VERSION` e o changelog, faz commit e tag.

### Alterado

- O `/admin/login/` redireciona para `/entrar/`; telas do allauth sem uso (cadastro, recuperação de senha por e-mail, e-mails) respondem 404.
- Variável de template da identidade do site renomeada de `site` para `jornal`, que o allauth sobrescrevia.

- Compose de desenvolvimento movido de `infra/docker-compose.dev.yml` para `compose.yaml` na raiz.

### Corrigido

- `make format` formata antes de aplicar correções do ruff e não para quando o djlint altera templates.

## [0.0.1] - 2026-09-12

### Adicionado

- Documentação de planejamento em `docs/`.
- Estrutura do repositório (E01): `backend/`, `frontend/`, `infra/`.
- Ferramentas de qualidade: `uv`, ruff, djlint, pre-commit e `.editorconfig`.
- `Makefile` com `install`, `lint`, `format` e `hooks`.
- Arquivo `VERSION` e este changelog.
