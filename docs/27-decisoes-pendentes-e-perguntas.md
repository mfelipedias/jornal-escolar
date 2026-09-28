# 27 — Decisões tomadas e perguntas

Em 2026-09-12 o dono do projeto respondeu às perguntas da primeira versão deste documento. As respostas e as decisões resultantes estão registradas abaixo. Os documentos afetados foram atualizados na mesma data.

## Respostas e decisões

### P1. Identidade e login
**Resposta:** professores têm contas institucionais Microsoft (`@professor.educacao.sp.gov.br`).
**Decisão:** login com Microsoft (Entra ID) via `django-allauth` na Fase 1, restrito a domínios permitidos e a contas pré-cadastradas pelo admin. Senha como reserva, ativada por link de primeiro acesso. Risco registrado: o tenant do estado pode bloquear aplicativos externos; testar na E09. → [23](23-seguranca-e-lgpd.md), [14](14-configuracao-de-perfil.md)

### P2. Exposição do servidor
**Resposta:** Docker Compose; home lab com Cloudflare Tunnel, com opção de VPS gratuita da Oracle; domínio `jornal.projetosrosa.com.br`.
**Decisão:** Cloudflare Tunnel em qualquer alvo; imagens multi-arch para servir o home lab (x86) e a Oracle (ARM); banco em um só lugar por vez. → [24](24-infraestrutura-e-deploy.md)

### P3 e P5. Política de publicação e quem modera
**Resposta:** nada é publicado automaticamente; tudo passa por um professor. Alunos não publicam nem têm cadastro; participam entregando o texto a um professor, que publica e credita. Cada professor tem autonomia para publicar, editar e excluir as próprias publicações. Coordenação, direção e admin podem moderar.
**Decisão:** `editorial.self_publish = staff`. O professor é o humano que aprova. Revisão por colega é opcional. Estado "aprovado" removido. Papéis: equipe, editor (coordenação/direção), admin. → [02](02-personas-papeis-permissoes.md), [04](04-fluxo-editorial.md)

### P4. Alunos
**Resposta:** não há termo de uso de imagem. Alunos da 1ª à 3ª série do ensino médio.
**Decisão:** alunos sem conta. Crédito com política de nome `first_initial` por padrão e marcação obrigatória de autorização pelo professor. Redigir o termo de autorização com a direção é tarefa da Fase 0 (E06b). → [23](23-seguranca-e-lgpd.md)

### P6. Identidade visual e nome
**Resposta:** sem identidade definida; tema claro e colorido; nome simples e autoexplicativo; escola [nome da escola omitido].
**Decisão:** nome **"Jornal da Rosa"**, tagline "Jornal digital da comunidade escolar" (a tagline inicial citava a escola; revista na segunda rodada, abaixo). Acento em rosa profundo, fundo claro, cores de área mais vivas. Marca: wordmark em Newsreader com um glifo de rosa simples, desenhado na E04. **Revisto na E01:** nome passou a "Jornal Escolar" e o glifo a uma folha de jornal (ver tabela da segunda rodada). → [09](09-design-system.md)

### P7. E-mail
**Resposta:** não há.
**Decisão:** nenhuma dependência de e-mail. Notificações no painel viram MVP. Contas criadas pelo admin; links de acesso entregues manualmente. E-mail por serviço gratuito é Evolução. → [04](04-fluxo-editorial.md), [06](06-modelo-de-dados.md)

### P8. Áreas do conhecimento
**Resposta:** áreas da BNCC; alimentar com todas as opções da escola; editável no painel administrativo.
**Decisão:** seed com as quatro áreas da BNCC mais "Formação e Projetos" e "Escola e Comunidade", com as disciplinas da rede estadual de SP. Tudo editável no Django Admin. → [18](18-painel-administrativo.md)

