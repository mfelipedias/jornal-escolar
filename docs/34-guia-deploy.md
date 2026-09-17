# 34 — Guia: como colocar o jornal no ar

Escrito para quem não trabalha com infraestrutura. Os detalhes técnicos estão em [24](24-infraestrutura-e-deploy.md); o backup tem guia próprio em [31](31-guia-backup.md).

Leva uma tarde na primeira vez. Depois, atualizar o site é um comando.

## A ideia em uma figura

```
Leitor no celular
      |
      v  https://jornal.projetosrosa.com.br
Cloudflare (cuida do HTTPS e protege contra ataques)
      |
      v  túnel criptografado, aberto DE DENTRO do servidor para fora
Servidor (home lab ou Oracle) com Docker
  ├─ cloudflared  ponta do túnel
  ├─ caddy        entrega CSS, JS e fotos; passa o resto adiante
  ├─ web          o Django (o jornal em si)
  ├─ db           o banco de dados
  └─ backup       às 3h copia banco e fotos para o Cloudflare R2
```

Por que túnel: o servidor não precisa de porta aberta no roteador nem de IP fixo. É o servidor que "liga" para a Cloudflare e mantém a linha aberta; os leitores chegam por essa linha. Se a internet de casa mudar de IP, nada quebra.

Cada caixinha acima é um **container**: um programa isolado, com tudo de que precisa, que o Docker liga e desliga. A receita de todos eles está em `infra/docker-compose.yml`.

## O que só você pode fazer

Marque conforme for fazendo. Nada disso cabe ao assistente de código, porque envolve contas e senhas suas.

- [ ] **Servidor** com Ubuntu e acesso por SSH (passo 1).
- [ ] **Chave de acesso do servidor ao GitHub**, porque o repositório é privado (passo 2).
- [ ] **Túnel na Cloudflare** e o token dele (passo 4).
- [ ] **Bucket no R2**, chave de acesso e senha do backup (passo 7 e [31](31-guia-backup.md)).
- [ ] **Conta no UptimeRobot** para avisar quando o site cair (passo 9).
- [ ] **Primeiro administrador** do jornal em produção (passo 6).
- [ ] Mais tarde: **registro do app na Microsoft** para o botão "Entrar com a conta da escola" ([32](32-guia-login-microsoft.md)). Até lá a equipe entra por senha com link de acesso.

## Passo 1 — O servidor

Qualquer um dos dois serve; o código é o mesmo.

| | Home lab | Oracle Cloud (gratuito) |
|---|---|---|
| Processador | x86 | ARM (Ampere A1) |
| Vantagem | Já é seu; necessário para a IA local no futuro | Não depende da energia e da internet de casa |
| Cuidado | Queda de luz ou de internet derruba o site | A Oracle às vezes diz "Out of capacity" ao criar a VM; tente outro horário ou outra região |

Requisitos: Ubuntu 24.04, 2 GB de RAM (4 GB é folgado), 20 GB de disco.

Na Oracle: crie uma instância "VM.Standard.A1.Flex" com Ubuntu 24.04, 1 OCPU e 6 GB de RAM já sobram. Guarde a chave SSH que ela oferece para baixar. **Não é preciso abrir nenhuma porta** além do SSH que já vem aberto.

Conecte no servidor pelo terminal do Windows:

```
ssh ubuntu@IP-DO-SERVIDOR
```

Instale Docker, git e make (copie e cole uma linha por vez):

```
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
sudo apt install -y git make
exit
```

O `exit` desconecta; conecte de novo com `ssh` para a permissão do Docker valer. Confira com `docker run --rm hello-world`: deve aparecer "Hello from Docker!".

Deixe o relógio no horário de São Paulo, para o backup rodar às 3h daqui:

```
sudo timedatectl set-timezone America/Sao_Paulo
```

## Passo 2 — Baixar o código

O repositório é privado, então o servidor precisa de uma chave para ler (só ler) o código.

1. No servidor: `ssh-keygen -t ed25519 -C servidor-jornal` e aperte Enter em todas as perguntas.
2. Mostre a chave pública: `cat ~/.ssh/id_ed25519.pub` e copie a linha inteira.
3. No GitHub: repositório → **Settings** → **Deploy keys** → **Add deploy key**. Título `servidor`, cole a chave, **deixe "Allow write access" desmarcado**.
4. No servidor:

```
git clone git@github.com:mfelipedias/jornal_escolar.git
cd jornal_escolar
```

Responda `yes` se ele perguntar sobre a "authenticity of host". Daqui em diante, todos os comandos são rodados dentro da pasta `jornal_escolar`.

## Passo 3 — O arquivo de configuração (.env)

```
cp infra/env/.env.producao.example infra/env/.env
nano infra/env/.env
```

