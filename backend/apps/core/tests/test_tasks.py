"""Tarefas agendadas do worker (E44, docs/24, "Tarefas agendadas").

Os testes não ligam o worker de verdade: conferem os horários registrados, chamam cada tarefa
como função (a regra de negócio é a mesma dos comandos) e, para provar que o Procrastinate
enfileira e executa, usam o conector em memória.
"""

from datetime import UTC, datetime, timedelta
from itertools import pairwise
from zoneinfo import ZoneInfo

import croniter
import pytest
from django.utils import timezone
from procrastinate.contrib.django import app
from procrastinate.testing import InMemoryConnector

from apps.core import tasks
from apps.engagement.models import ArticleRead
from tests.factories import ArticleFactory

SP = ZoneInfo("America/Sao_Paulo")

# Horário de Brasília esperado para cada tarefa: (hora, minuto, dia da semana ou None).
EXPECTED = {
    "cleanup": (4, 30, None),
    "remind_pending_comments": (7, 0, None),
    "remind_stale_reviews": (7, 10, None),
    "purge_worker_history": (5, 0, 6),  # domingo (weekday() do Python)
}


def periodic_crons() -> dict[str, str]:
    """Tarefas periódicas deste módulo (outros apps registram as suas, como a curadoria)."""
    return {
        name: task.cron
        for (name, _), task in app.periodic_registry.periodic_tasks.items()
        if task.task.func.__module__ == tasks.__name__
    }


def next_local_run(cron: str, start: datetime) -> datetime:
    """Como o Procrastinate calcula: croniter sobre o timestamp (UTC)."""
    it = croniter.croniter(cron)
    it.set_current(start_time=start.timestamp())
    return datetime.fromtimestamp(it.get_next(ret_type=float), tz=UTC).astimezone(SP)


def test_todas_as_tarefas_estao_agendadas():
    assert set(periodic_crons()) == {"heartbeat", *EXPECTED}


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_tarefa_roda_no_horario_de_brasilia(name):
    hour, minute, weekday = EXPECTED[name]
    cron = periodic_crons()[name]
    runs = [datetime(2026, 9, 17, 12, 0, tzinfo=SP)]  # quinta-feira ao meio-dia
    for _ in range(3):
        runs.append(next_local_run(cron, runs[-1]))
    runs = runs[1:]
    step = timedelta(days=1 if weekday is None else 7)
    for run in runs:
        assert (run.hour, run.minute) == (hour, minute)
        if weekday is not None:
            assert run.weekday() == weekday
    assert [b - a for a, b in pairwise(runs)] == [step, step]


def test_batimento_a_cada_hora_por_padrao():
    assert periodic_crons()["heartbeat"] == "0 * * * *"


def test_local_cron_converte_para_utc():
    assert tasks.local_cron(4, 30) == "30 7 * * *"
    assert tasks.local_cron(22, 15) == "15 1 * * *"  # passa da meia-noite em UTC
    assert tasks.local_cron(5, 0, day_of_week="0") == "0 8 * * 0"


def test_local_cron_recusa_dia_da_semana_que_muda_em_utc():
    with pytest.raises(ValueError, match="outro dia"):
        tasks.local_cron(22, 0, day_of_week="5")


# --- cada tarefa chama a regra certa ---


@pytest.mark.django_db
def test_avisos_chamam_os_services(monkeypatch):
    calls = []
    monkeypatch.setattr(
        tasks.engagement, "remind_stale_pending_comments", lambda: calls.append("comentarios") or 2
    )
    monkeypatch.setattr(
        tasks.editorial, "remind_stale_reviews", lambda: calls.append("revisoes") or 1
    )

    assert tasks.remind_pending_comments(timestamp=0) == 2
    assert tasks.remind_stale_reviews(timestamp=0) == 1
    assert calls == ["comentarios", "revisoes"]


@pytest.mark.django_db
def test_cleanup_apaga_leituras_antigas_e_pode_rodar_de_novo():
    article = ArticleFactory()
    today = timezone.localdate()
    ArticleRead.objects.create(article=article, viewer_key="a" * 64, day=today - timedelta(91))
    ArticleRead.objects.create(article=article, viewer_key="b" * 64, day=today)

    first = tasks.cleanup(timestamp=0)
    second = tasks.cleanup(timestamp=0)

    assert first["leituras"] == 1
    assert second == {
        "leituras": 0,
        "comentarios_rejeitados": 0,
        "comentarios_sem_dados_tecnicos": 0,
    }
    assert ArticleRead.objects.count() == 1


def test_batimento_devolve_o_horario_agendado():
    assert tasks.heartbeat(timestamp=0) == "1970-01-01T00:00:00+00:00"


# --- o Procrastinate enfileira e executa ---


@pytest.fixture
def in_memory():
    connector = InMemoryConnector()
    with app.replace_connector(connector):
        yield connector


def job_statuses(connector: InMemoryConnector) -> dict[str, str]:
    return {job["task_name"]: job["status"] for job in connector.jobs.values()}


def test_worker_executa_tarefas_enfileiradas(in_memory):
    tasks.heartbeat.defer(timestamp=0)
    tasks.purge_worker_history.defer(timestamp=0)

    app.run_worker(wait=False, install_signal_handlers=False, listen_notify=False)

    assert job_statuses(in_memory) == {
        "heartbeat": "succeeded",
        "purge_worker_history": "succeeded",
    }


def test_mesma_tarefa_nao_empilha_na_fila(in_memory):
    from procrastinate.exceptions import AlreadyEnqueued

    tasks.cleanup.defer(timestamp=0)
    with pytest.raises(AlreadyEnqueued):
        tasks.cleanup.defer(timestamp=1)
