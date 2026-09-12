from django.apps import AppConfig


class PublicationsConfig(AppConfig):
    name = "apps.publications"
    label = "publications"
    verbose_name = "Publicações"

    def ready(self) -> None:
        from . import signals  # noqa: F401