O `nano` é um editor de texto no terminal: setas para andar, `Ctrl+O` e Enter para salvar, `Ctrl+X` para sair. Preencha:

| Variável | O que colocar |
|---|---|
| `SECRET_KEY` | Resultado de `python3 -c "import secrets; print(secrets.token_urlsafe(50))"` |
| `POSTGRES_PASSWORD` | Resultado de `python3 -c "import secrets; print(secrets.token_hex(24))"` (só letras e números) |
| `SITE_URL`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` | Já vêm com `jornal.projetosrosa.com.br`. Se o domínio mudar, troque nos três |
| `CLOUDFLARE_TUNNEL_TOKEN` | Passo 4 |
| `BACKUP_PASSPHRASE`, `R2_*` | Passo 7 (pode deixar vazio por enquanto) |

**`SITE_URL` precisa ser o domínio real**, com `https://` e sem barra no fim. É com ele que o jornal monta os links do sitemap, do Google e do WhatsApp; com um valor errado, quem compartilhar uma publicação manda um link quebrado.

Guarde uma cópia deste arquivo num gerenciador de senhas. O backup não cobre o `.env`.

## Passo 4 — O túnel na Cloudflare

1. Entre em `dash.cloudflare.com` → **Zero Trust** (no menu da esquerda). Na primeira vez ela pede um nome de equipe e um plano: escolha o **Free**.
2. **Networks** → **Tunnels** → **Create a tunnel** → tipo **Cloudflared**.
3. Nome: `jornal`. Salve.
4. Na tela de instalação, escolha **Docker**. Aparece um comando como `docker run cloudflare/cloudflared:latest tunnel run --token eyJhIjoi...`. **Copie só o texto depois de `--token`** (começa com `eyJ`) e cole em `CLOUDFLARE_TUNNEL_TOKEN` no `.env`. Não rode o comando que a Cloudflare mostra: o nosso Compose já faz isso.
5. Avance para **Public Hostname** (ou "Route traffic"):
   - Subdomain: `jornal`
   - Domain: `projetosrosa.com.br`
   - Service: tipo **HTTP**, URL **`caddy:80`**
6. Salve. A Cloudflare cria sozinha o registro de DNS.

Em **SSL/TLS** → **Edge Certificates**, deixe **Always Use HTTPS** ligado. Não ligue regras de "Cache Everything": o painel da equipe não pode ficar em cache.

## Passo 5 — Ligar o site

```
make deploy
```

Na primeira vez demora de 5 a 10 minutos: o servidor monta a imagem do jornal (CSS, JS, Python). O comando termina quando todos os containers estão de pé. Depois:

```
make prod-check
```

Mostra verificações de segurança do Django. Avisos `security.W005` e `security.W021` (subdomínios e lista de pré-carregamento do HSTS) podem ser ignorados. Um aviso `core.W001` ou `core.W002` quer dizer que o `SITE_URL` está errado: corrija o `.env` e rode `make deploy` de novo.

Abra no navegador `https://jornal.projetosrosa.com.br/healthz/`. Deve aparecer `{"status": "ok", "version": "..."}`.

O `make deploy` também liga o **worker**, o programa que roda sozinho as tarefas de rotina: apagar dados antigos de madrugada e deixar no sino do painel, de manhã, os avisos de comentários e revisões esquecidos. Não precisa configurar nada. Para conferir que ele está vivo:

```
docker compose -f infra/docker-compose.yml --env-file infra/env/.env logs worker
```

Uma vez por hora aparece a linha `Worker vivo`.

## Passo 6 — Primeiro administrador

```
make prod-superuser
```

Informe seu e-mail e uma senha longa. Entre em `https://jornal.projetosrosa.com.br/entrar/`, depois em `/admin/`, e revise as **Configurações** do site (nome, descrição, imagem de compartilhamento). A partir daí, cadastre a equipe pelo painel e gere os links de acesso (plano B do [32](32-guia-login-microsoft.md)).

## Passo 7 — Backup

Siga "O que você precisa fazer uma única vez" do [31](31-guia-backup.md): bucket `jornal-backup`, chave de acesso e senha de criptografia. Coloque os valores no `.env` e aplique:

```
make deploy
make backup
```

O `make backup` mostra os passos de 1/5 a 5/5 e termina com "Backup concluído". No painel da Cloudflare, em R2 → `jornal-backup`, devem aparecer as pastas `banco/` e `midia/`.

## Passo 8 — Teste de restauração

Faça pelo menos uma vez antes de divulgar o jornal, com o site ainda sem conteúdo importante:

```
make backups
make restore FILE=mais-recente
```

O script pede para digitar `RESTAURAR`. Ele apaga o banco, carrega o backup, traz as fotos e reinicia o site. Abra o jornal e confira se está como antes.

