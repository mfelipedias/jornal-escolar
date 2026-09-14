# 23 — Segurança e LGPD

Não é aconselhamento jurídico. É o conjunto de decisões de arquitetura e produto que reduzem risco e facilitam conformidade. A escola deve validar o termo de autorização e a política de privacidade com quem responde por isso (direção e, se houver, a Diretoria de Ensino).

## Minimização de dados

| Pessoa | O que guardamos | O que não guardamos |
|---|---|---|
| Leitor | Cookie anônimo aleatório; logs de acesso com IP por até 14 dias; para comentários, nome informado e hash do IP | Conta, e-mail, histórico de leitura identificável |
| Aluno creditado | Nome de exibição (conforme política) e turma, dentro do crédito da publicação; marcação de que o professor tem autorização | Conta, e-mail, data de nascimento, documento, contato do responsável (fica no termo em papel, fora do sistema) |
| Equipe | E-mail institucional, nome, cargo, foto, bio, formação, disciplinas, interesses, links | Telefone, documentos, endereço |
| Todos com conta | Hash de senha (se usar senha), último login, eventos editoriais, auditoria | Senha em claro, tokens permanentes |

## Alunos: crédito e imagem

Alunos não têm conta. Aparecem no jornal de duas formas: creditados em publicações e em fotos. A escola **não tem hoje termo de autorização de uso de nome e imagem**. Isso precisa existir antes da primeira publicação com aluno.

Recomendação (tarefa não técnica da Fase 0, com a direção):

1. Redigir um **termo de autorização** simples, assinado pelo responsável (ou pelo próprio aluno se maior de 18), autorizando: (a) publicação do nome no jornal da escola, com opção "apenas primeiro nome e inicial", e (b) uso de imagem em fotos do jornal. Validade por ano letivo, revogável. Guardado pela secretaria. Modelo em [33](33-termo-de-autorizacao.md).
2. O sistema registra apenas: `consent_ok` no crédito e na foto (declaração do professor de que o termo existe) e, opcionalmente, um número de referência do termo.

Regras no sistema:

- Política `credits.student_name_policy` (padrão `first_initial`): ao marcar um crédito como aluno, o campo de nome recebe ajuda "Use primeiro nome e inicial do sobrenome, ex.: Rafael S." e o sistema valida o formato quando a política é `first_initial`. Nome completo só com política `full` (definida pelo admin) ou marcação explícita do professor.
- Crédito de aluno sem `consent_ok` bloqueia a publicação (checklist).
- Foto com `has_people` sem `consent_ok` bloqueia a publicação.
- Sem página de aluno, sem lista de alunos, sem busca por aluno. O nome do aluno aparece apenas no crédito da publicação e é indexável junto com ela; se a família pedir, o admin edita o crédito (anonimiza para "aluno da 2ª série") sem despublicar.
- Comentários públicos: quem comenta informa um nome; o formulário pede "só o primeiro nome"; o moderador pode reduzir o nome antes de aprovar. Ver [20](20-reacoes-leituras-comentarios.md).

## Direitos dos titulares

| Direito | Como o sistema atende |
|---|---|
| Acesso | `export_user_data` gera JSON com tudo de um usuário da equipe; disponível em "Conta" (Fase 2) |
| Correção | Edição de perfil; crédito de aluno editado pelo professor ou admin |
| Exclusão/anonimização | `anonymize_user` para equipe; para aluno, edição do crédito; para comentário, exclusão pelo moderador |
| Revogação de autorização | Admin ou professor edita o crédito e remove/troca a foto; registrado em `EditorialEvent` |
| Informação | Página "Privacidade" editável: dados, cookies, comentários, contato (`marcossilva06@professor.educacao.sp.gov.br`, também no rodapé) |

## Autenticação

### Microsoft (padrão)

- `django-allauth` com o provedor Microsoft (Entra ID), tenant `organizations`.
- O aplicativo é registrado em uma conta Microsoft gratuita do dono do projeto como **multi-tenant**; usuários da organização `educacao.sp.gov.br` podem entrar se a política daquela organização permitir aplicativos externos. **Risco:** a Secretaria pode bloquear. Testar com uma conta real na etapa E09 antes de depender disso. Explicação e passo a passo em [32](32-guia-login-microsoft.md).
- Só e-mails de domínios permitidos (`AUTH_ALLOWED_DOMAINS`, inicialmente `professor.educacao.sp.gov.br` e `educacao.sp.gov.br`) e **previamente cadastrados** pelo admin entram. Sem cadastro automático.
- Nenhum dado além de e-mail e nome é lido da Microsoft.

### Senha (reserva)

