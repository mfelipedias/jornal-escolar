# 02 — Personas, papéis e matriz de permissões

## Personas

### Leitora — "Bia, 16 anos, 2ª série"
Entra pelo celular por um link no grupo da turma. Quer ler a matéria da amiga, ver o que aconteceu na feira de ciências, deixar um comentário e sair. Não tem conta e não vai criar uma.

Necessidades: leitura confortável no celular, reagir e comentar sem login, encontrar conteúdo de uma turma ou de um professor.

### Aluno participante — "Rafael, 17 anos, 3ª série"
Escreveu um texto para o projeto de Sociologia. Não tem conta no sistema. Entrega o texto ao professor (documento, e-mail, papel), que o revisa, publica e credita Rafael como autor. Rafael quer ver o nome dele no jornal e mostrar para a família.

Necessidades: crédito claro e correto; nome exibido do jeito combinado com o professor.

### Professora autora — "Carla, Biologia"
Escreve uma vez por mês, geralmente sobre um projeto da turma, às vezes com textos dos alunos. Publica sozinha. Gostaria de receber ideias de pauta ligadas ao que ensina e de saber quando alguém comenta.

Necessidades: perfil preenchido em cinco minutos, editor parecido com o Word, publicar em um clique, moderar comentários das próprias publicações, pedir opinião de um colega quando quiser.

### Monitor — "Lucas, monitor escolar"
Acompanha o Grêmio e os eventos. Publica avisos e coberturas de eventos. Tem conta como membro da equipe, com cargo "Monitor".

Necessidades: mesmo painel do professor; tipo "Evento" fácil de usar.

### Coordenadora — "Ana, coordenação pedagógica"
Não escreve com frequência, mas responde pelo que vai ao ar. Quer poder despublicar, corrigir um crédito ou aprovar um comentário quando o professor não está disponível. Escolhe os destaques da home.

Necessidades: visão geral do que está publicado e pendente, poder de moderação sobre tudo, sem precisar entender o sistema a fundo.

### Administrador — o dono do projeto
Configura áreas, disciplinas, tipos, fontes de notícia, cria contas da equipe. Mantém o servidor.

Necessidades: Django Admin bem configurado, logs, backups, poucas telas customizadas.

## Tipos de usuário

Somente funcionários da escola têm conta. Alunos, famílias e comunidade são visitantes.

| Papel | Código | Quem | Descrição |
|---|---|---|---|
| Visitante | — | Alunos, famílias, comunidade | Lê, busca, reage, comenta (comentário passa por moderação). |
| Equipe | `staff` | Professores, monitores, biblioteca, secretaria e outros funcionários | Escreve, publica, edita e arquiva as próprias publicações; credita alunos; modera comentários das próprias publicações; pede revisão opcional a colegas; tem perfil público; recebe sugestões de pauta. |
| Editor | `editor` | Coordenação, direção ou professor de confiança | Tudo da equipe, mais: publica, edita, despublica qualquer publicação; modera qualquer comentário; define destaques da home; corrige créditos. |
| Administrador | `admin` | Dono do projeto | Tudo do editor, mais configuração do sistema, contas, taxonomia, fontes, auditoria. |

Papéis são hierárquicos: `admin` ⊃ `editor` ⊃ `staff`. Um usuário tem um papel.

Enquanto a escola não definir editores, o administrador exerce esse papel. Promover alguém a editor depois é uma mudança de campo no admin, sem código.

Além do papel, cada conta tem um **cargo** (`staff_kind`) apenas para exibição: `teacher` (Professor), `monitor` (Monitor), `coordinator` (Coordenação), `principal` (Direção), `librarian` (Sala de leitura), `other` (texto livre no `headline`). O cargo não dá permissão; o papel dá.

"Revisor" não é papel: qualquer membro da equipe pode ser convidado a revisar uma publicação específica ([04](04-fluxo-editorial.md)).

## Matriz de permissões

Legenda: ✅ sim · 🔒 apenas nas próprias publicações · 🟡 se designado revisor · ❌ não

