from typing import Any

from django.core.management.base import BaseCommand

from apps.curation.services import seed_sources


class Command(BaseCommand):
    help = (
        "Cadastra as fontes de notícias sugeridas em docs/21. Pode ser rodado várias vezes: "
        "só cria as que faltam e não altera as que já existem."
    )

    def handle(self, *args: Any, **options: Any) -> None:
        result = seed_sources()
        self.stdout.write(f"Fontes: {result.created} criadas, {result.existing} já existiam")
        self.stdout.write(self.style.SUCCESS("Fontes de notícias prontas."))
