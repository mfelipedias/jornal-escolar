from typing import Any

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError, CommandParser

from apps.accounts import privacy, services


class Command(BaseCommand):
    help = (
        "Anonimiza uma conta da equipe: apaga nome, e-mail, foto e perfil e desativa o login. "
        "Os créditos viram 'Ex-membro da equipe'. Não dá para desfazer (docs/23)."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("email", help="E-mail da conta")
        parser.add_argument("--yes", action="store_true", help="Não pedir confirmação")

    def handle(self, *args: Any, **options: Any) -> None:
        user = services.find_staff_account(options["email"])
        if user is None:
            raise CommandError("Nenhuma conta com esse e-mail.")
        if not options["yes"]:
            answer = input(f"Anonimizar {user.public_name} <{user.email}>? Digite 'sim': ")
            if answer.strip().lower() != "sim":
                raise CommandError("Cancelado.")
        try:
            privacy.anonymize_user(None, user)
        except ValidationError as exc:
            raise CommandError(" ".join(exc.messages)) from exc
        self.stdout.write(self.style.SUCCESS("Conta anonimizada."))
