# 16 — Editor de publicações

Rotas: `/painel/publicacoes/nova/` e `/painel/publicacoes/<id>/editar/` · Camada: **MVP** · Fase 1

## Objetivo

Escrever deve ser tão fácil quanto no Google Docs, com o mínimo de campos obrigatórios visíveis. Metadados ficam em um painel lateral que pode ser ignorado até a hora de enviar.

## Decisão técnica

TipTap 3 em modo vanilla ([D4](05-arquitetura-tecnica.md)). Conteúdo armazenado como JSON ProseMirror, renderizado no servidor para HTML e texto.

## Extensões habilitadas

| Extensão | Nó/marca | Notas |
|---|---|---|
| Document, Paragraph, Text | base | |
| Heading | `h2`, `h3` apenas | `h1` é o título da publicação |
| Bold, Italic, Underline (não), Strike (não) | | Sublinhado confunde com link; tachado não tem uso editorial |
| Link | | Só `http(s)` e `mailto`; abre em nova aba se externo; sem `javascript:` |
| BulletList, OrderedList, ListItem | | |
| Blockquote | | Com atributo opcional `cite` (autor da citação) |
| HorizontalRule | | |
| Image (custom) | `figure` com `img` + `figcaption` | Atributos: `assetId`, `alt`, `caption`, `credit`, `size` (`normal`/`wide`) |
| Youtube (Evolução) | | Só ID do vídeo, nunca iframe livre |
| Placeholder | | "Comece a escrever…" |
| CharacterCount | | Para tempo de leitura ao vivo |
| History | | Desfazer/refazer |
| Typography | | Aspas curvas, travessões |
| Table | Não | Sem tabelas no MVP; complexidade em celular |

Não há colagem de HTML arbitrário: o TipTap converte o que foi colado em nós do esquema e descarta o resto.

## Layout

```
┌──────────────────────────────────────────────────────────────┐
│ ← Voltar   [Rascunho]  Salvo às 14:32   [Pré-visualizar] [Enviar para revisão ▾] │
├────────────────────────────────────────────┬─────────────────┤
│                                            │ METADADOS       │
│  Título (campo grande, sem borda)          │ Tipo ▾          │
│  Linha fina (campo menor)                  │ Disciplinas     │
│                                            │  [Física ×] [+] │
│  [Toolbar: ¶ H2 H3 | B I | 🔗 | • 1. | ❝ | 🖼 | — | ↶ ↷] │ Tópicos [+]     │
│                                            │ Capa            │
│  Corpo do texto                            │  [imagem] [alt] │
│  ...                                       │ Créditos        │
│                                            │  Carla (autora) │
│                                            │  Rafael (autor) │
│                                            │  [+ adicionar]  │
│                                            │ Fontes          │
│                                            │  [+ adicionar]  │
│                                            │ Evento (se tipo)│
│                                            │  data, local    │
│                                            ├─────────────────┤
│                                            │ CHECKLIST       │
│                                            │ ✓ Título        │
│                                            │ ✗ Disciplina    │
│                                            │ ! Capa sem alt  │
└────────────────────────────────────────────┴─────────────────┘
```

No celular: metadados viram uma folha inferior acessível por botão "Detalhes"; toolbar fixa no rodapé; título e corpo ocupam a tela.

## Comportamentos

### Autosave

- A cada 2 segundos sem digitar, ou a cada 30 segundos, `PUT /x/articles/<id>/body/` com `title`, `subtitle`, `body_json`.
- Servidor: valida JSON contra o esquema (nós e marcas permitidos), renderiza `body_html` e `body_text`, calcula `reading_minutes`, salva, devolve `{saved_at}`.
- Indicador "Salvo às 14:32" / "Salvando…" / "Falha ao salvar — tentando de novo" com nova tentativa exponencial. Se offline, guarda no `localStorage` e reenvia.
- Conflito: se outro editor salvou depois (comparação de `updated_at`), mostra aviso "Este texto foi alterado por outra pessoa. Recarregue para ver as mudanças." Sem edição simultânea no MVP.

### Nova publicação

- `POST /painel/publicacoes/nova/` cria um `Article` em `draft` com título "Sem título" e redireciona ao editor. Isso garante um `id` para autosave e uploads desde o primeiro segundo.
- Rascunhos "Sem título" sem corpo e sem edição há 7 dias são apagados por tarefa de limpeza (Fase 4) ou comando manual.

### Upload de imagens

- Botão na toolbar, arrastar e soltar, ou colar da área de transferência.
- `POST /x/media/` (multipart) com o arquivo e `article_id`. Servidor: valida tipo real (magic bytes) e tamanho (10 MB), remove EXIF, gera variantes WebP 480/960/1600, cria `MediaAsset`, devolve `{id, url, variants, width, height}`.
- O nó `figure` recebe `assetId` e URL da variante 960. Ao renderizar, o servidor gera `srcset`.
- Após inserir, um pequeno diálogo pede `alt` (obrigatório ou "decorativa"), legenda e crédito; `has_people` e `consent_ok` como checkboxes.
- Progresso de upload e erro visível no lugar da imagem.

### Créditos