### Perguntas secundárias
| Pergunta | Resposta | Decisão |
|---|---|---|
| Nome e tagline | Você decide; escola [nome da escola omitido] | "Jornal da Rosa", depois trocado por "Jornal Escolar" (ver tabela da segunda rodada) |
| Fontes RSS | Gratuitas | Lista sugerida em [21](21-curadoria-de-noticias.md), sem APIs pagas |
| Sugestões em inglês | Sim | Preferência por usuário, ligada por padrão |
| Funcionários não docentes | Sim: coordenação, direção, monitores | Campo `staff_kind`; "Quem escreve" lista toda a equipe |
| Arquivo `.ics` | Não sabe o que é | É um arquivo que adiciona o evento ao calendário do celular. Fica na Fase 6 |
| Modo escuro | Não agora; deixar preparado | Tokens preparados; nenhum trabalho até haver pedido |
| Página pública de aluno | Não; alunos não têm cadastro | Confirmado; nunca |

### Pontos de divergência em relação ao briefing original
| Ponto | Resposta | Resultado |
|---|---|---|
| Leitor sem conta, reações anônimas | Sim | Mantido |
| Sem comentários públicos | **Não**: quer comentários com nome, visíveis só após aprovação do autor da publicação ou de admin | Comentários moderados na Fase 3 → [20](20-reacoes-leituras-comentarios.md) |
| Sem clima | **Não**: quer API de clima, se possível auto-hospedável | Open-Meteo na Fase 3 → [29](29-clima.md) |
| Sem frontend separado | Sem objeção | Mantido |
| Sem API pública no MVP | Sem objeção | Mantido |
| Papéis reduzidos | Sem objeção | Reduzidos ainda mais: três com conta |
| Revisor como atribuição | Sem objeção | Mantido, opcional |
| RSS antes de APIs | Sem objeção | Mantido |
| IA nunca gera texto | Toda a IA é projeto futuro | Fase 5 congelada → [22](22-ia.md) |

### Pedido adicional
**Versionamento** com número discreto no rodapé. → [30](30-versionamento.md)

## Segunda rodada de respostas (2026-09-12)

| Pergunta | Resposta | Decisão |
|---|---|---|
| Nome oficial da escola no rodapé | Não incluir o nome da escola no site. Rodapé: "Desenvolvido por Professor Marcos Felipe A. D. da Silva - marcossilva06@professor.educacao.sp.gov.br" | Nome da escola removido de tagline, rodapé, dados estruturados e configurações. Crédito e e-mail de contato configuráveis em `site.footer_credit` e `site.contact_email`. → [09](09-design-system.md) |
| Coordenadas para o clima | Clima de Osasco-SP | `WEATHER_LAT = -23.5329`, `WEATHER_LON = -46.7918`. → [29](29-clima.md) |
| Destino do backup | Não entende; fazer como sugerido e documentar | Cloudflare R2, na mesma conta já usada para o domínio. Guia em linguagem simples em [31](31-guia-backup.md) |
| Primeiros editores | Ainda não sabe | O administrador exerce o papel de editor até a escola definir alguém. → [02](02-personas-papeis-permissoes.md) |
| Nome do projeto (terceira rodada, durante a E01) | Deixar mais genérico: "Jornal Escolar" | "Jornal da Rosa" substituído por **"Jornal Escolar"** no código e na documentação; editável em `site.name`. Glifo passa a ser uma folha de jornal; acento rosa mantido; domínio `jornal.projetosrosa.com.br` não muda. → [09](09-design-system.md) |
| Login Microsoft bloqueado | Não entendeu a questão | Explicado em [32](32-guia-login-microsoft.md). Resumo: quem permite ou não o login com as contas dos professores é a Secretaria da Educação, não nós; se ela bloquear, cada pessoa entra com senha criada por um link que o admin gera. Nada a fazer agora; testamos na etapa E09. |

## Terceira rodada (2026-09-12)

| Pergunta | Resposta | Decisão |
|---|---|---|
| Ordem das próximas etapas | Continuar na ordem do plano | Segue da E19; curadoria de notícias continua na Fase 4. → [26](26-plano-de-desenvolvimento.md) |
| Registro do app na Microsoft | Não pretende fazer tão cedo | E06 parte 2 adiada. Login por senha com link de acesso é o caminho padrão; o botão Microsoft só aparece quando as credenciais forem configuradas. → [32](32-guia-login-microsoft.md) |
| Termo de uso de imagem | O projeto pode redigir o modelo | Modelo em [33](33-termo-de-autorizacao.md); direção revisa e aprova antes da primeira publicação com aluno. |

