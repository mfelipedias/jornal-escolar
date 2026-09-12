# 03 — Funcionalidades, priorização e o que não construir

## Lista de funcionalidades por domínio

Cada linha indica a camada (MVP, Evolução, Experimental), a fase do [roadmap](25-roadmap.md) e a prioridade MoSCoW.

### Conteúdo e leitura

| Funcionalidade | Camada | Fase | MoSCoW |
|---|---|---|---|
| Página de publicação com texto, imagens, créditos, disciplinas | MVP | 1 | Must |
| Tipos de publicação configuráveis | MVP | 1 | Must |
| Áreas, disciplinas e tópicos configuráveis pelo admin | MVP | 1 | Must |
| Home com destaques, últimas publicações e agenda | MVP | 1 | Must |
| Páginas de área, disciplina e tipo | MVP | 1 | Must |
| Perfil público da equipe | MVP | 1 | Must |
| Página "Quem escreve" (toda a equipe, com cargo) | MVP | 1 | Should |
| Página "Sobre o jornal" e "Privacidade" editáveis | MVP | 1 | Must |
| Versão do sistema no rodapé | MVP | 0 | Should |
| Página de tópico | MVP | 3 | Could |
| Clima "Hoje na escola" | MVP | 3 | Could |
| Feed RSS do jornal | MVP | 3 | Should |
| Coleções/edições | Evolução | 6 | Could |
| Vídeos incorporados (YouTube) | Evolução | 6 | Could |
| Modo escuro | Evolução | 6 | Won't por ora (tokens preparados) |

### Editorial

| Funcionalidade | Camada | Fase | MoSCoW |
|---|---|---|---|
| Editor de texto rico com imagens, links, listas, citações | MVP | 1 | Must |
| Salvamento automático | MVP | 1 | Must |
| Créditos múltiplos: equipe, alunos (sem conta), turmas, convidados | MVP | 1 | Must |
| Política de nome de aluno e marcação de autorização | MVP | 1 | Must |
| Estados: rascunho, publicado, arquivado; publicação pelo autor | MVP | 1 | Must |
| Checklist de publicação | MVP | 1 | Must |
| Notificações no painel (sino) | MVP | 1 | Must |
| Edição e despublicação por editor, com aviso ao autor | MVP | 1 | Must |
| Revisão opcional por colega; estados em revisão e alterações sugeridas | MVP | 2 | Should |
| Comentários editoriais internos | MVP | 2 | Should |
| Histórico de eventos e versões | MVP | 2 | Should |
| Painel editorial para editores | MVP | 2 | Should |
| E-mail por serviço gratuito | Evolução | 6 | Could |
| Agendamento de publicação | Evolução | 6 | Could |
| Diff entre versões | Evolução | 6 | Could |
| Banco de pautas | Evolução | 4 | Should |

### Pessoas

| Funcionalidade | Camada | Fase | MoSCoW |
|---|---|---|---|
| Login com conta Microsoft da escola | MVP | 1 | Must |
| Login com senha e link de primeiro acesso gerado pelo admin | MVP | 1 | Must |
| Contas criadas pelo admin com papel e cargo | MVP | 1 | Must |
| Perfil editável (foto, bio, formação, disciplinas, interesses) | MVP | 1 | Must |
| Assistente de primeiro acesso | MVP | 1 | Should |
| Exportar dados e anonimizar | MVP | 2 | Should |
| Estatísticas de participação no perfil | Evolução | 6 | Could |
| 2FA para admin | Evolução | 6 | Could |

### Descoberta

| Funcionalidade | Camada | Fase | MoSCoW |
|---|---|---|---|
| Busca full-text | MVP | 3 | Must |
| Filtros por área, disciplina, tipo, pessoa, período | MVP | 3 | Must |
| Ordenação por recência e por leituras | MVP | 3 | Should |
| "Leia também" | MVP | 3 | Should |
| Sugestão ao digitar | Evolução | 6 | Could |

### Engajamento

