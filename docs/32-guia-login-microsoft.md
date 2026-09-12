# 32 — Guia: login com a conta da escola (Microsoft)

Escrito para quem não trabalha com a área. Detalhes técnicos em [23](23-seguranca-e-lgpd.md).

## A ideia

Cada professor já tem um e-mail `@professor.educacao.sp.gov.br`, que é uma conta Microsoft. Em vez de criar mais uma senha para o jornal, a pessoa clica em "Entrar com a conta da escola", digita o e-mail e a senha que já usa no Teams ou no Outlook, e a Microsoft confirma para o jornal: "sim, esta pessoa é quem diz ser". O jornal nunca vê a senha.

Funciona como o botão "Entrar com Google" que aparece em vários sites.

## Quem decide se isso funciona

Aqui está a parte que gera a dúvida. As contas `@professor.educacao.sp.gov.br` pertencem à **organização Microsoft da Secretaria da Educação**. Quem administra essa organização decide quais aplicativos externos podem usar as contas dos professores para fazer login. Em muitas organizações isso é liberado; em outras, é bloqueado por política de segurança.

Então existem dois cenários:

| Cenário | O que acontece | O que você faz |
|---|---|---|
| A Secretaria permite | O botão "Entrar com a conta da escola" funciona. Cada professor entra com o e-mail institucional, sem senha nova. | Nada além de cadastrar o e-mail de cada pessoa no painel de administração. |
| A Secretaria bloqueia | Ao clicar no botão, a Microsoft mostra uma mensagem do tipo "seu administrador não permitiu este aplicativo". | O jornal usa o plano B: cada pessoa entra com uma senha própria do jornal. |

Não há como saber antes de testar. Por isso a etapa E09 do plano inclui um teste com a sua própria conta de professor. Os dois caminhos já estão previstos; nenhum código muda, só a configuração.

## Plano B: senha própria, sem e-mail

Como o jornal não envia e-mail, o processo é:

1. Você cadastra a pessoa no painel de administração (e-mail, nome, papel, cargo).
2. Clica em "Gerar link de acesso". Aparece um endereço como `https://jornal.projetosrosa.com.br/acesso/8f3a...`.
3. Você manda esse link para a pessoa por WhatsApp, pessoalmente, ou como preferir. O link vale por 7 dias e funciona uma única vez.
4. A pessoa abre o link, cria a senha e já está dentro.
5. Se esquecer a senha, ela pede a você, e você gera outro link.

O plano B funciona mesmo quando o login Microsoft está ativo: serve para quem não tem conta institucional ou está com problema nela.

## O que você precisa fazer uma única vez (etapa E06)

Para o botão da Microsoft existir, o jornal precisa estar "registrado" na Microsoft como um aplicativo. É gratuito e leva uns 15 minutos, feito com o assistente de código ao lado:

1. Entrar em `portal.azure.com` com **qualquer conta Microsoft** (pode ser uma conta pessoal Outlook; não precisa ser a da escola, e não precisa de cartão de crédito para isso).
2. Procurar "Microsoft Entra ID", depois "App registrations", "New registration".
3. Nome: `Jornal Escolar`. Em "Supported account types", escolher a opção que inclui **contas de qualquer organização** (multi-tenant). É isso que permite que contas da Secretaria entrem.
4. Em "Redirect URI", tipo Web, colocar `https://jornal.projetosrosa.com.br/entrar/microsoft/login/callback/`. Para testar no seu computador, adicione também `http://localhost:8000/entrar/microsoft/login/callback/` (em "Authentication", "Add URI").
5. Depois de criar, copiar o **Application (client) ID**.
6. Em "Certificates & secrets", criar um "client secret", e **copiar o valor na hora** (não aparece de novo). Anotar a validade (escolher 24 meses) e marcar na agenda para renovar.
7. Em "API permissions", garantir que existe `User.Read` (vem por padrão). Nada mais.
8. Colocar os dois valores no `.env` do servidor: `MS_CLIENT_ID` e `MS_CLIENT_SECRET`. Para testar no computador, coloque-os em `infra/env/.env` e rode `docker compose up` de novo: o botão "Entrar com a conta da escola" aparece em `/entrar/`.

## Como testar com uma conta real (etapa E09)

1. Cadastre no `/admin/` um usuário com o seu e-mail `@professor.educacao.sp.gov.br` (sem senha).
2. Abra `/entrar/` e clique em "Entrar com a conta da escola".
3. Resultados possíveis:
   - Voltou para o jornal com seu nome no topo: **funcionou**.
   - A Microsoft mostrou "aprovação do administrador necessária": **a Secretaria bloqueou**. Use o plano B.
   - O jornal mostrou "Peça ao administrador para cadastrar você": o e-mail cadastrado é diferente do da conta Microsoft.

O jornal só lê o e-mail e o nome da pessoa. Não acessa arquivos, agenda nem mensagens.

## Segurança: quem consegue entrar

Mesmo com o botão funcionando, **só entra quem você cadastrou antes**. Um professor de outra escola, com e-mail do mesmo domínio, vê a mensagem "Peça ao administrador para cadastrar você". Isso garante que a lista de quem escreve no jornal é decidida por você, não pela Microsoft.

## Se um dia mudar de ideia

Se preferir que todo mundo use senha própria, basta desligar o botão na configuração. Se a Secretaria liberar o aplicativo depois de ter bloqueado, é só ligar de novo. As contas são as mesmas nos dois casos.

## Histórico

- 2026-09-12: criado após dúvida do dono do projeto.
- 2026-09-12: E09 implementada; endereço de retorno definitivo, teste local e roteiro de teste com conta real. A configuração "Login com a conta Microsoft da escola ligado" fica em Admin → Configurações.
