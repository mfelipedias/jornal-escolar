# 07 — Rotas e API

## Abordagem

Como a aplicação é um monólito Django com renderização no servidor ([D1](05-arquitetura-tecnica.md)), a "API" tem três camadas:

1. **Rotas HTML públicas e autenticadas**: páginas completas.
2. **Endpoints internos**: chamados pelo HTMX (devolvem fragmentos HTML) ou pelo editor (devolvem JSON). Protegidos por sessão e CSRF. Não são API pública e podem mudar sem aviso.
3. **API pública somente leitura** (Evolução, Fase 6): JSON versionada em `/api/v1/`, com `django-ninja`, para integração com o site da escola ou um app futuro.

Convenção de nomes de URL no Django: `app:nome`, por exemplo `publications:detail`.

## 1. Rotas HTML

### Público

| Método | URL | Nome | Descrição | Fase |
|---|---|---|---|---|
| GET | `/` | `core:home` | Home | 1 |
| GET | `/publicacoes/` | `publications:list` | Lista com filtros (querystring: `area`, `disciplina`, `tipo`, `professor`, `de`, `ate`, `ordem`, `pagina`) | 1 (filtros completos na 3) |
| GET | `/publicacoes/<slug>/` | `publications:detail` | Página da publicação | 1 |
| GET | `/areas/<slug>/` | `taxonomy:area` | Página da área com suas disciplinas e publicações | 1 |
| GET | `/disciplinas/<slug>/` | `taxonomy:discipline` | Página da disciplina | 1 |
| GET | `/tipos/<slug>/` | `taxonomy:type` | Publicações de um tipo (ex.: `/tipos/eventos/`) | 1 |
| GET | `/topicos/<slug>/` | `taxonomy:topic` | Página do tópico | 3 |
| GET | `/agenda/` | `publications:agenda` | Eventos futuros e passados | 1 |
| GET | `/professores/` | `accounts:teacher_list` | "Quem escreve" | 1 |
| GET | `/professores/<slug>/` | `accounts:teacher_detail` | Perfil público | 1 |
| GET | `/busca/?q=` | `search:results` | Busca global | 3 |
| GET | `/sobre/`, `/privacidade/`, `/colaborar/` | `core:page` | Páginas estáticas editáveis | 1 |
| GET | `/feed.xml` | `publications:feed` | RSS do jornal | 3 |
| GET | `/sitemap.xml`, `/robots.txt` | | | 1 |

### Autenticação

| Método | URL | Nome | Descrição | Fase |
|---|---|---|---|---|
| GET/POST | `/entrar/` | `accounts:login` | Senha; botão "Entrar com a conta da escola" | 1 |
| GET | `/entrar/microsoft/` e callback | allauth | Login Microsoft | 1 |
| POST | `/sair/` | `accounts:logout` | | 1 |
| GET/POST | `/acesso/<uuid>/` | `accounts:access_link` | Primeiro acesso ou redefinição de senha por link gerado pelo admin | 1 |

### Painel (autenticado; prefixo `/painel/`)

| Método | URL | Nome | Quem | Fase |
|---|---|---|---|---|
| GET | `/painel/` | `dashboard:home` | todos logados | 1 |
| GET | `/painel/publicacoes/` | `dashboard:my_articles` | todos | 1 |
| GET/POST | `/painel/publicacoes/nova/` | `publications:create` | todos | 1 |
| GET | `/painel/publicacoes/<id>/editar/` | `publications:edit` | autores, revisor, editor+ | 1 |
| GET | `/painel/publicacoes/<id>/revisar/` | `editorial:review` | revisor, editor+ | 2 |
| GET | `/painel/revisao/` | `editorial:queue` | todos | 2 |
| GET | `/painel/comentarios/` | `engagement:moderation` | todos | 3 |
| GET | `/painel/notificacoes/` | `editorial:notifications` | todos | 1 |
| GET | `/painel/sugestoes/` | `curation:suggestions` | todos | 4 |
| GET | `/painel/pautas/` | `curation:story_ideas` | todos | 4 |
| GET/POST | `/painel/perfil/` | `accounts:profile_edit` | todos | 1 |
| GET/POST | `/painel/conta/` | `accounts:account_settings` | todos (senha, sessões) | 1 |
| GET/POST | `/painel/primeiro-acesso/<passo>/` | `accounts:onboarding` | todos (assistente, passos 1 a 3) | 1 |
| GET | `/painel/primeiro-acesso/concluir/` | `accounts:onboarding_done` | todos (fim do assistente ou "fazer isso depois") | 1 |
| GET | `/painel/editorial/` | `editorial:overview` | editor+ (tudo por estado, destaques, comentários) | 2 |

### Administração

| URL | Descrição | Fase |
|---|---|---|
| `/admin/` | Django Admin: usuários, taxonomia, tipos, configurações, páginas estáticas, fontes, auditoria | 1 |

Telas administrativas customizadas ficam dentro de `/painel/editorial/` (editores) e `/admin/` (admin). Ver [18](18-painel-administrativo.md).

## 2. Endpoints internos (HTMX e JSON)

Prefixo `/x/` para deixar explícito que são internos. Todos exigem CSRF; os de escrita exigem login, salvo reações e leituras.

### Publicações e editor

