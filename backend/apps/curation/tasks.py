"""Tarefas do worker para a curadoria de notícias (E45; docs/21, "Pipeline de coleta").

A cada 30 minutos, fetch_news enfileira uma tarefa fetch_news_source para cada fonte ativa cujo
intervalo (padrão de 2 horas, ajustável por fonte no admin) já passou. Cada fonte vira uma
tarefa separada: um feed lento ou quebrado não atrasa os outros.
"""

from procrastinate.contrib.django import app
from procrastinate.exceptions import AlreadyEnqueued

from apps.core.tasks import _run

from . import services
from .models import NewsSource


@app.periodic(cron="5,35 * * * *")
@app.task(name="fetch_news", queueing_lock="fetch_news")
def fetch_news(timestamp: int) -> int:
    def job() -> int:
        queued = 0
        for source in services.due_sources():
            try:
                fetch_news_source.configure(queueing_lock=f"news-source-{source.pk}").defer(
                    source_id=source.pk
                )
            except AlreadyEnqueued:
                continue
            queued += 1
        return queued

    return _run("fetch_news", timestamp, job)


@app.task(name="fetch_news_source")
def fetch_news_source(source_id: int) -> str:
    def job() -> str:
        source = NewsSource.objects.filter(pk=source_id, is_active=True).first()
        if source is None:
            return "fonte inexistente ou desativada"
        return services.fetch_source(source).describe()

    return _run("fetch_news_source", None, job)
