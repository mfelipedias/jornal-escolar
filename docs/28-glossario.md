# 28 — Glossário

| Termo (interface) | Nome no código | Definição |
|---|---|---|
| Publicação | `Article` | Qualquer conteúdo do jornal: notícia, projeto, entrevista etc. "Artigo" no código, "publicação" na interface. |
| Tipo de publicação | `ArticleType` | Categoria editorial: Notícia, Reportagem, Artigo de opinião, Entrevista, Projeto, Produção de aluno, Divulgação científica, Evento, Curiosidade, Resenha. |
| Área do conhecimento | `KnowledgeArea` | Agrupamento de disciplinas (ex.: Ciências da Natureza). |
| Disciplina | `Discipline` | Matéria escolar (ex.: Física). Pertence a uma área. |
| Tópico | `Topic` | Tag de interesse ou assunto (ex.: Inteligência Artificial). Liga professores, publicações e notícias. |
| Linha fina | `subtitle` | Frase abaixo do título que resume a publicação. |
| Capa | `cover` | Imagem principal da publicação. |
| Crédito / Contribuição | `ArticleContributor` | Registro de quem participou e em que papel. |
| Autor, Coautor, Colaborador, Revisor, Editor (da publicação) | `role` em `ArticleContributor` | Papéis de contribuição. |
| Papel (do usuário) | `User.role` | `staff`, `editor`, `admin`. |
| Cargo | `User.staff_kind` | Professor, Monitor, Coordenação, Direção, Sala de leitura, Outro. Só exibição. |
| Equipe | `staff` | Qualquer funcionário da escola com conta. |
| Aluno (crédito) | `ArticleContributor.is_student` | Aluno creditado em uma publicação, sem conta. |
| Editor (papel) | `editor` | Membro da equipe com poder de moderação sobre todo o jornal. |
| Revisor | contribuição `reviewer` | Colega convidado a revisar uma publicação específica. Opcional. |
| Rascunho, Em revisão, Alterações sugeridas, Publicado, Arquivado | `status` | Estados do fluxo editorial. |
| Comentário editorial | `EditorialComment` | Comentário interno da revisão. Nunca público. |
| Comentário (público) | `Comment` | Comentário de leitor, visível só após aprovação. |
| Notificação | `Notification` | Aviso no painel (sino). Não há e-mail. |
| Link de acesso | `AccessLink` | Link gerado pelo admin para primeiro acesso ou redefinição de senha. |
| Hoje na escola | `weather` | Bloco de clima da home (Open-Meteo). |
| Versão | `VERSION` | Número SemVer exibido no rodapé. |
| Evento editorial | `EditorialEvent` | Registro de uma ação no fluxo (quem, quando, o quê). |
| Versão | `ArticleRevision` | Snapshot do conteúdo em um momento. |
| Destaque | `is_featured` | Publicação escolhida para o topo da home. |
| Agenda | tipo com `has_event_date` | Publicações que são eventos com data. |
| Quem escreve | `/professores/` | Lista pública de professores. |
| Reação | `Reaction` | Interessante, Aprendi algo, Gostei, Parabéns. |
| Leitura | `ArticleRead` | Visita que atendeu ao critério de tempo e rolagem. |
| Fonte (de notícia) | `NewsSource` | Veículo ou feed cadastrado para curadoria. |
| Notícia externa / Sugestão | `NewsItem` / `NewsRecommendation` | Item coletado de uma fonte; sugestão é a relação com um professor. |
| Pauta | `StoryIdea` | Ideia de matéria, antes do rascunho. |
| Fontes (de uma publicação) | `sources` | Referências citadas ao final do texto. |
| Curadoria | app `curation` | Coleta e recomendação de notícias externas. |
| Painel | `/painel/` | Área autenticada. |
| Editorial (tela) | `/painel/editorial/` | Visão do editor sobre todas as publicações. |
| Administração | `/admin/` | Django Admin. |
| Fragmento | `partials/` | Pedaço de HTML devolvido ao HTMX. |
| Política de autopublicação | `editorial.self_publish` | `staff`: cada membro publica o próprio texto (decidido). |
| Política de nome de aluno | `credits.student_name_policy` | Como o nome do aluno aparece no crédito (`first_initial` por padrão). |
| Autorização | `consent_ok` | Professor declara ter o termo do responsável para nome ou imagem do aluno. |
| Chave anônima | cookie `jv` / `anon_key` | Identificador aleatório do visitante para reações e leituras. |
| MVP / Evolução / Experimental | — | Camadas de escopo definidas em [README](README.md). |

## Histórico

- 2026-09-12: versão inicial.
- 2026-09-12: termos atualizados conforme decisões (equipe, cargo, comentários, notificação, link de acesso, clima, versão).
