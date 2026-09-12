from typing import Any

from django.core.management.base import BaseCommand

from apps.taxonomy.services import seed_taxonomy


class Command(BaseCommand):
    help = (
        "Cria áreas, disciplinas, tópicos e tipos de publicação iniciais. "
        "Pode ser rodado várias vezes: só cria o que falta e não altera o que já existe."
    )

    def handle(self, *args: Any, **options: Any) -> None:
        result = seed_taxonomy()
        for key in ("áreas", "disciplinas", "tipos", "tópicos"):
            created = result.created.get(key, 0)
            existing = result.existing.get(key, 0)
            self.stdout.write(f"{key.capitalize()}: {created} criados, {existing} já existiam")
        self.stdout.write(self.style.SUCCESS("Taxonomia pronta."))