## Quarta rodada (2026-09-15)

| Pergunta | Resposta | Decisão |
|---|---|---|
| Visual do site (não perguntado; pedido espontâneo do dono ao ver o site) | "Está o design muito sério. É um jornal escolar, deve ser visualmente atrativo aos alunos. Replaneje movimentos, cores, modernização, logo, favicon etc. Você é o profissional." | Redesign na Fase 3b (R1–R5) com a direção "Pátio": fonte de display nova, acento mais vivo, cores de área saturadas em blocos, marca nova (avião de papel de jornal), favicons completos, animações de entrada e microinterações (todas desligadas com `prefers-reduced-motion`). Revoga do [09](09-design-system.md) as regras "nada de animação de entrada", "sem gradientes" e "sem sombras pesadas". Mantém: sem infantilização, contraste AA, nome da escola em lugar nenhum. → [09](09-design-system.md), [26](26-plano-de-desenvolvimento.md) |
| Carregamento da página | "Enquanto carrega eu vejo um emoji e uma página toda quebrada até ela se reconstruir; fica feia e demora." | Causa: no modo dev o Vite injeta o CSS por JavaScript, então o HTML aparece sem estilo até o script rodar. Correção na R1: CSS como entrada própria carregada por `<link>` antes do JS, preload das fontes e fallbacks com métricas. → [09](09-design-system.md) |

## Quinta rodada (2026-09-28)

| Pergunta | Resposta | Decisão |
|---|---|---|
| Login com Google ou passkeys (pedido do dono, depois descartado) | "Esquece isso. Vamos usar por enquanto só cadastros feitos dentro do próprio sistema." | Sem Google e sem passkeys. O login Microsoft continua no código, desligado enquanto não houver registro do app. |
| Quem cria a conta (revê P1) | "O professor cria seu próprio cadastro (permitindo só e-mails @prof e @professor), recebe um código por e-mail para criar a senha e logar; depois faz o passo a passo do restante do cadastro." | **Cadastro aberto** em `/cadastro/` só para `@prof.educacao.sp.gov.br` e `@professor.educacao.sp.gov.br` (`SIGNUP_ALLOWED_DOMAINS`). Código de 6 dígitos por e-mail, senha criada junto, e em seguida o assistente de primeiro acesso ([14](14-configuracao-de-perfil.md)). O admin continua podendo cadastrar qualquer pessoa (coordenação, monitores). → [23](23-seguranca-e-lgpd.md), Fase 4b em [26](26-plano-de-desenvolvimento.md) |
| Envio de e-mail (revê P7) | Gmail do dono, com senha de app (escolhido entre Brevo e Gmail) | E-mail pelo SMTP do Gmail (`EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`). Só e-mails de conta: código de cadastro, recuperação de senha e conta aprovada. Os avisos do dia a dia continuam no sino. Guia em [35](35-guia-email.md). Sem e-mail configurado, o cadastro e o "esqueci minha senha" ficam escondidos. |
| Quem se cadastra já publica? | "Admin aprova antes" | Conta criada pelo cadastro nasce **aguardando aprovação**: entra, completa o perfil e vê "aguardando aprovação"; não escreve nem acessa o resto do painel. Editores e admin aprovam ou recusam no painel editorial e recebem aviso no sino. Contas criadas pelo admin nascem aprovadas. → [02](02-personas-papeis-permissoes.md) |

## Decisões que continuam abertas

Nenhuma. Tudo o que não foi decidido tem um padrão definido e pode mudar depois sem impacto estrutural.

## Histórico

- 2026-09-12: versão inicial com perguntas.
- 2026-09-12: respostas recebidas e incorporadas; documento reescrito como registro.
- 2026-09-12: segunda rodada de respostas incorporada; guias 31 e 32 criados.
- 2026-09-12: terceira rodada: Microsoft adiada, termo redigido pelo projeto (33).
- 2026-09-15: quarta rodada: redesign visual e carregamento sem salto.
- 2026-09-28: quinta rodada: cadastro próprio com código por e-mail (Gmail), aprovação por editor/admin; P1 e P7 revistos.
