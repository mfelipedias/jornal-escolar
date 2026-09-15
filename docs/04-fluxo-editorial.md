# 04 — Fluxo editorial

## Objetivo

Cada membro da equipe é responsável pelo que publica. O sistema não impõe aprovação; oferece revisão por colega quando o autor quiser, e dá a editores e admin o poder de intervir depois. O fluxo precisa caber em uma equipe onde a maioria publica sozinha e ocasionalmente pede uma segunda leitura.

## Estados de uma publicação

| Estado | Código | Significado | Visível ao público |
|---|---|---|---|
| Rascunho | `draft` | Em escrita. Só autores, revisor convidado, editores e admin veem. | Não |
| Em revisão | `in_review` | Autor pediu a leitura de um colega. Opcional. | Não |
| Alterações sugeridas | `changes_requested` | Colega devolveu com comentários. Volta ao autor. | Não |
| Publicado | `published` | No ar. | Sim |
| Arquivado | `archived` | Retirado do ar ou abandonado. Preservado. | Não |

O estado "aprovado" foi removido: como o autor publica, aprovação e publicação são o mesmo ato. Agendamento (Evolução) usa `published` com `published_at` futuro.

## Diagrama de transições

```mermaid
stateDiagram-v2
    [*] --> draft: criar
    draft --> published: publicar (autor, editor, admin)
    draft --> in_review: pedir revisão (opcional)
    in_review --> changes_requested: sugerir alterações (revisor)
    in_review --> draft: revisor aprovou; volta ao autor com selo "revisado"
    in_review --> published: revisor aprova e publica (se autor permitiu)
    changes_requested --> draft: autor retoma
    changes_requested --> in_review: reenviar
    published --> archived: arquivar / despublicar
    published --> draft: reabrir (texto continua no ar até salvar de novo)
    draft --> archived: abandonar
    archived --> draft: restaurar
```

Observações:

- **Reabrir uma publicação não a tira do ar.** No MVP, edições após publicação alteram o registro diretamente e geram `ArticleRevision`; a URL nunca fica vazia. "Editar sem publicar as mudanças até terminar" é Evolução.
- **Pedir revisão** cria uma contribuição `reviewer` para o colega escolhido e o notifica no painel. O autor marca se o revisor pode publicar diretamente ("pode publicar por mim") ou apenas devolver.

## Regras de transição

