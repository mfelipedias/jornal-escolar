from django.db import models


class TimeStampedModel(models.Model):
    """Base das tabelas de negócio: created_at e updated_at (docs/06, "Princípios")."""

    created_at = models.DateTimeField("criado em", auto_now_add=True)
    updated_at = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        abstract = True
