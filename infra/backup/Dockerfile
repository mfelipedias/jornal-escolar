# Container de backup do Jornal Escolar (docs/24, "Backups"; guia em docs/31).
#
# Pequeno Linux (Alpine) com:
#   postgresql17-client  pg_dump e pg_restore, na mesma versão do banco
#   rclone               envia e busca arquivos no Cloudflare R2, criptografando no caminho
#   supercronic          relógio que dispara o backup todo dia às 3h
#   python               os scripts backup.py e restore.py
# Funciona em x86 e ARM (os pacotes do Alpine existem para os dois).
FROM python:3.13-alpine

RUN apk add --no-cache postgresql17-client rclone supercronic tzdata

ENV TZ=America/Sao_Paulo \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app
COPY comum.py backup.py restore.py crontab /app/

CMD ["supercronic", "-passthrough-logs", "/app/crontab"]
