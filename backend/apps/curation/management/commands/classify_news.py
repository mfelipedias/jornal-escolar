from datetime import timedelta
from typing import Any

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.curation import services


class Command(BaseCommand):
    help = (
        "Classifica de novo as notícias guardadas por tópico e disciplina (docs/21). Use depois "
        "de mudar palavras-chave ou padrões de fonte, se não quiser esperar o worker."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument("--dias", type=int, help="Só as notícias coletadas nos últimos N dias.")

    def handle(self, *args: Any, **options: Any) -> None:
        since = None
        if options["dias"]:
            since = timezone.now() - timedelta(days=options["dias"])
        total, classified = services.reclassify_items(since)
        self.stdout.write(
            self.style.SUCCESS(
                f"{total} notícia(s) classificada(s); {classified} com tópico ou disciplina."
            )
        )
