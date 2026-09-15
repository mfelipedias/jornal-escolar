from django.apps import AppConfig


class EngagementConfig(AppConfig):
    name = "apps.engagement"
    label = "engagement"
    verbose_name = "Participação dos leitores"

    def ready(self) -> None:
        from . import signals  # noqa: F401
