from typing import Any

from django.core.management.base import BaseCommand, CommandError

from apps.curation import services
from apps.curation.models import NewsSource


class Command(BaseCommand):
    help = (
        "Coleta notícias das fontes ativas agora, sem esperar o worker (docs/21). "
        "Sem opções, busca todas as fontes ativas."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--fonte", type=int, action="append", dest="ids", help="Só esta fonte (id)."
        )
        parser.add_argument(
            "--vencidas",
            action="store_true",
            help="Só as fontes cujo intervalo entre coletas já passou (o que o worker faz).",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        if options["ids"]:
            sources = list(NewsSource.objects.filter(pk__in=options["ids"]))
            if not sources:
                raise CommandError("Nenhuma fonte com esse id.")
        elif options["vencidas"]:
            sources = services.due_sources()
        else:
            sources = list(NewsSource.objects.filter(is_active=True))
        results = services.fetch_sources(sources)
        for result in results:
            style = self.style.SUCCESS if result.ok else self.style.ERROR
            self.stdout.write(style(result.describe()))
        errors = sum(not result.ok for result in results)
        new = sum(result.new for result in results)
        self.stdout.write(f"{len(results)} fonte(s), {new} notícia(s) nova(s), {errors} com erro.")
