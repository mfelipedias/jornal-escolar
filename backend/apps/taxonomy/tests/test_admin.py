import pytest
from django.urls import reverse

from apps.taxonomy.admin import TopicForm
from apps.taxonomy.models import KnowledgeArea, Topic
from apps.taxonomy.services import seed_taxonomy

pytestmark = pytest.mark.django_db

MODELS = ["knowledgearea", "discipline", "topic", "articletype"]


@pytest.fixture
def seeded():
    seed_taxonomy()


@pytest.mark.parametrize("model", MODELS)
def test_changelist_and_add_pages_render(admin_client, seeded, model):
    assert admin_client.get(reverse(f"admin:taxonomy_{model}_changelist")).status_code == 200
    assert admin_client.get(reverse(f"admin:taxonomy_{model}_add")).status_code == 200


def test_area_change_page_shows_disciplines_inline(admin_client, seeded):
    area = KnowledgeArea.objects.get(slug="ciencias-da-natureza")

    response = admin_client.get(reverse("admin:taxonomy_knowledgearea_change", args=[area.pk]))

    assert response.status_code == 200
    assert "Física" in response.content.decode()


def test_topic_form_parses_comma_separated_keywords():
    form = TopicForm(
        data={
            "name": "Robótica",
            "slug": "robotica",
            "is_active": "on",
            "keywords": " robótica, Arduino ,, arduino,  sensores   de toque ",
        }
    )

    assert form.is_valid(), form.errors
    assert form.cleaned_data["keywords"] == ["robótica", "Arduino", "sensores de toque"]


def test_topic_form_shows_keywords_as_text():
    topic = Topic.objects.create(name="Energia", keywords=["solar", "eólica"])

    form = TopicForm(instance=topic)

    assert form.initial["keywords"] == "solar, eólica"


def test_approve_topics_action(admin_client):
    pending = Topic.objects.create(name="Sugestão", is_active=False)

    response = admin_client.post(
        reverse("admin:taxonomy_topic_changelist"),
        {"action": "approve_topics", "_selected_action": [pending.pk]},
    )

    assert response.status_code == 302
    pending.refresh_from_db()
    assert pending.is_active


def test_non_admin_cannot_edit_taxonomy(client, editor_user):
    client.force_login(editor_user)

    response = client.get(reverse("admin:taxonomy_knowledgearea_changelist"))

    assert response.status_code == 302