- Para quem não conseguir usar a conta Microsoft ou para o admin.
- Ativação por "link de primeiro acesso" gerado pelo admin (token de uso único, 7 dias), entregue por qualquer canal.
- Reset de senha: sem e-mail, o admin gera um novo link. Não existe "esqueci minha senha" automático.
- Validadores do Django (mínimo 10 caracteres, não comum, não similar ao e-mail). Hash Argon2.
- Limite de tentativas: 5 erros por 15 min por e-mail e 30 por 15 min por IP. **Ajuste da E09:** o limite por IP era 5, mas a escola inteira sai pela mesma conexão; 5 erros de uma pessoa bloqueariam todos os professores. Em produção, `TRUSTED_CLIENT_IP_HEADER=CF-Connecting-IP` faz o limite usar o IP real atrás da Cloudflare.
- Login Microsoft identifica a pessoa pelo `userPrincipalName`, nunca pelo campo `mail`: em aplicativos multi-tenant, o `mail` pode ser preenchido pelo administrador de qualquer organização Microsoft e permitiria se passar por um professor cadastrado. Contas convidadas (`#EXT#`) são recusadas.
- As telas de cadastro, recuperação de senha por e-mail e gestão de e-mails do allauth respondem 404. O `/admin/login/` redireciona para `/entrar/`, que tem o limite de tentativas.

### Sessões

Cookies `Secure`, `HttpOnly`, `SameSite=Lax`; expiração em 14 dias de inatividade; "sair de todas as sessões". 2FA TOTP para admin via `django-otp` (Evolução).

## Autorização

- Regras em `apps/editorial/permissions.py`; views usam decorador; templates usam template tag com as mesmas funções.
- Objetos buscados com filtro de permissão (`selectors.articles_for(user)`).
- Django Admin só para `admin`.

## Proteções web

- CSRF em todos os POST (HTMX envia token por cabeçalho).
- Cabeçalhos: CSP (scripts e estilos só do próprio domínio, com nonce; `frame-ancestors 'none'`; `img-src 'self' data:`), `X-Content-Type-Options`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy` mínima. HSTS na Cloudflare.
- HTML de publicações nunca vem do cliente; renderizado no servidor e sanitizado com `nh3`. Comentários são texto puro escapado; URLs removidas.
- Rate limit em login, upload, reações, leituras, comentários, busca.
- `DEBUG=False`, `ALLOWED_HOSTS` fechado, `SECRET_KEY` de ambiente.
- Atrás da Cloudflare: usar o IP real do cabeçalho `CF-Connecting-IP` só quando a requisição vier do túnel; Caddy configura `trusted_proxies`.

## Uploads

- Só imagens (JPEG, PNG, WebP). Verificação por magic bytes com Pillow; tamanho máximo 10 MB; dimensão máxima 6000px.
- Reescrita completa pelo Pillow (remove EXIF e metadados); variantes WebP.
- Nomes gerados (`<uuid>.<ext>`), caminho por ano/mês.
- Servidos de `/media/` com `Content-Type` correto e `nosniff`.
- Quota por usuário (1 GB) e limpeza de órfãos.
- Implementação (E11): `apps/publications/media.py`. A orientação da câmera é aplicada antes de descartar o EXIF. Arquivos truncados são recusados na decodificação completa. Limite de 60 envios por hora por pessoa com o limitador próprio `apps/core/ratelimit.py` (em vez de `django-ratelimit`). Apagar um `MediaAsset` apaga original e variantes.

## Auditoria

`AuditLog`: login, mudança de papel, criação/desativação/anonimização de usuário, geração de link de acesso, alteração de `SiteSetting`, exclusão de mídia, exportação de dados, moderação de comentário. IP como hash com sal mensal.

## Moderação

- Comentários: invisíveis até aprovação ([20](20-reacoes-leituras-comentarios.md)).
- Publicações: editor e admin despublicam em um clique; URL responde 410.
- "Reportar problema" na publicação (Evolução) abre formulário que cria uma notificação para editores; nada público.

## Backups e continuidade

Ver [24](24-infraestrutura-e-deploy.md). `pg_dump` diário + volume de mídia, criptografados, enviados para destino externo; restauração testada por trimestre.

## Checklist antes de ir ao ar

Revisada na E28. `[x]` = feito e verificado no código (teste automático quando possível); `[ ]` = depende do servidor real ou de uma pessoa, e fica com o dono do projeto. Os testes citados estão em `backend/`.

- [x] **HTTPS com HSTS.** `prod.py`: `SECURE_SSL_REDIRECT`, HSTS de 30 dias, `SECURE_PROXY_SSL_HEADER` (teste `tests/test_security_checklist.py::test_producao_liga_cookies_seguros_hsts_e_desliga_debug`). HSTS para subdomínios e *preload* ficam desligados de propósito (valeriam para o domínio inteiro, que tem outros sites) e os avisos W005/W021 do `check --deploy` são silenciados.
  - [ ] **Dono:** no servidor, conferir `curl -I https://<domínio>/` com `Strict-Transport-Security` e `make prod-check` sem avisos.
- [x] **`DEBUG=False`, `SECRET_KEY` de ambiente, `ALLOWED_HOSTS` e `CSRF_TRUSTED_ORIGINS`.** `prod.py` fixa `DEBUG=False` mesmo com `DEBUG=True` no ambiente; o Compose exige as variáveis; `check --deploy --fail-level WARNING` passa com a configuração de produção (teste `test_check_deploy_sem_avisos_com_configuracao_de_producao`). Cookies de sessão e CSRF `Secure`, sessão `HttpOnly`, `SameSite=Lax`, 14 dias de inatividade.
  - [ ] **Dono:** `SECRET_KEY` gerada no servidor e domínio real no `.env` (docs/34).
