"""Tarefas agendadas do Jornal Escolar (E44; docs/24, "Tarefas agendadas").

Quem executa é o worker do Procrastinate (serviço `worker` nos Compose de dev e de produção,
comando `manage.py procrastinate worker`). A fila fica no próprio PostgreSQL, sem Redis.

Cada tarefa só chama a regra que já existe nos services (a mesma dos comandos de
gerenciamento), então rodar à mão com o comando e rodar pelo worker dá o mesmo resultado. Todas
podem rodar de novo sem estrago: nada é apagado duas vezes e nenhum aviso é repetido.

O Procrastinate lê o cron em UTC. Os horários abaixo são escritos no horário de Brasília por
`local_cron`, que converte para UTC.

| Tarefa | Quando (Brasília) | O que faz |
|---|---|---|
| heartbeat | a cada hora, no minuto 0 (*) | registra no log que o worker está vivo |
| cleanup | todo dia às 4h30 | leituras, comentários e notícias com prazo vencido (`cleanup`) |
| remind_pending_comments | todo dia às 7h | comentários de leitores pendentes há 3 dias |
| remind_stale_reviews | todo dia às 7h10 | revisões paradas há 5 dias |
| purge_worker_history | domingo às 5h | histórico de tarefas do worker com mais de 30 dias |

(*) `WORKER_HEARTBEAT_CRON`, em UTC; "* * * * *" mostra o agendamento funcionando.
"""

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import close_old_connections, connection
from procrastinate import JobContext
from procrastinate.contrib.django import app

from apps.accounts import signup
from apps.curation import services as curation
from apps.editorial import services as editorial
from apps.engagement import services as engagement

logger = logging.getLogger(__name__)

# Tarefas concluídas ficam no banco (dá para ver no admin) por este tempo.
JOBS_RETENTION_HOURS = 30 * 24


def local_cron(hour: int, minute: int, day_of_week: str = "*") -> str:
    """Cron em UTC para um horário de Brasília (TIME_ZONE). São Paulo não tem horário de verão
    desde 2019; se voltar a ter, o deslocamento do dia em que o worker liga é o que vale."""
    offset = datetime.now(ZoneInfo(settings.TIME_ZONE)).utcoffset()
    total = hour * 60 + minute - int(offset.total_seconds() // 60)
    if day_of_week != "*" and not 0 <= total < 24 * 60:
        raise ValueError("Em UTC esse horário cai em outro dia da semana: escolha outro.")
    utc_hour, utc_minute = divmod(total % (24 * 60), 60)
    return f"{utc_minute} {utc_hour} * * {day_of_week}"


def _when(timestamp: int) -> str:
    return datetime.fromtimestamp(timestamp, tz=UTC).isoformat()


def _run[T](name: str, timestamp: int | None, job: Callable[[], T]) -> T:
    """Roda uma regra síncrona do Django fechando conexões velhas antes e depois (o worker é um
    processo que fica ligado dias seguidos). Dentro de uma transação (nos testes) não mexe."""
    managed = not connection.in_atomic_block
    if managed:
        close_old_connections()
    try:
        result = job()
    finally:
        if managed:
            close_old_connections()
    if timestamp is None:
        logger.info("Tarefa %s: %s", name, result)
    else:
        logger.info("Tarefa %s (agendada para %s): %s", name, _when(timestamp), result)
    return result


@app.periodic(cron=settings.WORKER_HEARTBEAT_CRON)
@app.task(name="heartbeat", queueing_lock="heartbeat")
def heartbeat(timestamp: int) -> str:
    """Tarefa de teste: prova que o worker liga, agenda e executa no horário."""
    logger.info("Worker vivo (batimento agendado para %s).", _when(timestamp))
    return _when(timestamp)


@app.periodic(cron=local_cron(4, 30))
@app.task(name="cleanup", queueing_lock="cleanup")
def cleanup(timestamp: int) -> dict[str, int]:
    def job() -> dict[str, int]:
        rejected, cleared = engagement.purge_old_comments()
        return {
            "leituras": engagement.purge_old_reads(),
            "comentarios_rejeitados": rejected,
            "comentarios_sem_dados_tecnicos": cleared,
            "noticias_antigas": curation.purge_old_items(),
            "codigos_de_email": signup.purge_old_codes(),
        }

    return _run("cleanup", timestamp, job)


@app.periodic(cron=local_cron(7, 0))
@app.task(name="remind_pending_comments", queueing_lock="remind_pending_comments")
def remind_pending_comments(timestamp: int) -> int:
    return _run("remind_pending_comments", timestamp, engagement.remind_stale_pending_comments)


@app.periodic(cron=local_cron(7, 10))
@app.task(name="remind_stale_reviews", queueing_lock="remind_stale_reviews")
def remind_stale_reviews(timestamp: int) -> int:
    return _run("remind_stale_reviews", timestamp, editorial.remind_stale_reviews)


@app.periodic(cron=local_cron(5, 0, day_of_week="0"))
@app.task(name="purge_worker_history", pass_context=True, queueing_lock="purge_worker_history")
async def purge_worker_history(context: JobContext, timestamp: int) -> None:
    """Apaga do banco o registro das tarefas concluídas há mais de 30 dias (as que falharam
    ficam, para investigar)."""
    await context.app.job_manager.delete_old_jobs(nb_hours=JOBS_RETENTION_HOURS)
    logger.info("Histórico antigo do worker apagado (agendado para %s).", _when(timestamp))
