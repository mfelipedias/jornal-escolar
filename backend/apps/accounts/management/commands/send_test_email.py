from typing import Any

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = (
        "Envia um e-mail de teste para conferir a configuração do Gmail (docs/35). "
        "Uso: send_test_email voce@exemplo.com"
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument("destino", help="Endereço que vai receber o teste.")

    def handle(self, *args: Any, **options: Any) -> None:
        if not settings.EMAIL_CONFIGURED:
            raise CommandError(
                "E-mail não configurado: preencha EMAIL_HOST_USER e EMAIL_HOST_PASSWORD no "
                "infra/env/.env (docs/35)."
            )
        try:
            send_mail(
                "Teste do Jornal Escolar",
                "Se você recebeu este e-mail, o envio de códigos do jornal está funcionando.\n",
                None,
                [options["destino"]],
            )
        except Exception as exc:  # o Gmail explica o problema na mensagem
            raise CommandError(f"Não foi possível enviar: {exc}") from exc
        self.stdout.write(self.style.SUCCESS(f"E-mail de teste enviado para {options['destino']}."))