Em um servidor novo (troca do home lab para a Oracle, por exemplo) o caminho é o mesmo: passos 1 a 5 com o **mesmo `.env`**, `make restore FILE=mais-recente` e pronto. O túnel acompanha o token: desligue o servidor antigo (`make prod-down`) para os dois não disputarem o mesmo endereço.

## Passo 9 — Aviso quando o site cair (UptimeRobot)

1. Crie uma conta gratuita em `uptimerobot.com`.
2. **New monitor** → tipo **Keyword**.
3. URL: `https://jornal.projetosrosa.com.br/healthz/`
4. Keyword: `"status": "ok"`, com a opção de alertar quando a palavra **não existir**.
5. Intervalo: 5 minutos. Contato: seu e-mail (e o app do celular, se quiser notificação).

O `/healthz/` responde "ok" só quando o site, o banco e as migrações estão em ordem. Se o servidor desligar, a Cloudflare responde com erro e o UptimeRobot avisa do mesmo jeito.

## No dia a dia

| Quero... | Comando (na pasta `jornal_escolar` do servidor) |
|---|---|
| Atualizar o site para a versão nova do GitHub | `make deploy` |
| Ver o que está acontecendo / erros | `make prod-logs` (sai com `Ctrl+C`) |
| Ver as tarefas agendadas (limpezas e avisos) | Django Admin → "Procrastinate"; ou as linhas de `worker` no `make prod-logs` |
| Fazer um backup agora (antes de algo arriscado) | `make backup` |
| Desligar o site | `make prod-down` |
| Ver quanto disco o Docker usa | `docker system df` |
| Apagar imagens velhas depois de várias atualizações | `docker image prune` |

Os dados ficam em "volumes" do Docker e **sobrevivem** a `make deploy`, `make prod-down` e reinícios do servidor. Nunca rode `docker compose down -v` nem `docker volume rm` em produção: o `-v` apaga banco e fotos.

## Quando algo dá errado

| Sintoma | Causa provável | O que fazer |
|---|---|---|
| Cloudflare mostra "Error 1033" ou "Tunnel not found" | cloudflared parado ou token errado | `make prod-logs` e procure linhas de `cloudflared`; confira `CLOUDFLARE_TUNNEL_TOKEN` e `COMPOSE_PROFILES=tunel` |
| Cloudflare mostra "Bad gateway" (502) | Site ainda ligando ou com erro | Espere 1 minuto; se continuar, `make prod-logs` e procure linhas de `web` |
| "Muitos redirecionamentos" no navegador | O Django não percebeu que a visita veio por HTTPS | No `.env`, `SECURE_SSL_REDIRECT=False` (a Cloudflare já força HTTPS) e `make deploy` |
| `/healthz/` com `"status": "error"` | Banco fora do ar ou migração pendente | `make prod-logs`; normalmente `make deploy` resolve |
| Página "Bad Request (400)" | Domínio diferente do `ALLOWED_HOSTS` | Confira `ALLOWED_HOSTS` e `CSRF_TRUSTED_ORIGINS` |
| Links compartilhados apontam para `localhost` | `SITE_URL` errado | Corrija e `make deploy` |
| Avisos de revisão parada ou de comentários pendentes não chegam | `worker` parado | `make prod-logs` e procure linhas de `worker`; `make deploy` religa |
| `make backup` diz que a senha não confere | `BACKUP_PASSPHRASE` diferente da do primeiro backup | Recoloque a senha original; nunca troque a senha de um bucket em uso |

## Como foi testado (E27)

Sem servidor nem contas, a E27 testou tudo o que dá para testar num computador com Docker:

- Imagem do site construída para x86 e ARM (`make build`), e a de ARM executada com emulação.
- Compose de produção ligado sem o túnel, com outro nome de projeto e outra porta (8088), ao lado do ambiente de desenvolvimento: `/healthz/` respondendo "ok" pelo Caddy, CSS e imagens (`/static/img/og-default.png`) entregues pelo Caddy com cache, fotos em `/media/`.
- Backup para uma pasta local (`BACKUP_DESTINO=local`) no lugar do R2, com os arquivos criptografados; apagar um usuário e uma foto; restaurar o backup anterior e ver os dois de volta; apagar todos os volumes (simulando um servidor novo) e restaurar de novo; senha errada recusada sem mexer no banco.

O que falta, e só acontece no servidor real: túnel, R2, UptimeRobot e o site no endereço público.

## Histórico

- 2026-09-14: criado na E27.
- 2026-09-14: E39. Nada muda nos passos: o site passa a guardar o cache numa tabela do banco, criada sozinha ao ligar (`createcachetable` no entrypoint).
