from typing import Any

from django.core.management.base import BaseCommand

from apps.engagement import services as engagement


class Command(BaseCommand):
    help = (
        "Apaga dados que já cumpriram o prazo (docs/18). Por enquanto: registros diários de "
        "leitura com mais de 90 dias (o total de cada publicação continua). Pode rodar quantas "
        "vezes quiser; o agendamento mensal chega com o worker (E44)."
    )

    def handle(self, *args: Any, **options: Any) -> None:
        reads = engagement.purge_old_reads()
        self.stdout.write(self.style.SUCCESS(f"Leituras antigas apagadas: {reads}."))
