# 26 — Plano de desenvolvimento incremental

## Método

Cada etapa segue o ciclo: **definir → explicar a decisão → implementar → testar → revisar → avançar**. Uma etapa cabe em uma ou duas sessões e termina com algo verificável. Nenhuma etapa começa com a anterior aberta.

Para cada etapa: objetivo, documentos de referência, entregável, critério de aceite. Etapas de uma fase podem ser reordenadas; fases não.

Convenção de commits: um commit por etapa, mensagem `E07: taxonomia e seed`. Ao fechar uma fase, `make release` cria a versão ([30](30-versionamento.md)).

## Fase 0 — Fundação (→ v0.1.0)

| # | Etapa | Referência | Entregável | Aceite |
|---|---|---|---|---|
| E01 | Estrutura do repositório, `pyproject.toml`, `uv`, ruff, djlint, pre-commit, `.editorconfig`, `Makefile`, `VERSION` = `0.0.1`, `CHANGELOG.md` | [08](08-estrutura-do-repositorio.md), [30](30-versionamento.md) | Árvore criada | `make lint` passa |
| E02 | Projeto Django com settings por ambiente, `django-environ`, `.env.example`, PostgreSQL no Compose de dev, `/healthz/` com versão | [24](24-infraestrutura-e-deploy.md) | `make dev` sobe | `/healthz/` devolve `{"status":"ok","version":"0.0.1"}` |
| E03 | Usuário customizado com `email`, `role`, `staff_kind` (só o modelo) | [06](06-modelo-de-dados.md) | Migração inicial | `createsuperuser` com e-mail |
| E04 | Vite + Tailwind 4 + HTMX + Alpine via `django-vite`; tokens; marca "Jornal Escolar" (wordmark e glifo); `base.html`, `layouts/public.html`, masthead, rodapé com crédito de desenvolvimento e versão | [09](09-design-system.md) | Página inicial provisória | Fontes locais; responsiva; rodapé sem nome da escola |
| E05 | factory-boy; GitHub Actions (pytest e pytest-django já entraram na E02 junto com os primeiros testes) | [24](24-infraestrutura-e-deploy.md) | CI verde | |
| E06 | `CLAUDE.md`, `README.md`; Cloudflare Tunnel apontando para a página provisória; app registrado na Microsoft seguindo o guia | [24](24-infraestrutura-e-deploy.md), [32](32-guia-login-microsoft.md) | Site "em breve" no ar | `https://jornal.projetosrosa.com.br` responde |
| E06b | (não técnica) Termo de autorização de nome e imagem redigido com a direção | [23](23-seguranca-e-lgpd.md) | Documento | Aprovado pela direção |

**Release:** `v0.1.0`.

## Fase 1 — MVP (→ v1.0.0)

