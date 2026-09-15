# 15 — Painel da equipe

Prefixo: `/painel/` · Layout: `layouts/dashboard.html` · Camada: **MVP** · Fases 1 a 4

O painel é o mesmo para todos os papéis; o que muda é o menu e alguns blocos.

## Menu lateral

| Item | Rota | Quem | Fase |
|---|---|---|---|
| Início | `/painel/` | todos | 1 |
| Minhas publicações | `/painel/publicacoes/` | todos | 1 |
| Nova publicação | `/painel/publicacoes/nova/` | todos | 1 |
| Revisões (contador) | `/painel/revisao/` | todos | 2 |
| Comentários (contador) | `/painel/comentarios/` | todos | 3 |
| Sugestões (contador) | `/painel/sugestoes/` | todos | 4 |
| Pautas | `/painel/pautas/` | todos | 4 |
| Editorial | `/painel/editorial/` | editor+ | 2 |
| Perfil | `/painel/perfil/` | todos | 1 |
| Conta | `/painel/conta/` | todos | 1 |
| Administração | `/admin/` | admin | 1 |
| Ver o jornal | `/` | todos | 1 |

Sino de notificações no cabeçalho do painel (todas as fases a partir da 1). Versão do sistema no rodapé do menu.

## Início do painel

Rota: `/painel/` · Nome: `dashboard:home`

**Objetivo.** Responder "o que preciso fazer agora?" em uma olhada.

**Blocos:**

1. **Pendências** (só se houver algo):
   - "3 comentários aguardam sua aprovação" → fila de comentários (Fase 3).
   - "Lucas pediu que você revise 'Feira de Ciências'" → revisão (Fase 2).
   - "Seu texto 'X' foi editado por Ana (coordenação)" → publicação.
   - "Complete seu perfil: falta foto" → perfil.
2. **Continuar escrevendo**: até 3 rascunhos recentes com título, última edição, "Abrir".
3. **Sugestões para você** (Fase 4): 3 notícias com ações rápidas.
4. **Suas últimas publicadas**: 3 itens com leituras, reações e comentários dos últimos 30 dias.
5. **Números** (`stat`): publicadas, rascunhos, leituras em 30 dias, comentários aprovados.

## Minhas publicações

Rota: `/painel/publicacoes/` · Nome: `dashboard:my_articles`

- Tabela (desktop) ou lista (celular): título, tipo, estado, meu papel, última atualização, leituras e comentários pendentes.
- Filtro por estado (chips): Todos, Rascunhos, Em revisão, Alterações sugeridas, Publicados, Arquivados.
- Ações por linha: Abrir, Ver no jornal, "mais": duplicar como rascunho, arquivar, fechar/abrir comentários.
- Aba "Revisando" com publicações em que sou revisor.

## Revisões

Rota: `/painel/revisao/` · Nome: `editorial:queue` · Fase 2

Sem fila geral: aparecem só as revisões pedidas a mim (aba "Pedidas a mim") e as que eu pedi (aba "Que eu pedi"). Editores têm a aba "Todas em revisão". Cada item: título, autores, nota do autor, enviado há X dias, "pode publicar por mim" sim/não, botão "Revisar". Ver [17](17-tela-de-revisao.md).

## Comentários

Rota: `/painel/comentarios/` · Nome: `engagement:moderation` · Fase 3

Fila de moderação descrita em [20](20-reacoes-leituras-comentarios.md): pendentes das minhas publicações (editores: de todas), aprovar/rejeitar/editar nome/responder, seleção em lote, abas Pendentes, Aprovados, Rejeitados.

## Sugestões e Pautas

Rotas: `/painel/sugestoes/` e `/painel/pautas/` · Fase 4

Descritas em [21](21-curadoria-de-noticias.md). Sugestões: abas Para você, Salvas, Ignoradas; cards com ações Ignorar, Salvar, Interessante, Virar pauta; filtro por tópico, fonte e idioma. Pautas: quadro Abertas, Atribuídas, Em produção, Concluídas; "Criar rascunho" gera publicação com fontes preenchidas.

## Editorial (editor+)

Rota: `/painel/editorial/` · Fase 2. Ver [18](18-painel-administrativo.md).

## Notificações

