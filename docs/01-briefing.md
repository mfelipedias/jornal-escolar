# 01 — Briefing, objetivo e ideia principal

## Nome

**Jornal Escolar** — jornal digital da comunidade escolar. Endereço: `jornal.projetosrosa.com.br`.

O nome oficial da escola **não aparece no site**, por decisão do dono do projeto. "Rosa" no nome do jornal é uma referência interna. O rodapé traz apenas o crédito de desenvolvimento e o e-mail de contato.

## Uma frase

Uma plataforma editorial da comunidade escolar, onde professores e demais membros da equipe produzem e publicam conteúdo ligado às disciplinas, creditando os alunos que participam, com revisão por colegas opcional, comentários moderados e uma curadoria de pautas que ajuda a começar a escrever.

## O que o projeto é

- Um **jornal digital** público, lido por alunos, professores, famílias e comunidade.
- Uma **redação pequena**: quem escreve é a equipe da escola (professores, monitores, coordenação); alunos participam com textos entregues ao professor, que publica e credita. Cada autor responde pelo que publica; revisão por colega é opcional; editores podem intervir.
- Um **mapa do conhecimento da escola**: toda publicação está ligada a disciplinas e áreas, e cada professor tem um perfil que mostra o que produz.
- Uma **curadoria de pautas**: o sistema sugere notícias externas ligadas aos interesses dos professores para virarem matérias originais.

## O que o projeto não é

- Não é uma rede social. Não há feed infinito, seguidores nem mensagens diretas. Comentários existem, mas só aparecem depois que o autor da publicação aprova.
- Não é um agregador de notícias. Conteúdo externo nunca é reproduzido; só título, resumo curto, fonte e link.
- Não é um sistema de gestão escolar. Não guarda notas, frequência, turmas completas ou dados administrativos.
- Não é um portal de notícias tradicional. A home privilegia leitura e descoberta por área do conhecimento, não volume.

## Público

| Público | Relação com o site | Precisa de conta? |
|---|---|---|
| Alunos | Leem, reagem, comentam; entregam textos a professores e são creditados | Não |
| Famílias e comunidade | Leem, reagem, comentam | Não |
| Equipe (professores, monitores, coordenação, direção, sala de leitura) | Escrevem, publicam, creditam alunos, moderam comentários, recebem sugestões de pauta | Sim, criada pelo admin |
| Editores | Membros da equipe com poder de moderação sobre tudo | Sim |
| Administrador | Configura o sistema | Sim |

Decisão importante: **só a equipe tem conta; alunos e leitores nunca**. Isso reduz drasticamente o volume de dados pessoais de menores, elimina cadastro em massa e mantém o site aberto para a comunidade. Ver [02-personas-papeis-permissoes.md](02-personas-papeis-permissoes.md).

## Objetivos mensuráveis do primeiro semestre de uso

1. Pelo menos 5 membros da equipe com perfil preenchido e ao menos uma publicação cada.
2. Pelo menos 2 publicações por semana no total.
3. Pelo menos 5 publicações com alunos creditados.
4. Comentários moderados em menos de 3 dias na mediana.

Esses números orientam o que é MVP: tudo que não contribui para eles é adiado.

## Princípios de produto

1. **Simples de manter por uma pessoa.** Uma pessoa desenvolve e mantém. Cada dependência precisa se justificar.
2. **Humano decide, sistema sugere.** Automação classifica e recomenda; publicar, creditar e aprovar comentários são atos humanos. O professor é o responsável pelo que publica.
3. **Menos dados, menos risco.** Coletar o mínimo, especialmente de menores. Leitores anônimos; alunos sem conta.
4. **Editorial antes de social.** Reações discretas, comentários só após aprovação, sem gamificação.
5. **Configurável, não hard-coded.** Áreas, disciplinas, tipos de publicação e fontes de notícia são dados, não código.
6. **Incremental e verificável.** Cada etapa entrega algo usável e testável.

## Visão crítica da ideia original

O prompt original é sólido e já antecipa muitos problemas. Pontos em que o planejamento diverge ou aperta o foco, já incorporando as respostas do dono do projeto ([27](27-decisoes-pendentes-e-perguntas.md)):

| Ideia original | Avaliação | Decisão |
|---|---|---|
| Sete papéis (visitante, aluno, aluno colaborador, professor, revisor, editor, admin) | Excesso. Alunos não terão conta. "Revisor" é atribuição por publicação. Funcionários não docentes também escrevem. | Três papéis com conta: equipe, editor, administrador; mais o visitante. Cargo é só exibição. |
| Fluxo com aprovação obrigatória | A escola quer autonomia do professor; ele é o humano que aprova o texto do aluno. | Autopublicação pela equipe; revisão por colega opcional; editores moderam depois. Cinco estados. |
| Frontend em React/Next.js separado do backend | Duplica a manutenção para um desenvolvedor sem experiência em frontend moderno. | Monólito Django com templates, HTMX e Alpine.js. Ver [05](05-arquitetura-tecnica.md). |
| API REST completa desde o início | Sem cliente externo, é trabalho sem consumidor. | Rotas HTML e endpoints internos no MVP. API pública somente leitura como Evolução. Ver [07](07-rotas-e-api.md). |
| Clima na página inicial | Valor editorial pequeno, mas o dono do projeto quer e o custo é baixo com Open-Meteo. | Bloco discreto "Hoje na escola" na Fase 3. Sem pautas a partir do clima. Ver [29](29-clima.md). |
| Usar APIs de notícias como fonte principal | APIs gratuitas têm limites baixos e restrições de uso. | Fontes RSS gratuitas curadas pelo administrador. Ver [21](21-curadoria-de-noticias.md). |
| Comentários públicos | Com menores, exigem moderação. O dono do projeto quer comentários; a solução é moderação prévia. | Comentários com nome, invisíveis até aprovação do autor da publicação, editor ou admin. Ver [20](20-reacoes-leituras-comentarios.md). |
| Aluno com perfil e conta | Risco LGPD desnecessário; a escola decidiu que alunos não têm cadastro. | Aluno é crédito de autoria registrado pelo professor, com política de nome e autorização. |
| Notificações por e-mail | Não há e-mail disponível. | Notificações no painel desde o MVP. |
| IA desde o planejamento | Correto adiar; o dono do projeto congelou a fase. | Fase 5 congelada; documento mantido como referência. |
| Busca dedicada (Elasticsearch, Meilisearch) | Volume não justifica. | PostgreSQL full-text search com `unaccent` e `pg_trgm`. |