| Ação | Visitante | Equipe | Editor | Admin |
|---|---|---|---|---|
| Ler publicações publicadas | ✅ | ✅ | ✅ | ✅ |
| Buscar e filtrar | ✅ | ✅ | ✅ | ✅ |
| Reagir | ✅ (cookie anônimo) | ✅ | ✅ | ✅ |
| Comentar (vai para moderação) | ✅ | ✅ | ✅ | ✅ |
| Ver perfil público da equipe | ✅ | ✅ | ✅ | ✅ |
| Entrar (Microsoft ou senha) | ❌ | ✅ | ✅ | ✅ |
| Editar o próprio perfil | ❌ | 🔒 | 🔒 | ✅ |
| Criar rascunho | ❌ | ✅ | ✅ | ✅ |
| Editar rascunho | ❌ | 🔒 ou 🟡 | ✅ | ✅ |
| Creditar alunos e colegas | ❌ | 🔒 | ✅ | ✅ |
| Publicar | ❌ | 🔒 | ✅ | ✅ |
| Editar publicação publicada | ❌ | 🔒 | ✅ | ✅ |
| Arquivar / despublicar | ❌ | 🔒 | ✅ | ✅ |
| Pedir revisão a um colega | ❌ | 🔒 | ✅ | ✅ |
| Comentar na revisão (interno) | ❌ | 🔒 ou 🟡 | ✅ | ✅ |
| Aprovar / solicitar alterações em revisão | ❌ | 🟡 | ✅ | ✅ |
| Moderar comentários públicos | ❌ | 🔒 | ✅ | ✅ |
| Responder comentários como autor | ❌ | 🔒 | ✅ | ✅ |
| Definir destaques da home | ❌ | ❌ | ✅ | ✅ |
| Ver sugestões de pauta (Fase 4) | ❌ | ✅ | ✅ | ✅ |
| Criar pauta a partir de sugestão (Fase 4) | ❌ | ✅ | ✅ | ✅ |
| Upload de imagens | ❌ | ✅ | ✅ | ✅ |
| Criar contas da equipe | ❌ | ❌ | ❌ | ✅ |
| Mudar papel de um usuário | ❌ | ❌ | ❌ | ✅ |
| Gerenciar áreas, disciplinas, tópicos, tipos | ❌ | ❌ | ❌ | ✅ |
| Gerenciar fontes de notícia (Fase 4) | ❌ | ❌ | ❌ | ✅ |
| Configurações, auditoria, anonimização | ❌ | ❌ | ❌ | ✅ |

Notas da matriz:

- Ninguém revisa o próprio texto ([04](04-fluxo-editorial.md)): em "Aprovar / solicitar alterações", o ✅ de editor e admin vale para textos de outras pessoas.
- 🟡 em "Editar rascunho" vale enquanto o texto está em revisão com a pessoa. O revisor não mexe nos créditos nem duplica o texto; se achar erro, comenta.
- Contas, papéis, taxonomia e configurações ficam no Django Admin, liberado só para o papel `admin`.
- A matriz é testada célula a célula em `backend/apps/editorial/tests/test_matrix.py`, que copia esta tabela e falha se as duas divergirem. Linhas de recursos futuros (reações, comentários públicos, busca, pautas, fontes) aparecem lá como fora do escopo até a etapa delas.

## Política editorial

Configuração `editorial.self_publish`:

| Valor | Efeito |
|---|---|
| `staff` (**decidido**) | Cada membro da equipe publica as próprias publicações. Revisão por colega é opcional. Editores podem intervir depois. |
| `never` (reservado) | Toda publicação precisa de aprovação de outro membro. Existe para uma escola mais restritiva ou para um período de adaptação; não é o padrão. |

Em qualquer valor: **alunos não têm conta e nunca publicam**; o professor responde pelo texto que publica com o aluno creditado.

## Como isso vira código

- Campo `role` em `User` com choices `staff | editor | admin`; campo `staff_kind` para exibição.
- Funções puras em `apps/editorial/permissions.py`: `can_edit(user, article)`, `can_publish(user, article)`, `can_moderate_comment(user, comment)` etc. Uma implementação, usada por views, services, templates e testes.
- Nos templates, a tag `{% load permissions %}{% can "publish" article as pode_publicar %}` chama `can_publish`; ações sem objeto dispensam o segundo argumento (`{% can "access_admin" as mostra_admin %}`). Nenhum template ou view testa `role` ou `is_staff` diretamente.
- Regras que dependem de revisão consultam `ArticleContributor` com `role = reviewer`.
- Sem sistema genérico de permissões por objeto.

## Histórico

- 2026-09-12: versão inicial.
- 2026-09-12: alunos sem conta; papéis reduzidos a equipe, editor e admin; cargo para exibição; autopublicação como padrão; comentários públicos moderados. Conforme respostas em [27](27-decisoes-pendentes-e-perguntas.md).
- 2026-09-14: E30: notas da matriz (ninguém revisa o próprio texto, alcance do revisor, Django Admin), tag `{% can %}` e teste célula a célula.
