# 17 — Tela de revisão

Rota: `/painel/publicacoes/<id>/revisar/` · Nome: `editorial:review` · Camada: **MVP** (Should) · Fase 2

## Objetivo

Quando um autor pede a leitura de um colega, o colega precisa ler o texto como ficará publicado, comentar trechos e devolver (ou publicar, se autorizado) em uma única tela. A revisão é opcional e entre pares; não é aprovação hierárquica.

## Quem acessa

Revisor designado, editor, admin. Autores acessam a mesma tela em modo "responder comentários", sem botões de decisão.

## Layout

```
┌──────────────────────────────────────────────────────────────┐
│ ← Revisões   Título   [Em revisão]   Pedido há 2 dias por Carla │
│ Nota da autora: "Dá uma olhada na introdução e nos dados"    │
│ Autores: Carla Souza · Rafael S. (aluno, 2ª B)              │
│ [Editar texto] [Sugerir alterações] [Aprovar ▾]              │
├──────────────────────────────────┬───────────────────────────┤
│ TEXTO (renderização final)       │ COMENTÁRIOS (3 abertos)   │
│ Trechos comentados em amarelo;   │ ┌───────────────────────┐ │
│ clicar leva ao comentário.       │ │ "…a água ferve a 100…"│ │
│ Selecionar texto → "Comentar".   │ │ Marcos · há 1h        │ │
│                                  │ │ Depende da pressão.   │ │
│                                  │ │ [Responder] [Resolver]│ │
│                                  │ └───────────────────────┘ │
│                                  │ [Novo comentário geral]   │
│                                  ├───────────────────────────┤
│                                  │ CHECKLIST                 │
│                                  │ ✓ Disciplinas: Física     │
│                                  │ ✓ Autorização do aluno    │
│                                  ├───────────────────────────┤
│                                  │ HISTÓRICO                 │
│                                  │ 10 set · Carla pediu revisão │
└──────────────────────────────────┴───────────────────────────┘
```

No celular: texto em cima, painel de comentários por botão flutuante com contador.

## Comentários editoriais

- **Ancorado**: selecionar texto mostra "Comentar". Guarda `anchor_text` (≤ 300) e posições no documento. Se o trecho mudar, o comentário aparece como "trecho alterado", ainda visível.
- **Geral**: sem âncora.
- Respostas em um nível. Resolver: revisor ou autor. Resolvidos ficam colapsados.

## Ações e efeitos

| Botão | Quem | Pré-condição | Efeito |
|---|---|---|---|
| Editar texto | revisor, editor+ | | Abre o editor; edições ficam registradas como `edited_by_third_party`; autor é notificado. |
| Sugerir alterações | revisor, editor+ | ao menos 1 comentário aberto | `changes_requested`; notificação aos autores com os comentários. |
| Aprovar | revisor, editor+ | | Volta a `draft` com evento `approved`; selo "Revisado por Marcos"; autor notificado e publica quando quiser. |
| Aprovar e publicar | revisor com `can_publish`, editor+ | checklist ok | Publica; autor notificado. |
| Recusar revisão | revisor | | Remove a atribuição; autor notificado para escolher outro colega. |
| Arquivar | editor+ | nota obrigatória | |

Menu "▾" em Aprovar: "Aprovar e publicar" aparece apenas quando permitido.

## Regras

- Ninguém revisa o próprio texto.
- O revisor não altera créditos; se achar erro, comenta.
- Revisão pedida e sem ação por 5 dias gera notificação a ambos; após 15 dias o autor pode cancelar o pedido e publicar.

## Histórico da publicação

Lista de `EditorialEvent` em ordem cronológica. Editor+ vê "Ver versões" (`ArticleRevision`); diff visual é Evolução.

## Histórico

- 2026-09-12: versão inicial.
- 2026-09-12: reescrito para revisão opcional entre pares; sem fila geral; "pode publicar por mim"; sem e-mail.
