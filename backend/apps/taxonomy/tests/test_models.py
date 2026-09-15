import pytest
from django.db.models import ProtectedError

from apps.taxonomy.models import AREA_COLOR_CLASSES, AreaColor, Discipline, KnowledgeArea, Topic

pytestmark = pytest.mark.django_db


def test_slug_is_generated_from_name_without_accents():
    area = KnowledgeArea.objects.create(name="Ciências da Natureza")
    discipline = Discipline.objects.create(name="Física", area=area)

    assert area.slug == "ciencias-da-natureza"
    assert discipline.slug == "fisica"


def test_explicit_slug_is_kept():
    area = KnowledgeArea.objects.create(name="Matemática e suas Tecnologias", slug="matematica")

    assert area.slug == "matematica"


def test_every_area_color_has_tailwind_classes():
    assert set(AREA_COLOR_CLASSES) == set(AreaColor.values)
    for classes in AREA_COLOR_CLASSES.values():
        assert set(classes) == {
            "text", "soft_bg", "solid_bg", "border", "bright_bg", "from_soft", "on_bright"
        }  # fmt: skip
        assert classes["on_bright"] in {"text-ink", "text-white"}


def test_area_color_classes():
    area = KnowledgeArea(name="Linguagens", color=AreaColor.CORAL)

    assert area.color_classes["soft_bg"] == "bg-area-coral-soft"


def test_areas_are_ordered_by_order_then_name():
    KnowledgeArea.objects.create(name="B", order=2)
    KnowledgeArea.objects.create(name="A", order=2)
    KnowledgeArea.objects.create(name="C", order=1)

    assert [a.name for a in KnowledgeArea.objects.all()] == ["C", "A", "B"]


def test_area_with_disciplines_cannot_be_deleted():
    area = KnowledgeArea.objects.create(name="Humanas")
    Discipline.objects.create(name="História", area=area)

    with pytest.raises(ProtectedError):
        area.delete()


def test_topic_keywords_default_to_empty_list():
    topic = Topic.objects.create(name="Robótica")

    assert topic.keywords == []
    assert topic.created_at is not None
