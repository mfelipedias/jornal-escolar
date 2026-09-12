from django.apps import AppConfig


class AccountsConfig(AppConfig):
    name = "apps.accounts"
    label = "accounts"
    verbose_name = "Contas"

    def ready(self) -> None:
        from . import signals  # noqa: F401