| Transição | Quem pode | Condições | Efeitos |
|---|---|---|---|
| criar | staff, editor, admin | — | Criador vira `author`. |
| publicar | autores/coautores da publicação, editor, admin | Checklist obrigatória ok ([abaixo](#validações-antes-de-publicar)) | Define `published_at`, slug definitivo, indexa, notifica coautores. |
| pedir revisão | autores | Um revisor escolhido | Notifica o revisor. |
| sugerir alterações | revisor designado, editor, admin | Ao menos um comentário editorial | Notifica autores. |
| aprovar (devolver com selo) | revisor designado, editor, admin | — | Evento `approved`; badge "Revisado por X" no painel e, se autor quiser, crédito público. |
| aprovar e publicar | revisor designado com permissão do autor, editor, admin | Checklist ok | Publica. |
| arquivar | autores, editor, admin | Nota opcional (obrigatória para editor/admin arquivando texto alheio) | URL responde 410. |
| restaurar | autores, editor, admin | — | Volta a `draft`. |
| editar publicada | autores, editor, admin | — | Evento `edited_after_publish`; se editor/admin edita texto alheio, o autor é notificado. |

Toda transição e toda edição por terceiro gera `EditorialEvent` (quem, quando, de qual estado para qual, nota). É a auditoria editorial e alimenta a linha do tempo do perfil.

## Papéis de contribuição

| Papel | Código | Significado | Crédito público |
|---|---|---|---|
| Autor | `author` | Escreveu o texto. Pode haver vários. | Em destaque |
| Coautor | `coauthor` | Escreveu com responsabilidade menor. | Sim |
| Colaborador | `collaborator` | Pesquisa, fotos, entrevista, dados. Campo "contribuição" (ex.: "fotos"). | "Com colaboração de" |
| Revisor | `reviewer` | Colega que revisou. | Discreto, opcional |
| Editor | `editor` | Responsável editorial pela publicação (quando um editor interveio). | Discreto, opcional |

Uma contribuição aponta para um `User` da equipe **ou** é um crédito sem conta com `display_name`. Créditos sem conta cobrem:

- **Alunos** (`is_student = true`, com `class_group`, ex.: "2ª série B"). O nome de exibição segue a política `credits.student_name_policy` (padrão `first_initial`: "Rafael S."); o professor pode escrever o nome completo se houver autorização. O crédito de aluno exige a marcação `consent_ok` ("tenho autorização do responsável para publicar o nome do aluno"). Ver [23](23-seguranca-e-lgpd.md).
- **Turmas** ("Turma 1ª A"), **convidados** ("Maria Silva, ex-aluna"), **entidades** ("Grêmio Estudantil").

Autor e coautor têm as mesmas permissões de edição; a diferença é só de crédito. Créditos sem conta não têm permissão nenhuma.

## Revisão por colega (opcional)

- Ao pedir revisão, o autor escolhe um colega, escreve uma nota ("olha a introdução") e marca ou não "pode publicar por mim".
- O revisor vê a publicação na aba "Revisões pedidas a mim" do painel e na tela de revisão ([17](17-tela-de-revisao.md)).
- Comentários editoriais são internos e ficam no histórico.
- Não existe fila geral nem "assumir revisão": quem pede escolhe. Editores veem tudo de qualquer forma.
- Sugestão automática de revisor por afinidade fica congelada com a IA.

## Moderação por editores e admin

- Podem editar, despublicar e arquivar qualquer publicação. Ao fazê-lo em texto alheio, a nota é obrigatória e o autor recebe notificação no painel.
- Podem alterar créditos (ex.: corrigir nome de aluno).
- Podem marcar destaques da home.
- Os comentários públicos têm fluxo próprio em [20](20-reacoes-leituras-comentarios.md).

## Notificações

Sem e-mail no MVP ([27](27-decisoes-pendentes-e-perguntas.md) P7). Todas as notificações são **no painel** (sino no cabeçalho e bloco "Pendências" no início do painel), modelo `Notification`.

| Evento | Quem recebe |
|---|---|
| Pedido de revisão | Revisor |
| Alterações sugeridas / aprovado | Autores |
| Publicado por revisor ou editor | Autores |
| Editado ou arquivado por editor/admin | Autores |
| Novo comentário público aguardando moderação | Autores; editores se pendente há mais de 3 dias |
| Revisão parada há mais de 5 dias | Revisor e autor |

E-mail por serviço gratuito (Brevo, Resend) é Evolução, ligado por configuração, sem mudança de modelo.

## Validações antes de publicar

Checklist automática no editor:

1. Título com até 120 caracteres. **Bloqueia.**
2. Ao menos uma disciplina. **Bloqueia.**
3. Um tipo de publicação. **Bloqueia.**
4. Corpo não vazio. **Bloqueia.**
5. Todo crédito de aluno com `consent_ok` marcado. **Bloqueia.**
6. Toda imagem com `has_people` tem `consent_ok`. **Bloqueia.**
7. Linha fina preenchida. Aviso.
8. Imagem de capa com texto alternativo. Aviso (obrigatório para destaque na home).
9. Fontes citadas quando a publicação nasceu de uma sugestão externa (Fase 4). Aviso.

## Implementação (E29)

- **Um revisor por vez.** O revisor designado é o crédito `reviewer` com conta. Pedir revisão a outro colega (por exemplo, ao reenviar) substitui o anterior; o crédito removido fica registrado no histórico.
- **Cancelar pedido** pode ser feito pelo autor a qualquer momento (a revisão é opcional); o texto volta a `draft`, o crédito de revisão sai e o revisor é avisado. Enquanto está `in_review`, o autor não publica: cancela antes. Editores publicam de qualquer estado.
- **Recusar revisão** (`in_review → draft`) pelo próprio revisor, que sai dos créditos; os autores são avisados.
- **Retomar** (`changes_requested → draft`) e **publicar direto de `changes_requested`** ficam com autores e editores, como no editor ([16](16-editor-de-publicacoes.md)).
- **Sugerir alterações exige ao menos um comentário editorial aberto** (desde a E32). A nota opcional vira um comentário geral.
- Ninguém revisa o próprio texto: autores e coautores (mesmo editores) não aprovam nem sugerem alterações nos textos que assinam.
- O revisor designado vê o texto em qualquer estado não publicado, edita só enquanto está `in_review` e não altera créditos.
- Eventos: toda mudança de estado grava `status_change` (de, para, quem, nota). Além dele, `reviewer_assigned`, `reviewer_removed` (cancelado ou recusado), `approved`, `contributor_changed` (créditos; alunos e convidados sem nome), `edited_after_publish` e `edited_by_third_party` (no máximo um por pessoa a cada 15 minutos, por causa do autosave).
- O autor editando durante a revisão avisa o revisor no painel (um aviso não lido por vez).

## Histórico

- 2026-09-12: versão inicial (seis estados, aprovação obrigatória).
- 2026-09-12: reescrito. Autopublicação pela equipe, revisão opcional, estado "aprovado" removido, alunos como crédito sem conta, notificações só no painel.
- 2026-09-14: E29. Seção "Implementação": um revisor por vez, cancelar a qualquer momento, recusar revisão, nota obrigatória para sugerir alterações até a E32 e tipos de evento `reviewer_removed` e `approved`.
- 2026-09-14: E32. Sugerir alterações exige ao menos um comentário aberto; comentários geram eventos e avisos (ver [17](17-tela-de-revisao.md)).
- 2026-09-15: E41. "Novo comentário público aguardando moderação" agrupado: um aviso por publicação enquanto não é lido, com o total atualizado; editores recebem pelo comando `notify_pending_comments` quando o pendente passa de 3 dias (ver [20](20-reacoes-leituras-comentarios.md)).