- **Equipe**: autocomplete por nome (`/x/users/search/`) entre contas ativas. Papel: autor, coautor, colaborador (com nota), revisor, editor.
- **Aluno**: botão "Creditar aluno" abre campos: nome (com ajuda "primeiro nome e inicial, ex.: Rafael S."; validado conforme `credits.student_name_policy`), turma (ex.: "2ª série B"), papel (autor, coautor, colaborador) e a caixa obrigatória "Tenho autorização do responsável para publicar o nome deste aluno". Sem a caixa, a checklist bloqueia.
- **Outros sem conta**: nome livre e papel (turma inteira, convidado, Grêmio).
- Criador aparece como autor por padrão e pode ser rebaixado a coautor, mas não removido enquanto for o único autor da equipe. Toda publicação precisa de ao menos um membro da equipe como autor ou coautor: é quem responde por ela.

### Fontes

- Lista de (título, URL, veículo). Pré-preenchida quando a publicação nasce de uma sugestão (Fase 4).
- URLs validadas; título obrigatório.

### Pré-visualizar

- Abre `/publicacoes/<slug-ou-id>/` em nova aba com a faixa "Pré-visualização". Mesmo template da página final.

### Publicar e pedir revisão

- Botão principal muda conforme o estado:
  - `draft`: **"Publicar"**, com menu secundário "Pedir revisão a um colega" (abre seletor de colega, nota e a opção "pode publicar por mim").
  - `changes_requested`: "Publicar" e "Reenviar para revisão".
  - `in_review` (autor): "Em revisão com Marcos" com opção "Cancelar pedido"; edição continua permitida e o revisor é avisado.
  - `published`: "Salvar alterações" (registra `edited_after_publish`).
- Com a política `never` (reservada), "Publicar" só aparece para editores e o botão principal é "Pedir revisão".
- Checklist bloqueia a publicação se houver itens obrigatórios pendentes ([04](04-fluxo-editorial.md)).
- Ao lado do título, um toggle "Comentários abertos" (padrão ligado, Fase 3).

## Renderizador servidor (JSON → HTML)

Módulo `apps/publications/rendering.py`:

- Percorre o documento recursivamente. Cada tipo de nó tem uma função; nós desconhecidos são ignorados (não emitidos) e registrados em log.
- Marcas mapeadas: `bold` → `<strong>`, `italic` → `<em>`, `link` → `<a href rel target>` com URL validada.
- `figure` consulta `MediaAsset` para gerar `img` com `srcset`, `alt`, `width/height` (evita layout shift) e `figcaption` com legenda e crédito.
- Saída passa por `bleach`/`nh3` como segunda barreira, com lista fechada de tags e atributos.
- Também gera `body_text` (concatenação de texto com quebras) e conta palavras (200 por minuto para tempo de leitura).

## Testes obrigatórios

- Documento com nó desconhecido não emite HTML para ele.
- Link `javascript:` é descartado.
- Imagem sem `assetId` válido não é renderizada.
- Autosave por usuário sem permissão retorna 403.
- Upload de arquivo com extensão de imagem mas conteúdo executável é rejeitado.

## Fora do MVP

- Tabelas, vídeos, embeds, notas de rodapé, comentários inline no editor (comentários ficam na tela de revisão, ancorados por trecho), edição colaborativa em tempo real, importação de .docx.

## Implementação (E14 e E15)

- Conflito: o autosave envia o `updated_at` que o editor conhece; o servidor só recusa (409) se **outra pessoa** salvou depois (`Article.last_edited_by`). Salvamentos da própria pessoa, como texto e metadados em paralelo, não geram conflito. O painel lateral devolve o novo `updated_at` no cabeçalho `HX-Trigger` (`articleUpdated`).
- Versões de texto publicado: salvamentos seguidos da mesma pessoa em até 15 minutos atualizam a mesma `ArticleRevision` (`edited_after_publish`), em vez de criar uma por autosave.
- Painel lateral em HTMX: metadados salvam sozinhos a cada mudança (`/x/articles/<id>/meta/`); a checklist se atualiza depois de cada autosave; "Publicar" salva o texto pendente antes de enviar e fica desativado enquanto houver item obrigatório.
- Créditos: colega por busca (`/x/users/search/`), aluno (nome validado pela política, turma, autorização e opção de nome completo autorizado) e outros sem conta. A pessoa responsável da equipe (autor ou coautor) não pode ser removida se for a única.
- Imagens no corpo e capa ficam para a E16.

## Implementação (E29)

- "Pedir revisão" abre uma caixa com a lista de colegas (sem quem assina o texto), nota e "pode publicar por mim", marcado conforme a preferência do perfil. Em `changes_requested` o botão vira "Reenviar para revisão", com o último revisor já escolhido. O menu secundário virou um botão ao lado de "Publicar".
- Em `in_review` o autor vê "Em revisão com X" e "Cancelar pedido"; o revisor designado (ou editor) vê "Revisar", com comentário, "Sugerir alterações", "Aprovar e devolver aos autores", "Aprovar e publicar" (quando permitido) e "Não posso revisar". Depois de decidir, quem não pode mais editar volta ao painel. A tela de revisão completa é da E31.
- O painel lateral ganhou a seção "Revisão": com quem está, nota do pedido, alterações sugeridas (com "Voltar a rascunho") e o selo "Revisado por X".
- No celular, "Pedir revisão" e "Arquivar" saem da barra e ficam no fim da folha "Detalhes", porque a barra não comporta tantos botões em 390 px.

## Histórico

- 2026-09-12: versão inicial.
- 2026-09-12: créditos de aluno sem conta com autorização; botão "Publicar" como padrão; revisão opcional.
- 2026-09-14: E29: fluxo de revisão no editor (seção "Implementação (E29)").
- 2026-09-14: E31: no editor, "Revisar" virou um link para a tela de revisão ([17](17-tela-de-revisao.md)); a caixa com as decisões saiu do editor.
