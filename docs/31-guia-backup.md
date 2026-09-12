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
2. Empacota as fotos que mudaram desde o último backup.
3. Criptografa os dois pacotes com a sua senha.
4. Envia para o R2.
5. Confere se o arquivo do banco está íntegro.
6. Apaga cópias antigas, mantendo: os últimos 7 dias, as últimas 4 semanas e os últimos 6 meses.

Se algo falhar, aparece um aviso no painel de administração e no registro de erros.

## O que você precisa fazer uma única vez

Isso será feito na etapa E27, com o assistente de código ao lado. Anote aqui para saber o que esperar.

1. **Criar o espaço no R2.** No painel da Cloudflare, menu "R2", botão "Create bucket", nome `jornal-backup`. Um bucket é só uma pasta na nuvem.
2. **Criar uma chave de acesso.** Ainda em R2, "Manage R2 API Tokens", "Create API Token", permissão "Object Read & Write" restrita ao bucket `jornal-backup`. A Cloudflare mostra um `Access Key ID` e um `Secret Access Key`. **Copie os dois na hora**: o segundo não aparece de novo.
3. **Escolher a senha de criptografia.** Uma frase longa, por exemplo cinco palavras aleatórias. Guarde em um gerenciador de senhas ou em papel em lugar seguro. **Sem essa senha o backup é inútil.** Ela não fica na Cloudflare nem no código; fica só no arquivo `.env` do servidor e com você.
4. **Colocar tudo no arquivo `.env` do servidor:** `R2_ACCOUNT_ID` (aparece no painel do R2), `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET=jornal-backup` e `BACKUP_PASSPHRASE`.
5. **Rodar o primeiro backup à mão** com `make backup` e conferir no painel da Cloudflare que apareceram dois arquivos no bucket.

## Como conferir que está funcionando

Uma vez por mês, dois minutos:

- Abra o painel da Cloudflare, R2, bucket `jornal-backup`. Deve haver arquivos com a data de ontem.
- No painel de administração do jornal, a seção "Sistema" mostra a data e o tamanho do último backup bem-sucedido.

Se a data estiver velha, rode `make backup` no servidor e leia a mensagem de erro; normalmente é chave expirada ou disco cheio.

## Como restaurar (o teste que evita sustos)

A cada três meses, ou antes de qualquer mudança grande, faça um teste de restauração. É a única forma de saber que o backup serve para alguma coisa.

1. Em uma máquina limpa (pode ser a VPS da Oracle, ou o próprio computador com Docker), clone o repositório e copie o `.env` com as mesmas chaves do R2 e a mesma senha.
2. Rode `make restore FILE=<nome do arquivo no R2>`. O script baixa, descriptografa, recria o banco e a pasta de mídia.
3. Suba o site com `make dev` e abra no navegador. Se as publicações e fotos aparecem, o backup funciona.
4. Apague a máquina de teste.

Se um dia precisar restaurar de verdade, o processo é o mesmo, na máquina que vai virar o servidor definitivo, seguido de apontar o túnel da Cloudflare para ela.

## O que o backup não cobre

- O arquivo `.env` com as senhas: guarde uma cópia dele fora do servidor (gerenciador de senhas).
- O código: está no GitHub.
- A configuração da Cloudflare (domínio, túnel): fica na conta Cloudflare.

Com esses três itens mais o backup, o jornal pode ser reconstruído do zero em menos de uma hora.

## Histórico

- 2026-09-12: criado a pedido do dono do projeto.
