# 31 — Guia: como funciona o backup e o que você precisa fazer

Escrito para quem não trabalha com infraestrutura. Detalhes técnicos estão em [24](24-infraestrutura-e-deploy.md).

## O que é e por que importa

Tudo o que o jornal guarda fica em dois lugares no servidor: o **banco de dados** (textos, contas, créditos, comentários, configurações) e a **pasta de mídia** (fotos enviadas). Se o disco do servidor morrer, o container for apagado por engano ou alguém invadir e destruir os dados, sem backup tudo se perde.

Backup é uma cópia desses dois lugares, feita automaticamente todos os dias, guardada **fora do servidor**, em um serviço de armazenamento na internet. Se o pior acontecer, você restaura a cópia em outro servidor e o jornal volta como estava na madrugada anterior.

A regra que seguimos, simplificada: os dados existem em ao menos dois lugares diferentes, e um deles não está na sua casa.

## Onde a cópia fica

**Cloudflare R2.** É o serviço de armazenamento da Cloudflare, a mesma empresa que já vai cuidar do domínio `jornal.projetosrosa.com.br` e do túnel. Motivos da escolha:

- Você já terá uma conta Cloudflare; não precisa criar conta em outro lugar.
- Os primeiros 10 GB são gratuitos, e o jornal inteiro deve ocupar menos de 2 GB por muitos anos.
- Não cobra para baixar os dados de volta, o que importa na hora de restaurar.
- É compatível com a ferramenta padrão que o servidor usa para enviar arquivos (`rclone`).

A cópia é **criptografada** antes de sair do servidor com uma senha que só você tem. Nem a Cloudflare consegue ler.

## O que acontece todo dia, sem você fazer nada

Às 3h da manhã, um pequeno programa dentro do servidor:

1. Exporta o banco de dados inteiro para um arquivo.
2. Confere se o arquivo do banco está íntegro.
3. Criptografa e envia o arquivo para o R2, na pasta `banco/`.
4. Envia as fotos novas para a pasta `midia/`, também criptografadas. Fotos apagadas no site não somem na hora: vão para `midia-removida/` e ficam lá por 6 meses.
5. Apaga cópias antigas do banco, mantendo: tudo dos últimos 7 dias, uma por semana das últimas 4 semanas e uma por mês dos últimos 6 meses.

Se algo falhar, a mensagem fica no registro do servidor (`make prod-logs`, linhas do `backup`). Um aviso no painel de administração é uma melhoria futura; por enquanto, confira uma vez por mês como explicado abaixo.

## O que você precisa fazer uma única vez

Faça junto com o passo 7 do guia de deploy ([34](34-guia-deploy.md)). O código já está pronto desde a E27.

1. **Criar o espaço no R2.** No painel da Cloudflare, menu "R2", botão "Create bucket", nome `jornal-backup`. Um bucket é só uma pasta na nuvem.
2. **Criar uma chave de acesso.** Ainda em R2, "Manage R2 API Tokens", "Create API Token", permissão "Object Read & Write" restrita ao bucket `jornal-backup`. A Cloudflare mostra um `Access Key ID` e um `Secret Access Key`. **Copie os dois na hora**: o segundo não aparece de novo.
3. **Escolher a senha de criptografia.** Uma frase longa, por exemplo cinco palavras aleatórias (sem o símbolo `$` e sem aspas). Guarde em um gerenciador de senhas ou em papel em lugar seguro. **Sem essa senha o backup é inútil.** Ela não fica na Cloudflare nem no código; fica só no arquivo `.env` do servidor e com você. **Não troque essa senha depois do primeiro backup**: os arquivos antigos só abrem com a senha antiga.
4. **Colocar tudo no arquivo `.env` do servidor:** `R2_ACCOUNT_ID` (aparece no painel do R2), `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET=jornal-backup` e `BACKUP_PASSPHRASE`.
5. **Rodar o primeiro backup à mão** com `make deploy` (para o servidor ler o `.env` novo) e `make backup`, e conferir no painel da Cloudflare que apareceram as pastas `banco/` e `midia/` no bucket. Os arquivos terminam em `.bin`: é a criptografia.

## Como conferir que está funcionando

Uma vez por mês, dois minutos:

- Abra o painel da Cloudflare, R2, bucket `jornal-backup`, pasta `banco/`. Deve haver um arquivo com a data de ontem no nome (`jornal-AAAA-MM-DD_030000.dump.bin`).
- Ou, no servidor, `make backups` lista os backups disponíveis.

Se a data estiver velha, rode `make backup` no servidor e leia a mensagem de erro; normalmente é chave expirada ou disco cheio.

## Como restaurar (o teste que evita sustos)

A cada três meses, ou antes de qualquer mudança grande, faça um teste de restauração. É a única forma de saber que o backup serve para alguma coisa.

1. Em uma máquina limpa (pode ser a VPS da Oracle), siga os passos 1 a 3 do [34](34-guia-deploy.md) e copie o `.env` com as mesmas chaves do R2 e a mesma senha. **Nessa cópia, deixe `COMPOSE_PROFILES=` vazio**: sem isso a máquina de teste liga o túnel e passa a dividir os leitores com o servidor de verdade.
2. Rode `make deploy` e depois `make restore FILE=mais-recente` (ou o nome de um backup mostrado por `make backups`). O script pede para digitar `RESTAURAR`, baixa, descriptografa, recria o banco, traz as fotos e reinicia o site.
3. No navegador da própria máquina, abra `http://127.0.0.1:8080` (no `.env` de teste: `SECURE_SSL_REDIRECT=False` e `127.0.0.1` acrescentado em `ALLOWED_HOSTS`, separado por vírgula). Se as publicações e fotos aparecem, o backup funciona.
4. No mesmo dia, rode `make prod-down` e apague a máquina de teste. Se ela ficar ligada, às 3h ela também faria backup no mesmo bucket.

Se um dia precisar restaurar de verdade, o processo é o mesmo, na máquina que vai virar o servidor definitivo, com o `.env` completo (inclusive `COMPOSE_PROFILES=tunel`): o túnel acompanha o token e passa a apontar para ela. Desligue o servidor antigo, se ele ainda existir.

## O que o backup não cobre

- O arquivo `.env` com as senhas: guarde uma cópia dele fora do servidor (gerenciador de senhas).
- O código: está no GitHub.
- A configuração da Cloudflare (domínio, túnel): fica na conta Cloudflare.

Com esses três itens mais o backup, o jornal pode ser reconstruído do zero em menos de uma hora.

## Histórico

- 2026-09-12: criado a pedido do dono do projeto.
- 2026-09-14: E27: pastas `banco/`, `midia/` e `midia-removida/` no bucket; retenção guarda tudo dos últimos 7 dias; teste de restauração sem túnel; aviso no painel fica para depois.