| Método | URL | Resposta | Descrição | Fase |
|---|---|---|---|---|
| PUT | `/x/articles/<id>/body/` | JSON `{saved_at, revision}` | Autosave do editor: recebe `body_json`, `title`, `subtitle`; servidor renderiza HTML e texto | 1 |
| POST | `/x/articles/<id>/meta/` | fragmento | Atualiza tipo, disciplinas, tópicos, capa, fontes, evento | 1 |
| POST | `/x/articles/<id>/contributors/` | fragmento | Adiciona contribuição | 1 |
| DELETE | `/x/articles/<id>/contributors/<cid>/` | fragmento | Remove | 1 |
| POST | `/x/articles/<id>/transition/<action>/` | fragmento ou redirect | `publish`, `archive`, `restore`, `reopen` (Fase 1; campo opcional `next` com endereço interno para onde voltar); `request_review`, `cancel_review`, `request_changes`, `approve`, `approve_publish`, `decline_review` (Fase 2) | 1 e 2 |
| POST | `/x/articles/<id>/duplicate/` | redirect | Duplicar como rascunho (cópia das imagens incluída) e abrir o editor | 1 |
| POST | `/x/articles/<id>/comments-toggle/` | fragmento | Abre/fecha comentários | 3 |
| POST | `/x/articles/<id>/feature/` | fragmento | Marca/desmarca destaque (editor+) | 1 |
| POST | `/x/media/` | JSON `{id, url, variants, width, height}` | Upload de imagem (multipart) | 1 |
| PATCH | `/x/media/<id>/` | JSON | alt, crédito, licença, consentimento | 1 |
| GET | `/x/users/search/?q=` | JSON | Autocomplete de usuários para créditos e revisores | 1 |
| GET | `/x/articles/<id>/checklist/` | fragmento | Checklist de publicação | 1 |

### Editorial

| Método | URL | Resposta | Fase |
|---|---|---|---|
| POST | `/x/articles/<id>/editorial-comments/` | fragmento (lista) | 2 |
| POST | `/x/editorial-comments/<id>/resolve/` | fragmento | 2 |
| POST | `/x/notifications/read-all/` | fragmento (sino) | 1 |
| GET | `/x/notifications/` | fragmento (lista suspensa) | 1 |

### Descoberta

| Método | URL | Resposta | Fase |
|---|---|---|---|
| GET | `/x/articles/?filtros` | fragmento (grade de cards + paginação) | 3 |
| GET | `/x/search/suggest/?q=` | fragmento | 6 |

### Engajamento

| Método | URL | Resposta | Fase |
|---|---|---|---|
| POST | `/x/articles/<id>/react/` | fragmento (barra de reações) | 3 |
| POST | `/x/articles/<id>/read/` | 204 | Beacon de leitura | 3 |
| POST | `/x/articles/<id>/comments/` | fragmento (confirmação) | Novo comentário público, entra pendente | 3 |
| POST | `/x/comments/<id>/<action>/` | fragmento | `approve`, `reject`, `reply`, `rename`; em lote via `/x/comments/bulk/` | 3 |

### Curadoria

| Método | URL | Resposta | Fase |
|---|---|---|---|
| POST | `/x/news/<id>/<action>/` | fragmento | `ignore`, `save`, `interesting`, `to-idea` | 4 |
| POST | `/x/ideas/<id>/to-article/` | redirect ao editor | 4 |

### IA (Fase 5, congelada)

`/x/ai/articles/<id>/suggest-titles/`, `/review-hints/`, `/suggest-questions/` conforme [22](22-ia.md). Não implementar.

## 3. API pública somente leitura (Fase 6)

Só se houver consumidor concreto. Esboço:

| Método | URL |
|---|---|
| GET | `/api/v1/articles/?area=&discipline=&type=&page=` |
| GET | `/api/v1/articles/{slug}/` |
| GET | `/api/v1/areas/`, `/api/v1/disciplines/`, `/api/v1/types/` |
| GET | `/api/v1/teachers/`, `/api/v1/teachers/{slug}/` |
| GET | `/api/v1/search/?q=` |

Sem endpoints de escrita. Sem dados de alunos além do nome de exibição já público. Autenticação por chave de API simples, com limite de requisições.

## Convenções de resposta

- Fragmentos HTMX: template em `templates/<app>/partials/`. A view detecta `request.htmx` (biblioteca `django-htmx`) e devolve o fragmento; sem HTMX, devolve a página completa. Isso mantém tudo funcionando sem JavaScript.
- JSON: apenas onde o cliente é JavaScript próprio (editor, upload). Erros em `{"error": {"code": "...", "message": "..."}}` com status HTTP adequado.
- Rate limit com `django-ratelimit`: reações, leituras e comentários por IP; login por IP e por e-mail; upload por usuário.
- Toda resposta traz o cabeçalho `X-App-Version` ([30](30-versionamento.md)).

## Histórico

- 2026-09-12: versão inicial.
- 2026-09-12: login Microsoft e links de acesso no lugar de convites; notificações; comentários públicos; transições revisadas; IA congelada.
- 2026-09-14: E23: rotas do assistente de primeiro acesso.
- 2026-09-14: E24: `/x/articles/<id>/duplicate/` e `next` nas transições.
- 2026-09-14: E25: `/painel/destaques/` (`editorial:featured`), `/x/featured/search/`, `/x/articles/<id>/feature/` com `acao` (`adicionar`, `remover`, `subir`, `descer`), `/painel/paginas/` (`core:page_list`), `/painel/paginas/<slug>/editar/`, `/painel/paginas/<slug>/publicar/` e `PUT /x/pages/<slug>/body/`.
- 2026-09-14: E36: `/busca/` (`search:results`) implementada; aceita `q`, `area`, `disciplina`, `tipo` e `pagina`.