| # | Etapa | Referência | Entregável | Aceite |
|---|---|---|---|---|
| E07 | Taxonomia: `KnowledgeArea`, `Discipline`, `Topic`, `ArticleType`; admin; `seed_taxonomy` com as áreas e disciplinas da escola | [06](06-modelo-de-dados.md), [18](18-painel-administrativo.md) | Modelos + seed | Seed idempotente; admin edita tudo |
| E08 | `SiteSetting` com cache; `StaticPage` (texto simples por ora) | [06](06-modelo-de-dados.md) | Modelos | `site.name` no masthead |
| E09 | Login Microsoft via `django-allauth` restrito a domínios e contas pré-cadastradas; login por senha; rate limit; layout `auth.html`; **teste com conta real de professor** | [23](23-seguranca-e-lgpd.md) | Telas | Conta cadastrada entra; não cadastrada é recusada |
| E10 | `AccessLink` (link de primeiro acesso / redefinição gerado pelo admin); `TeacherProfile`; ação no admin "gerar link" | [14](14-configuracao-de-perfil.md) | Fluxo | Link expira em 7 dias e é de uso único |
| E11 | `MediaAsset`: upload, magic bytes, EXIF, variantes WebP, `/x/media/` | [16](16-editor-de-publicacoes.md), [23](23-seguranca-e-lgpd.md) | Serviço + endpoint | Arquivo falso rejeitado; 3 variantes |
| E12 | `Article`, `ArticleContributor` (com `is_student`, `class_group`, `consent_ok`), `ArticleRevision`; estados `draft`, `published`, `archived`; services; `permissions.py` inicial | [04](04-fluxo-editorial.md), [06](06-modelo-de-dados.md) | Modelos + testes | Staff publica o próprio; não publica alheio; editor publica qualquer |
| E13 | Renderizador ProseMirror JSON → HTML + texto; sanitização; tempo de leitura | [16](16-editor-de-publicacoes.md) | `rendering.py` + testes | Nó desconhecido ignorado; `javascript:` descartado |
| E14 | Editor TipTap: bundle, extensões, toolbar, autosave, indicador | [16](16-editor-de-publicacoes.md) | Tela | Texto persiste após recarregar |
| E15 | Editor: metadados, créditos (equipe por autocomplete; aluno com turma, política de nome e `consent_ok`; sem conta), fontes, evento, checklist | [16](16-editor-de-publicacoes.md) | Tela completa | Checklist bloqueia aluno sem consentimento |
| E16 | Editor: imagens (toolbar, arrastar, colar); diálogo alt/legenda/crédito/pessoas/consentimento | [16](16-editor-de-publicacoes.md) | | Imagem com `srcset` na pré-visualização |
| E17 | `Notification` e sino no painel; notificações de publicação/edição por terceiro | [04](04-fluxo-editorial.md) | | Editor edita texto alheio, autor vê aviso |
| E18 | Página de publicação pública; pré-visualização; 404/410 | [11](11-pagina-publicacao.md) | Template | Lighthouse acessibilidade ≥ 95 |
| E19 | Componentes: `card` (4 variantes), `byline`, `tag`, `status-badge`, `empty-state`, `pagination`, `toast`; página `/dev/components/` | [09](09-design-system.md) | Templates | Demonstração renderiza todos |
| E20 | Home | [10](10-pagina-inicial.md) | | Com seed tudo aparece; sem dados, estado vazio |
| E21 | Lista com filtros básicos (GET), área, disciplina, tipo, agenda | [12](12-paginas-de-navegacao.md) | | Filtros sem JS |
| E22 | Perfil público e "Quem escreve" (toda a equipe, com cargo) | [13](13-perfil-publico-professor.md) | | Abas corretas |
| E23 | Configuração de perfil, assistente de primeiro acesso, conta | [14](14-configuracao-de-perfil.md) | | e2e do assistente |
| E24 | Painel: início com pendências e notificações, minhas publicações, menu | [15](15-painel-professor.md) | | Pendências corretas com seed |
| E25 | Destaques da home (tela do editor) e páginas estáticas com o editor | [18](18-painel-administrativo.md) | | Reordenar reflete na home |
| E26 | SEO: meta, Open Graph, JSON-LD, sitemap, robots; compartilhar | [11](11-pagina-publicacao.md) | | Validador sem erro |
| E27 | Dockerfile multi-arch, Compose de produção com `cloudflared` e Caddy, backup para Cloudflare R2, restore, UptimeRobot | [24](24-infraestrutura-e-deploy.md), [31](31-guia-backup.md) | Deploy | Site no ar; restore testado |
| E28 | Seed realista; revisão visual celular/desktop; checklist de segurança; página de privacidade | [23](23-seguranca-e-lgpd.md) | | Checklist completa |

**Marco e release:** convidar 3 colegas, publicar 5 publicações reais → `v1.0.0`.

## Fase 2 — Revisão opcional, moderação e conta (→ v1.1.0)

| # | Etapa | Referência | Aceite |
|---|---|---|---|
| E29 | Estados `in_review`, `changes_requested`; pedir revisão com "pode publicar por mim"; `EditorialEvent` completo | [04](04-fluxo-editorial.md) | Testes de todas as transições |
| E30 | `permissions.py` completo (revisor designado); template tag; testes da matriz | [02](02-personas-papeis-permissoes.md) | Cada célula testada |
| E31 | Tela de revisão: leitura, decisão, histórico; aba "Revisões pedidas a mim" | [17](17-tela-de-revisao.md) | Sugerir alterações sem comentário é bloqueado |
| E32 | Comentários editoriais ancorados e gerais; resolver | [17](17-tela-de-revisao.md) | Âncora sobrevive a edição de outro trecho |
| E33 | Painel editorial: visão geral, todas as publicações, alertas | [18](18-painel-administrativo.md) | Alertas aparecem |
| E34 | `AuditLog`; exportar e anonimizar usuário; "Conta" completa | [23](23-seguranca-e-lgpd.md) | Anonimizar mantém crédito genérico |

## Fase 3 — Busca e interação (→ v1.2.0)

