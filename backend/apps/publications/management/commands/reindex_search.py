from typing import Any

from django.core.management.base import BaseCommand

from apps.publications import search


class Command(BaseCommand):
    help = (
        "Refaz o índice de busca de todas as publicações (docs/19). Pode rodar quantas vezes "
        "quiser: útil depois de restaurar um backup ou mudar a configuração de busca."
    )

    def handle(self, *args: Any, **options: Any) -> None:
        total = search.reindex_all()
        self.stdout.write(self.style.SUCCESS(f"Índice de busca refeito: {total} publicação(ões)."))
