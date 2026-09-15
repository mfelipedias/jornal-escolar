from typing import Any

from django.core.management.base import BaseCommand

from apps.engagement import services


class Command(BaseCommand):
    help = (
        "Avisa os editores, no sino do painel, das publicações com comentários de leitores "
        "aguardando aprovação há mais de 3 dias (docs/04, docs/20). Pode rodar quantas vezes "
        "quiser: cada editor recebe um aviso por publicação até chegar um novo pendente "
        "atrasado. O agendamento diário chega com o worker (E44)."
    )

    def handle(self, *args: Any, **options: Any) -> None:
        sent = services.remind_stale_pending_comments()
        self.stdout.write(self.style.SUCCESS(f"Avisos de comentários pendentes: {sent}."))
