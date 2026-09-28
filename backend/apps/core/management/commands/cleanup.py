from typing import Any

from django.core.management.base import BaseCommand

from apps.accounts import signup
from apps.curation import services as curation
from apps.engagement import services as engagement


class Command(BaseCommand):
    help = (
        "Apaga dados que já cumpriram o prazo (docs/18, docs/20): registros diários de leitura "
        "com mais de 90 dias (o total de cada publicação continua), comentários rejeitados há "
        "mais de 30 dias, o hash do IP e o código anônimo dos comentários com mais de 30 dias e "
        "as notícias coletadas há mais de 60 dias (docs/21) e os códigos enviados por e-mail "
        "vencidos há mais de 7 dias. "
        "Pode rodar quantas vezes quiser; o worker roda isto todo dia às 4h30 (apps/core/tasks.py)."
    )

    def handle(self, *args: Any, **options: Any) -> None:
        reads = engagement.purge_old_reads()
        self.stdout.write(self.style.SUCCESS(f"Leituras antigas apagadas: {reads}."))
        rejected, cleared = engagement.purge_old_comments()
        self.stdout.write(self.style.SUCCESS(f"Comentários rejeitados apagados: {rejected}."))
        self.stdout.write(
            self.style.SUCCESS(f"Comentários com dados técnicos removidos: {cleared}.")
        )
        news = curation.purge_old_items()
        self.stdout.write(self.style.SUCCESS(f"Notícias coletadas antigas apagadas: {news}."))
        codes = signup.purge_old_codes()
        self.stdout.write(self.style.SUCCESS(f"Códigos de e-mail vencidos apagados: {codes}."))