- [x] **CSP sem `unsafe-inline` para scripts.** `SecurityHeadersMiddleware` (`apps/core/middleware.py`) com `default-src 'self'`, estilos só do site, `img-src 'self' data: blob:`, `object-src 'none'`, `frame-ancestors 'none'`, `form-action` só do site e da Microsoft. Além disso: `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy` mínima (testes `test_cabecalhos_de_seguranca_nas_paginas` e `test_csp_do_admin_so_libera_estilos_inline`). Conferido no navegador com o build de produção: home, publicação, agenda, perfis, login, painel, menu, editor e admin sem nenhuma violação no console.
  - Desvio: `script-src` tem `'unsafe-eval'`, exigido pelo Alpine padrão (avalia `x-data` e `@click`). Sem nonce: não há script inline para liberar. Para tirar a exceção, trocar pelo build `@alpinejs/csp` (Evolução). O Django Admin aceita `'unsafe-inline'` só em estilos.
- [x] **CSRF em todos os POST.** Middleware do Django; HTMX e `fetch` mandam o token pelo cabeçalho (testes `test_login_exige_csrf` e `test_endpoints_htmx_exigem_csrf`).
- [x] **Rate limits testados.** Login: 5 erros por e-mail e 30 por IP em 15 min (`accounts/tests/test_login.py`); envio de imagens: 60 por hora (`publications/tests/test_media_endpoints.py::test_upload_rate_limit`). Reações, leituras, comentários e busca ainda não existem (Fases 2 e 3).
  - [ ] **Dono:** em produção, `TRUSTED_CLIENT_IP_HEADER=CF-Connecting-IP` para o limite usar o IP real.
- [x] **Uploads.** Tipo pelo conteúdo, 10 MB, 6000 px, EXIF removido, nomes aleatórios, cota (`publications/tests/test_media.py`); Caddy entrega `/media/` com `nosniff` e CSP `sandbox`.
- [x] **HTML sanitizado.** Documento limpo, HTML gerado no servidor e `nh3` (`publications/tests/test_rendering.py`, `test_html_de_publicacao_e_gerado_e_limpo_no_servidor`).
- [x] **Cadastro fechado.** Telas de cadastro, senha por e-mail e gestão de e-mails do allauth respondem 404; `/admin/login/` passa pelo login com limite (testes `test_telas_de_cadastro_e_senha_por_email_nao_existem` e `test_admin_login_passa_pela_tela_com_limite_de_tentativas`). Argon2 e mínimo de 10 caracteres.
- [ ] **Login Microsoft testado com conta real de professor; senha de reserva funcionando.** Senha de reserva e link de acesso cobertos por testes. **Dono:** registro Microsoft adiado (E06 parte 2, docs/32).
- [ ] **Página de privacidade publicada e revisada pela direção.** Texto completo escrito na E28 (`apps/core/services.py`, `PRIVACY_BODY`), fora do ar. **Dono:** levar à direção, ajustar pelo painel em "Páginas" e pôr no ar.
- [ ] **Termo de autorização de nome e imagem aprovado** e arquivamento combinado com a secretaria. Modelo pronto em [33](33-termo-de-autorizacao.md). **Dono:** aprovação da direção.
- [ ] **Backup executado e restaurado com sucesso.** Testado localmente na E27 (destino pasta). **Dono:** repetir no servidor com o R2 (docs/31 e 34).
- [ ] **Contas de teste removidas; admin com senha forte.** O banco de produção nasce vazio; `seed_demo` recusa rodar sem `DEBUG=True`. **Dono:** criar o admin com `make prod-superuser` e senha forte; nunca usar `admin@jornal.local` fora do dev.
- [x] **Logs de acesso.** Ajuste da E28: em vez de guardar IP por 14 dias, os logs não guardam o IP de quem visita. O Caddy não grava log de acesso; o Gunicorn registra o IP interno do Caddy; os logs dos containers giram por tamanho (5 × 10 MB). O IP do visitante só passa pela Cloudflare. A página de privacidade diz isso.
- [x] **`pip-audit` sem vulnerabilidade crítica.** Rodado em 2026-09-14 nas dependências de produção (`uv export --no-dev` + `uvx pip-audit`): nenhuma vulnerabilidade conhecida. `npm audit --omit=dev`: 0 vulnerabilidades. **Dono:** repetir antes de cada versão.

## Histórico

- 2026-09-12: versão inicial.
- 2026-09-12: reescrito para alunos sem conta, login Microsoft, sem e-mail, comentários públicos, Cloudflare.
- 2026-09-12: modelo do termo de autorização criado em [33](33-termo-de-autorizacao.md).
- 2026-09-14: E28: checklist marcada; CSP com `'unsafe-eval'` por causa do Alpine e sem nonce (não há script inline); HSTS sem subdomínios nem preload; logs sem IP do visitante em vez de retenção de 14 dias; texto da página de privacidade escrito, aguardando a direção.