| # | Etapa | Referência | Aceite |
|---|---|---|---|
| E35 | `unaccent`, `pg_trgm`, `pt_unaccent`; `search_vector`; reindexação | [19](19-busca-e-filtros.md) | "fisica" encontra "Física" |
| E36 | Página de busca com grupos, trechos, fallback por trigramas | [19](19-busca-e-filtros.md) | |
| E37 | Filtros completos via HTMX com `hx-push-url`; ordenação; cache | [12](12-paginas-de-navegacao.md) | URL reproduz o filtro |
| E38 | Reações: modelo, endpoint, barra, cookie, rate limit | [20](20-reacoes-leituras-comentarios.md) | 31ª reação/min bloqueada |
| E39 | Leituras: beacon, regra tempo + rolagem, unicidade diária, exibição | [20](20-reacoes-leituras-comentarios.md) | Recarregar 5 vezes conta 1 |
| E40 | Comentários públicos: modelo, formulário com honeypot e limites, remoção de links, exibição dos aprovados, resposta do autor | [20](20-reacoes-leituras-comentarios.md) | Comentário novo é invisível ao público |
| E41 | Fila de moderação no painel; aprovar em lote; notificações; `comments_enabled` por publicação | [20](20-reacoes-leituras-comentarios.md) | Editor vê todos os pendentes |
| E42 | Clima "Hoje na escola" com Open-Meteo e cache | [29](29-clima.md) | Widget some se a API falhar |
| E43 | "Leia também"; feed RSS; página de tópico | [11](11-pagina-publicacao.md) | Feed valida |

## Fase 4 — Curadoria (→ v1.3.0)

| # | Etapa | Referência | Aceite |
|---|---|---|---|
| E44 | Procrastinate: worker, tarefa de teste, limpezas periódicas | [24](24-infraestrutura-e-deploy.md) | Tarefa roda no horário |
| E45 | `NewsSource`, `NewsItem`; admin com "Buscar agora"; coleta, normalização, canonicalização | [21](21-curadoria-de-noticias.md) | 5 fontes reais sem erro |
| E46 | Deduplicação por URL e título; retenção | [21](21-curadoria-de-noticias.md) | Item em duas fontes gera 1 registro |
| E47 | Classificação por fonte e palavras-chave; `keywords` no admin | [21](21-curadoria-de-noticias.md) | 100 itens classificados |
| E48 | Recomendação; tela de sugestões com ações; fontes em inglês por preferência | [21](21-curadoria-de-noticias.md) | Ignorar reduz sugestões do tópico |
| E49 | `StoryIdea`: quadro, criação, conversão em rascunho | [15](15-painel-professor.md) | Rascunho nasce com fonte |

## Fase 5 — IA (congelada)

Etapas E50 a E55 permanecem descritas na versão anterior deste documento (histórico do git) e em [22](22-ia.md). Não serão detalhadas nem executadas até decisão do dono do projeto.

## Como o assistente de código deve trabalhar em cada etapa

1. Ler o(s) documento(s) de referência da etapa.
2. Propor em poucas linhas o que será feito e por quê, citando a decisão do documento.
3. Implementar apenas o escopo da etapa.
4. Escrever ou atualizar testes; rodar `make test` e `make lint`.
5. Mostrar como verificar manualmente.
6. Se uma decisão do documento se mostrar errada na prática, **parar, propor a mudança no documento e só então continuar**.
7. Ao fechar uma fase, atualizar `CHANGELOG.md` e criar a versão.

## Histórico

- 2026-09-12: versão inicial.
- 2026-09-12: pytest adiantado da E05 para a E02; na E03 o banco de desenvolvimento é recriado (o usuário customizado precisa existir antes das migrações de `auth`).
- 2026-09-12: reescrito: sem contas de aluno, login Microsoft, notificações no painel na Fase 1, comentários e clima na Fase 3, IA congelada, releases por fase.
- 2026-09-12: E06b: o dono pediu que o projeto redija o modelo do termo ([33](33-termo-de-autorizacao.md)); falta só a aprovação da direção. E06 parte 2 (túnel e registro Microsoft) adiada por decisão do dono: até lá a equipe entra por senha com link de acesso, e o túnel entra junto com o deploy na E27. A ordem das demais etapas não muda.
- 2026-09-14: E27 feita até onde dá sem servidor e sem contas: imagens multi-arch, Compose de produção, Caddy, backup e restore testados localmente com destino em pasta. "Site no ar", túnel (E06 parte 2), R2 e UptimeRobot ficam com o dono, seguindo o guia [34](34-guia-deploy.md).
