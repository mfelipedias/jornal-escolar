# 35 — Guia do e-mail (Gmail)

Para que serve: mandar aos professores o **código de 6 dígitos** do cadastro, o código de **"Esqueci minha senha"** e o aviso de **conta aprovada**. Os outros avisos do jornal continuam no sino do painel, sem e-mail.

Decisão do dono em 2026-09-28 ([27](27-decisoes-pendentes-e-perguntas.md), quinta rodada): usar o Gmail que ele já tem. Sem o e-mail configurado, o site funciona normalmente, mas os botões "Criar conta" e "Esqueci minha senha" não aparecem.

## O que é uma "senha de app"

O site precisa entrar no seu Gmail só para **enviar** e-mails. Ele não usa a sua senha normal: o Google gera uma senha especial, de 16 letras, que só serve para isso e pode ser apagada quando você quiser, sem mexer na sua senha de sempre.

## Passo a passo (uns 5 minutos)

### 1. Criar a senha de app no Google

1. Entre em <https://myaccount.google.com/security> com o Gmail que vai enviar os e-mails.
2. Em "Como você faz login no Google", ligue a **Verificação em duas etapas** (se ainda não estiver ligada). O Google só oferece senha de app com ela ligada.
3. Abra <https://myaccount.google.com/apppasswords>.
4. Em "Nome do app", escreva `Jornal Escolar` e clique em **Criar**.
5. Aparece uma senha de 16 letras em 4 blocos (ex.: `abcd efgh ijkl mnop`). Copie. Ela só aparece uma vez.
### 2. Colar no jornal, pela tela (jeito recomendado)

1. Entre no jornal como administrador e abra **Administração → E-mail de envio** (`/admin/core/emailsettings/`).
2. Servidor `smtp.gmail.com`, porta `587`, segurança "STARTTLS" (já vêm preenchidos).
3. Usuário: o seu Gmail. Senha: a senha de app (com ou sem espaços). Nome do remetente: opcional (vazio usa o nome do site).
4. **Salvar**. A senha fica guardada cifrada e nunca aparece de novo na tela; para trocar, digite outra; para manter, deixe o campo vazio.
5. Em "Testar o envio", clique em **Enviar e-mail de teste**. A tela diz na hora se deu certo ou mostra o erro do Gmail.

O campo "em uso agora" mostra se vale a configuração da tela ou a do `.env`.

### 2 (alternativa). Pelo arquivo do servidor

Se preferir não guardar a senha no banco: em `infra/env/.env`, preencha `EMAIL_HOST_USER=seu.email@gmail.com` e `EMAIL_HOST_PASSWORD=abcdefghijklmnop` (sem espaços), rode `make deploy` e teste com `docker compose -f infra/docker-compose.yml --env-file infra/env/.env exec web python manage.py send_test_email seu.email@gmail.com`. A tela, quando preenchida, tem prioridade sobre o arquivo.

No computador de desenvolvimento não precisa de nada disso: sem Gmail configurado, os e-mails aparecem no terminal do Django (`docker compose logs web`), com o código.

## Como o e-mail chega

- Remetente: **Jornal Escolar &lt;seu.email@gmail.com&gt;**. O Gmail não deixa usar outro endereço.
- Limite do Gmail: cerca de 500 e-mails por dia, muito acima do que o jornal usa.
- Pode cair no spam na primeira vez. As telas avisam para olhar a caixa de spam.

## Configurações

| Onde | O quê |
|---|---|
| Django Admin → E-mail de envio | Servidor, porta, segurança, usuário, senha (cifrada) e nome do remetente. Tem prioridade. |
| `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | Reserva no `.env`: Gmail e senha de app. |
| `SIGNUP_ALLOWED_DOMAINS` | Domínios aceitos no cadastro. Padrão: `prof.educacao.sp.gov.br,professor.educacao.sp.gov.br`. |
| Django Admin → Configurações → "Cadastro próprio ligado" | Desliga o cadastro sem mexer no servidor. |

## Problemas comuns

| Mensagem | O que fazer |
|---|---|
| `Username and Password not accepted` | A senha de app está errada ou foi apagada. Gere outra (passo 3). Não use a senha normal do Gmail. |
| `E-mail não configurado` | A tela está sem usuário ou senha e o `.env` também. Preencha a tela. |
| Professor diz que o código não chegou | Peça para olhar o spam e pedir outro código. São até 3 pedidos por hora. |

## A senha no banco e os backups

A senha da tela é cifrada com uma chave derivada do `SECRET_KEY` do servidor. O backup leva a senha cifrada, nunca a senha em si. Se um backup for restaurado num servidor com **outro** `SECRET_KEY`, a tela avisa "não abre com o SECRET_KEY atual": é só digitar a senha de app de novo.

## Para desligar

Apague a senha de app em <https://myaccount.google.com/apppasswords>, marque "apagar a senha salva" na tela e esvazie as duas variáveis no `.env`.

## Histórico

- 2026-09-28: versão inicial (Fase 4b, C1).
- 2026-09-28: C1b: configuração pela tela "E-mail de envio" do Django Admin, com senha cifrada e botão de teste; o `.env` vira reserva.
