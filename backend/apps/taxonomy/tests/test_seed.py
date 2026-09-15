import pytest
from django.core.management import call_command

from apps.taxonomy import seed_data
from apps.taxonomy.models import ArticleType, Discipline, KnowledgeArea, Topic
from apps.taxonomy.services import seed_taxonomy

pytestmark = pytest.mark.django_db

EXPECTED_DISCIPLINES = sum(len(area["disciplines"]) for area in seed_data.AREAS)


def counts() -> tuple[int, int, int, int]:
    return (
        KnowledgeArea.objects.count(),
        Discipline.objects.count(),
        Topic.objects.count(),
        ArticleType.objects.count(),
    )


def test_seed_creates_school_taxonomy():
    seed_taxonomy()

    assert counts() == (8, 31, 30, 10)
    assert EXPECTED_DISCIPLINES == 31


def test_seed_is_idempotent():
    seed_taxonomy()
    second = seed_taxonomy()

    assert counts() == (8, 31, 30, 10)
    assert second.created == {}
    assert second.existing == {"áreas": 8, "disciplinas": 31, "tipos": 10, "tópicos": 30}


def test_seed_does_not_overwrite_admin_edits():
    seed_taxonomy()
    area = KnowledgeArea.objects.get(slug="linguagens")
    area.name = "Linguagens (editado)"
    area.color = "magenta"
    area.save()

    seed_taxonomy()

    area.refresh_from_db()
    assert area.name == "Linguagens (editado)"
    assert area.color == "magenta"


def test_seed_recreates_only_missing_items():
    seed_taxonomy()
    Topic.objects.get(slug="robotica").delete()

    result = seed_taxonomy()

    assert result.created == {"tópicos": 1}
    assert Topic.objects.filter(slug="robotica").exists()


def test_seed_details():
    seed_taxonomy()

    physics = Discipline.objects.get(slug="fisica")
    assert physics.area.slug == "ciencias-da-natureza"
    assert KnowledgeArea.objects.get(slug="matematica").color == "azul"
    assert ArticleType.objects.get(slug="evento").has_event_date
    assert not ArticleType.objects.get(slug="noticia").has_event_date
    ai = Topic.objects.get(slug="inteligencia-artificial")
    assert "IA" in ai.keywords
    assert set(ai.disciplines.values_list("slug", flat=True)) == {
        "tecnologia-e-inovacao",
        "matematica",
        "filosofia",
    }


def test_every_topic_discipline_exists_in_seed():
    names = {name for area in seed_data.AREAS for name in area["disciplines"]}

    for topic_name, _, discipline_names in seed_data.TOPICS:
        missing = set(discipline_names) - names
        assert not missing, f"{topic_name}: {missing}"


def test_management_command_output(capsys):
    call_command("seed_taxonomy")

    output = capsys.readouterr().out
    assert "Áreas: 8 criados, 0 já existiam" in output
    assert "Taxonomia pronta." in output
