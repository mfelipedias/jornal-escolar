from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from apps.accounts import privacy, services


class Command(BaseCommand):
    help = "Exporta os dados de uma conta da equipe em JSON ou ZIP (docs/23, docs/18)."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("email", help="E-mail da conta")
        parser.add_argument("--zip", action="store_true", help="ZIP com o JSON e a foto")
        parser.add_argument(
            "--output", help="Arquivo de saída. Sem ele, o JSON sai na tela (ZIP exige arquivo)."
        )

    def handle(self, *args: Any, **options: Any) -> None:
        user = services.find_staff_account(options["email"])
        if user is None:
            raise CommandError("Nenhuma conta com esse e-mail.")
        fmt = "zip" if options["zip"] else "json"
        if fmt == "zip" and not options["output"]:
            raise CommandError("Para ZIP, informe o arquivo com --output.")
        content, _, _ = privacy.export_for(None, user, fmt=fmt)
        if not options["output"]:
            self.stdout.write(content.decode("utf-8"))
            return
        path = Path(options["output"])
        path.write_bytes(content)
        self.stdout.write(self.style.SUCCESS(f"Dados de {user.public_name} salvos em {path}."))
