from typing import Any

from django.core.management.base import BaseCommand, CommandError

from apps.core import demo


class Command(BaseCommand):
    help = (
        "SÓ PARA DESENVOLVIMENTO: cria equipe fictícia, publicações com capas, agenda e "
        "destaques para ver o site cheio. Pode ser rodado várias vezes: só cria o que falta. "
        "Recusa rodar sem DEBUG=True (produção). Para apagar tudo: seed_demo --apagar"
    )

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--apagar",
            action="store_true",
            help="Apaga as pessoas fictícias, as publicações delas e as imagens geradas.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        try:
            if options["apagar"]:
                counts = demo.remove_demo()
                for key, value in counts.items():
                    self.stdout.write(f"{key.capitalize()} apagadas: {value}")
                self.stdout.write(self.style.SUCCESS("Dados de demonstração apagados."))
                return
            result = demo.seed_demo()
        except demo.DemoNotAllowed as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(f"Pessoas criadas: {result.people}")
        self.stdout.write(f"Publicações criadas: {result.articles}")
        self.stdout.write(f"Imagens geradas: {result.images}")
        if result.featured:
            self.stdout.write(f"Destaques da home definidos: {len(result.featured)}")
        self.stdout.write(
            self.style.SUCCESS(
                "Demonstração pronta. As contas fictícias não têm senha. "
                "Para apagar: python manage.py seed_demo --apagar"
            )
        )
