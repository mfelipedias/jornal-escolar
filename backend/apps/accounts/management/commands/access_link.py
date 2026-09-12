from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.utils import timezone

from apps.accounts import services
from apps.accounts.models import AccessLink


class Command(BaseCommand):
    help = "Gera um link de acesso (criar ou redefinir senha) para uma conta já cadastrada."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("email", help="E-mail da conta")
        parser.add_argument(
            "--purpose",
            choices=AccessLink.Purpose.values,
            help="Padrão: primeiro acesso se a conta não tem senha; senão, redefinir senha.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        user = services.find_staff_account(options["email"])
        if user is None:
            raise CommandError("Nenhuma conta com esse e-mail. Cadastre a pessoa no admin antes.")
        try:
            link = services.create_access_link(user, purpose=options["purpose"])
        except services.AccessLinkError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(f"{link.get_purpose_display()} para {user.public_name}:")
        self.stdout.write(self.style.SUCCESS(services.access_link_url(link)))
        expires = timezone.localtime(link.expires_at)
        self.stdout.write(f"Vale até {expires:%d/%m/%Y %H:%M} e só pode ser usado uma vez.")
