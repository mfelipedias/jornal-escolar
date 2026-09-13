from dataclasses import dataclass, field

from django.db import transaction
from django.utils.text import slugify

from . import seed_data
from .models import ArticleType, Discipline, KnowledgeArea, Topic


@dataclass
class SeedResult:
    created: dict[str, int] = field(default_factory=dict)
    existing: dict[str, int] = field(default_factory=dict)

    def count(self, key: str, *, was_created: bool) -> None:
        bucket = self.created if was_created else self.existing
        bucket[key] = bucket.get(key, 0) + 1


@transaction.atomic
def seed_taxonomy() -> SeedResult:
    """Cria a taxonomia inicial da escola.

    Idempotente e conservador: procura cada item pelo slug e só cria o que falta.
    Nunca altera itens existentes, para não desfazer edições feitas no Django Admin.
    """
    result = SeedResult()

    for area_order, area_data in enumerate(seed_data.AREAS, start=1):
        area, created = KnowledgeArea.objects.get_or_create(
            slug=area_data["slug"],
            defaults={
                "name": area_data["name"],
                "short_name": area_data.get("short_name", ""),
                "color": area_data["color"],
                "description": area_data["description"],
                "order": area_order * 10,
            },
        )
        result.count("áreas", was_created=created)

        for discipline_order, discipline_name in enumerate(area_data["disciplines"], start=1):
            _, created = Discipline.objects.get_or_create(
                slug=slugify(discipline_name),
                defaults={
                    "name": discipline_name,
                    "area": area,
                    "order": discipline_order * 10,
                },
            )
            result.count("disciplinas", was_created=created)

    for type_order, type_data in enumerate(seed_data.ARTICLE_TYPES, start=1):
        _, created = ArticleType.objects.get_or_create(
            slug=slugify(type_data["name"]),
            defaults={
                "name": type_data["name"],
                "description": type_data["description"],
                "has_event_date": type_data.get("has_event_date", False),
                "order": type_order * 10,
            },
        )
        result.count("tipos", was_created=created)

    for topic_name, keywords, discipline_names in seed_data.TOPICS:
        topic, created = Topic.objects.get_or_create(
            slug=slugify(topic_name),
            defaults={"name": topic_name, "keywords": keywords},
        )
        if created:
            slugs = [slugify(name) for name in discipline_names]
            topic.disciplines.set(Discipline.objects.filter(slug__in=slugs))
        result.count("tópicos", was_created=created)

    return result