## Complementos propostos que não estavam na ideia original

| Complemento | Por quê | Camada |
|---|---|---|
| **Tópicos** (tags de interesse) separados de disciplinas | "Inteligência Artificial" não é disciplina, mas é interesse de professores e assunto de notícias. Tópicos ligam equipe, publicações e notícias externas. | MVP (estrutura), uso pleno na Fase 4 |
| **Agenda** | Eventos são um tipo de publicação com data de evento. A home mostra "Próximos eventos" sem nova infraestrutura. | MVP |
| **Crédito sem conta** | Alunos, turmas ("Turma 1ª A"), convidados e entidades (Grêmio) são creditados sem usuário. É assim que o aluno aparece no jornal. | MVP |
| **Versionamento visível** | Número de versão discreto no rodapé, changelog e tags git. | MVP, ver [30](30-versionamento.md) |
| **Pauta** como entidade | Antes do rascunho existe a ideia. Uma sugestão de notícia vira pauta, que vira rascunho. Permite "banco de pautas" da redação. | Fase 4 |
| **Edições/coleções** | Um editor agrupa publicações em "Edição de outubro" ou "Especial Feira de Ciências". Dá ritmo editorial. | Evolução |
| **Newsletter por e-mail** | Forma mais eficaz de trazer leitores de volta sem rede social. | Evolução |
| **Página "Quem escreve"** | Lista de professores e a produção de cada um; reforça o caráter de comunidade. | MVP |

## Principais problemas e riscos

| Risco | Impacto | Mitigação |
|---|---|---|
| Baixa adesão dos professores | O jornal morre sem conteúdo | Editor de texto fácil, perfil rápido de preencher, sugestões de pauta, publicação em um clique |
| Login Microsoft bloqueado pelo tenant do estado | Ninguém consegue entrar | Senha de reserva com link de acesso gerado pelo admin; testar cedo (E09) |
| Comentários sem moderação a tempo | Leitores desmotivados; conteúdo pendente acumulado | Fila visível no painel, aprovação em lote, editores alertados após 3 dias, fechar comentários por publicação |
| Exposição de dados de menores | Risco legal e reputacional | Leitores anônimos, alunos sem conta, nome "Rafael S." por padrão, autorização registrada pelo professor, termo assinado, fotos com autorização |
| Dependência de uma só pessoa técnica | Projeto abandonado | Stack simples, documentação, deploy com um comando, backups automáticos |
| Reprodução indevida de conteúdo externo | Violação de direitos | Curadoria nunca armazena texto integral; publicação derivada é original e cita fonte |
| Over-engineering | Projeto nunca chega ao ar | Fases estritas; nada de fila, busca dedicada ou IA antes do jornal existir |
| Home lab fora do ar ou sem IP público | Site indisponível para a comunidade | Cloudflare Tunnel ou VPS pequena como borda; backups fora do servidor. Ver [24](24-infraestrutura-e-deploy.md) |

## Escopo por camada

| Camada | MVP | Evolução | Experimental |
|---|---|---|---|
| Conteúdo | Publicações com tipos, disciplinas, tópicos, áreas, créditos múltiplos, imagens | Coleções/edições, séries, vídeos incorporados | Versão em áudio |
| Editorial | Rascunho → publicado pelo autor; notificações no painel; revisão opcional com comentários editoriais | Agendamento, diff de versões, e-mail | Sugestão automática de revisores |
| Pessoas | Perfil da equipe, crédito de aluno, página "Quem escreve" | Estatísticas de participação | Linha do tempo editorial |
| Descoberta | Home, área, disciplina, perfil, busca full-text | Filtros combinados, páginas de tópico | Recomendação de leitura |
| Engajamento | Reações, contador de leituras, comentários moderados, clima na home | Newsletter | Enquetes |
| Curadoria | — | Fontes RSS, sugestões por interesse, pauta a partir de sugestão | Classificação e resumo por IA |
| IA | — | — | Congelada: classificação, assistente de escrita |

## Histórico

- 2026-09-12: versão inicial.
- 2026-09-12: incorporadas as respostas do dono do projeto: nome, alunos sem conta, autopublicação, comentários moderados, clima, sem e-mail, IA congelada, versionamento.
