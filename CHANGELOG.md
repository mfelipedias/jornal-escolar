# Changelog

Todas as mudanças relevantes do Jornal Escolar ficam registradas aqui.

O formato segue o [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e o projeto usa [Versionamento Semântico](https://semver.org/lang/pt-BR/). Detalhes em [docs/30](docs/30-versionamento.md).

## [Não lançado]

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

### Alterado

- O revisor designado edita o texto enquanto a revisão está com ele, mas não altera créditos. O crédito de revisão só entra e sai pelo fluxo de revisão.
- No celular, "Pedir revisão" e "Arquivar" ficam na folha "Detalhes" do editor.
- O selo de estado usa "Alterações sugeridas" (antes "Alterações pedidas").
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
