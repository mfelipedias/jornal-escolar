from typing import Any

from django.core.management.base import BaseCommand

from apps.editorial import services


class Command(BaseCommand):
    help = (
        "Avisa revisor e autores, no sino do painel, das revisões sem movimento há mais de "
        "5 dias (docs/04). Pode rodar quantas vezes quiser: cada pessoa recebe um aviso por "
        "revisão parada. O worker roda isto todo dia às 7h10 (apps/core/tasks.py)."
    )

    def handle(self, *args: Any, **options: Any) -> None:
        sent = services.remind_stale_reviews()
        self.stdout.write(self.style.SUCCESS(f"Avisos de revisão parada: {sent}."))
