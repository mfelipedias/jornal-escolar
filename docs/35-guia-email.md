# 35 — Guia do e-mail (Gmail)

Para que serve: mandar aos professores o **código de 6 dígitos** do cadastro, o código de **"Esqueci minha senha"** e o aviso de **conta aprovada**. Os outros avisos do jornal continuam no sino do painel, sem e-mail.

Decisão do dono em 2026-09-28 ([27](27-decisoes-pendentes-e-perguntas.md), quinta rodada): usar o Gmail que ele já tem. Sem o e-mail configurado, o site funciona normalmente, mas os botões "Criar conta" e "Esqueci minha senha" não aparecem.

## O que é uma "senha de app"

O site precisa entrar no seu Gmail só para **enviar** e-mails. Ele não usa a sua senha normal: o Google gera uma senha especial, de 16 letras, que só serve para isso e pode ser apagada quando você quiser, sem mexer na sua senha de sempre.

## Passo a passo (uns 5 minutos)

1. Entre em <https://myaccount.google.com/security> com o Gmail que vai enviar os e-mails.
2. Em "Como você faz login no Google", ligue a **Verificação em duas etapas** (se ainda não estiver ligada). O Google só oferece senha de app com ela ligada.
3. Abra <https://myaccount.google.com/apppasswords>.
4. Em "Nome do app", escreva `Jornal Escolar` e clique em **Criar**.
5. Aparece uma senha de 16 letras em 4 blocos (ex.: `abcd efgh ijkl mnop`). Copie. Ela só aparece uma vez.
6. No servidor, abra `infra/env/.env` e preencha (a senha sem os espaços):

   ```
   EMAIL_HOST_USER=seu.email@gmail.com
   EMAIL_HOST_PASSWORD=abcdefghijklmnop
   ```

7. Atualize o site: `make deploy`.
8. Teste: `docker compose -f infra/docker-compose.yml --env-file infra/env/.env exec web python manage.py send_test_email seu.email@gmail.com`. Deve chegar "Teste do Jornal Escolar".

No computador de desenvolvimento não precisa de nada disso: sem Gmail configurado, os e-mails aparecem no terminal do Django (`docker compose logs web`), com o código.

## Como o e-mail chega

- Remetente: **Jornal Escolar &lt;seu.email@gmail.com&gt;**. O Gmail não deixa usar outro endereço.
- Limite do Gmail: cerca de 500 e-mails por dia, muito acima do que o jornal usa.
- Pode cair no spam na primeira vez. As telas avisam para olhar a caixa de spam.

## Configurações

| Onde | O quê |
|---|---|
| `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | Gmail e senha de app. Os dois preenchidos ligam o envio. |
| `SIGNUP_ALLOWED_DOMAINS` | Domínios aceitos no cadastro. Padrão: `prof.educacao.sp.gov.br,professor.educacao.sp.gov.br`. |
| Django Admin → Configurações → "Cadastro próprio ligado" | Desliga o cadastro sem mexer no servidor. |

## Problemas comuns

| Mensagem | O que fazer |
|---|---|
| `Username and Password not accepted` | A senha de app está errada ou foi apagada. Gere outra (passo 3). Não use a senha normal do Gmail. |
| `E-mail não configurado` | Falta `EMAIL_HOST_USER` ou `EMAIL_HOST_PASSWORD` no `.env`, ou falta rodar `make deploy`. |
| Professor diz que o código não chegou | Peça para olhar o spam e pedir outro código. São até 3 pedidos por hora. |

## Para desligar

Apague a senha de app em <https://myaccount.google.com/apppasswords> e esvazie as duas variáveis no `.env`.

## Histórico

- 2026-09-28: versão inicial (Fase 4b, C1).
