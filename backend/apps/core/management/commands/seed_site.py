from typing import Any

from django.core.management.base import BaseCommand

from apps.core.services import seed_site


class Command(BaseCommand):
    help = (
        "Cria as configurações do site e as páginas Sobre, Como participar e Privacidade. "
        "Pode ser rodado várias vezes: só cria o que falta."
    )

    def handle(self, *args: Any, **options: Any) -> None:
        for key, created in seed_site().items():
            self.stdout.write(f"{key.capitalize()}: {created} criadas")
        self.stdout.write(
            self.style.SUCCESS("Site pronto. A página de Privacidade está despublicada.")
        )