Modelo `Notification`. Sino com contador de não lidas; lista das últimas 20 com "marcar todas como lidas"; cada item leva à URL do objeto. Sem e-mail.

## Histórico

- 2026-09-12: versão inicial.
- 2026-09-12: reescrito: sem convite nem painel de aluno, comentários, revisões sem fila geral, notificações no painel desde a Fase 1.
- 2026-09-14 (E24): implementado o que é da Fase 1. Detalhes decididos na implementação:
  - Pendências da Fase 1 são as notificações não lidas (até 5, com link para todas; abrir uma a marca como lida) e "Complete seu perfil". O bloco some quando não há nada.
  - "Suas últimas publicadas" mostra tipo e data; leituras, reações e comentários entram com a Fase 3, assim como os números "leituras em 30 dias" e "comentários aprovados". Na Fase 1 os números são publicadas e rascunhos.
  - "Minhas publicações" lista os textos em que a pessoa é autora ou coautora (qualquer estado) e os publicados em que aparece como colaboração ou edição. Chips da Fase 1: Todos, Rascunhos, Publicados, Arquivados. Colunas de leituras e comentários pendentes, "fechar/abrir comentários" e a aba "Revisando" ficam para as fases deles.
  - Ações por linha: Abrir, Ver no jornal e, no menu "mais", Duplicar como rascunho, Arquivar (só quando não pede motivo; editor arquivando texto alheio usa o editor) e Restaurar como rascunho.
  - Duplicar copia texto, capa, tipo, disciplinas, tópicos, evento, fontes e créditos (sem revisão e edição); quem duplica vira autor. As imagens viram cópias novas, porque cada imagem pertence a uma publicação só.
  - O menu mostra só os itens da Fase 1. Perfil, Conta, Notificações e Nova publicação passaram a usar o layout do painel; o editor volta para "Minhas publicações".
- 2026-09-14: E29: chips "Em revisão" e "Alterações sugeridas" em "Minhas publicações" (`?estado=em-revisao` e `?estado=alteracoes-sugeridas`). A aba de revisões pedidas a mim continua para a E31.
- 2026-09-14: E31: item "Revisões" no menu com contador das revisões pedidas a mim. `/painel/revisao/` com as abas `?aba=pedidas-a-mim` (padrão), `que-eu-pedi` (textos em revisão que assino) e `todas` (editor+), só com textos em revisão, do pedido mais antigo para o mais recente. A aba "Revisando" de "Minhas publicações" ficou coberta por essa tela.
- 2026-09-14: E33: item "Editorial" no menu (editor+), que agrupa visão geral, todas as publicações, Destaques e Páginas em abas. Os itens "Destaques" e "Páginas" da E25 saíram do menu; os endereços continuam. Detalhes em [18](18-painel-administrativo.md).
- 2026-09-14: E39: números do início ganham "Leituras em 30 dias" (registros diários de leitura das minhas publicadas, hoje incluído). "Suas últimas publicadas" mostra o total de leituras e de reações de cada uma (total desde a publicação, não só dos últimos 30 dias). "Minhas publicações" ganha a coluna "Leituras" (só publicadas; as outras mostram "—"). Comentários entram na E40 e E41.
- 2026-09-14: E40: número "Comentários aprovados" no início (soma de `comments_count` das minhas publicadas). Bloco de pendentes, coluna de pendentes e a fila são da E41.
- 2026-09-15: E41: item "Comentários" no menu com o contador de pendentes que a pessoa modera (editores: do jornal todo). No início, a primeira pendência é "N comentários aguardam sua aprovação" (editor com pendentes fora dos seus textos: "N comentários aguardam aprovação no jornal (M nas suas publicações)"); os avisos de comentário do sino não se repetem na lista. "Minhas publicações" ganha a coluna "Comentários pendentes" (link para a fila filtrada; "fechados" quando a publicação não aceita mais) e, no menu "mais" das publicadas, "Fechar comentários" / "Abrir comentários". A fila tem as abas Pendentes, Aprovados e Rejeitados, como previsto; editores veem todas as publicações na mesma fila, sem aba separada.
- 2026-09-15: R5: menu lateral em pílulas (ativo `accent-soft`), contadores em pílula `sun-soft`; a barra de carregamento do topo também aparece no painel e no editor, sem fade nas trocas do HTMX.