| Funcionalidade | Camada | Fase | MoSCoW |
|---|---|---|---|
| Compartilhar (link, WhatsApp) | MVP | 1 | Should |
| Reações (quatro tipos) | MVP | 3 | Should |
| Contador de leituras | MVP | 3 | Should |
| Comentários públicos com moderação prévia pelo autor/editor | MVP | 3 | Should |
| Fila de moderação de comentários no painel | MVP | 3 | Should |
| Newsletter | Evolução | 6 | Could |
| Enquetes | Experimental | 6 | Could |

### Curadoria e IA

| Funcionalidade | Camada | Fase | MoSCoW |
|---|---|---|---|
| Fontes RSS gratuitas (português e inglês) | Evolução | 4 | Should |
| Coleta periódica, deduplicação, classificação por palavras-chave | Evolução | 4 | Should |
| "Sugestões para você" com ações | Evolução | 4 | Should |
| Pautas a partir de sugestões | Evolução | 4 | Should |
| Tudo de IA (classificação, resumo, assistente) | Experimental | 5 | **Congelado** |
| Geração de texto de matéria por IA | — | — | Won't |

### Administração

| Funcionalidade | Camada | Fase | MoSCoW |
|---|---|---|---|
| Django Admin para taxonomia, usuários, tipos, configurações, páginas | MVP | 1 | Must |
| Gestão de destaques da home | MVP | 1 | Must |
| Backup automático | MVP | 1 | Must |
| Log de erros no admin (sem e-mail) | MVP | 1 | Should |
| Log de auditoria | MVP | 2 | Should |

## O que NÃO construir agora

| Não construir | Motivo | Quando reconsiderar |
|---|---|---|
| Contas para alunos ou leitores | Decisão da escola; dados de menores | Não reconsiderar |
| Perfil público de aluno | Idem | Não reconsiderar |
| Comentários sem moderação prévia | Público menor de idade | Não reconsiderar |
| Threads de comentários entre leitores | Vira rede social; moderação dobra | Não reconsiderar |
| Frontend separado (React/Next) | Dobra o custo de manutenção | Se surgir app móvel |
| API REST pública | Sem consumidor | Quando existir integração real |
| Busca dedicada | PostgreSQL resolve | Se ficar lenta |
| Fila de tarefas e Redis no MVP | Nenhuma tarefa assíncrona até a Fase 4 | Fase 4, Procrastinate |
| E-mail | Não há; notificações no painel bastam | Fase 6, serviço gratuito |
| Qualquer coisa com IA | Congelado pelo dono do projeto | Quando tudo estiver funcional |
| Clima auto-hospedado | API pública gratuita basta | Se a API for limitada |
| Previsão de vários dias, mapas | Não é site de clima | Não reconsiderar |
| Gamificação, rankings | Contraria o caráter editorial | Não reconsiderar |
| Chat entre usuários | Fora do escopo | Não reconsiderar |
| Aplicativo móvel | Site responsivo atende | Não antes de um ano |
| Múltiplas escolas | Uma escola | Projeto novo |
| Editor colaborativo em tempo real | Complexidade alta | Não antes da Fase 6 |
| Modo escuro | Sem pedido; tokens já preparados | Quando houver pedido |

## Estimativa relativa de complexidade

Escala: 1 (um dia) a 5 (várias semanas), para uma pessoa com o perfil do dono do projeto.

| Bloco | Complexidade | Observação |
|---|---|---|
| Setup, Docker, CI, versionamento | 2 | |
| Login Microsoft + senha + links de acesso | 2 | O risco é externo (tenant), não técnico |
| Taxonomia + admin + seed | 1 | |
| Publicação, créditos com alunos, permissões | 2 | |
| Editor TipTap, upload, sanitização | 4 | Maior risco técnico do MVP |
| Notificações no painel | 1 | |
| Páginas públicas | 3 | Template e CSS |
| Perfil e assistente | 2 | |
| Revisão opcional com comentários editoriais | 3 | |
| Busca e filtros | 2 | |
| Reações e leituras | 2 | |
| Comentários públicos e moderação | 2 | |
| Clima | 1 | |
| Coleta RSS, deduplicação, classificação | 3 | |
| Recomendação e sugestões | 2 | |
| IA | 4 | Congelada |

## Histórico

- 2026-09-12: versão inicial.
- 2026-09-12: reescrito conforme respostas: alunos sem conta, autopublicação, comentários moderados, clima, sem e-mail, IA congelada, versionamento.
