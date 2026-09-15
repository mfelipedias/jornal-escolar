"""Tela de revisão e aba "Revisões" (E31, docs/15, docs/17).

Aceite: sugerir alterações sem comentário é bloqueado. Desde a E32 vale ao menos um
comentário editorial aberto (ou a nota, que vira um comentário geral); o bloqueio está no
serviço e na tela. Os comentários em si são testados em test_review_comments.py.
"""

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse

from apps.dashboard.menu import menu_items
from apps.editorial import selectors
from apps.editorial.models import Notification
from apps.publications import services
from apps.publications.models import Article
from tests.factories import ArticleFactory, UserFactory

pytestmark = pytest.mark.django_db

S = Article.Status


@pytest.fixture
def author():
    return UserFactory(full_name="Carla Souza")


@pytest.fixture
def reviewer():
    return UserFactory(full_name="Marcos Lima")


@pytest.fixture
def article(author):
    return ArticleFactory(ready=True, author=author, created_by=author, title="Feira de Ciências")


def review_url(article):
    return reverse("editorial:review", args=[article.pk])


def transition_url(article, action):
    return reverse("publications:transition", args=[article.pk, action])


def send_to_review(article, author, reviewer, **kwargs):
    kwargs.setdefault("note", "Olha a introdução")
    return services.request_review(author, article, reviewer, **kwargs)


def flash(response):
    return [str(m) for m in response.wsgi_request._messages]


# --- aceite: sugerir alterações sem comentário ---


@pytest.mark.parametrize("note", ["", "   ", "\n\t"])
def test_service_blocks_request_changes_without_comment(article, author, reviewer, note):
    send_to_review(article, author, reviewer)

    with pytest.raises(ValidationError):
        services.request_changes(reviewer, article, note)

    assert Article.objects.get(pk=article.pk).status == S.IN_REVIEW
    assert not Notification.objects.filter(kind=Notification.Kind.CHANGES_REQUESTED).exists()


def test_screen_requires_comment_to_request_changes(client, article, author, reviewer):
    send_to_review(article, author, reviewer)
    client.force_login(reviewer)

    html = client.get(review_url(article)).content.decode()
    form = html.split('id="review-changes"')[1].split("</form>")[0]

    assert transition_url(article, "request_changes") in form
    assert ':disabled="!note.trim() && !openCount"' in form
    assert "Deixe ao menos um comentário" in form


def test_screen_post_without_comment_stays_in_review_with_error(client, article, author, reviewer):
    send_to_review(article, author, reviewer)
    client.force_login(reviewer)

    response = client.post(
        transition_url(article, "request_changes"),
        {"note": "  ", "next": review_url(article)},
    )

    assert response.status_code == 302
    assert response["Location"] == review_url(article)
    assert Article.objects.get(pk=article.pk).status == S.IN_REVIEW
    assert flash(response) == [services.CHANGES_WITHOUT_COMMENT]
    page = client.get(response["Location"]).content.decode()
    assert services.CHANGES_WITHOUT_COMMENT in page


def test_request_changes_with_comment_from_screen(client, article, author, reviewer):
    send_to_review(article, author, reviewer)
    client.force_login(reviewer)

    response = client.post(
        transition_url(article, "request_changes"),
        {"note": "Faltou citar a fonte.", "next": review_url(article)},
        follow=True,
    )

    assert Article.objects.get(pk=article.pk).status == S.CHANGES_REQUESTED
    html = response.content.decode()
    assert "Marcos Lima</span> sugeriu alterações" in html
    assert "Faltou citar a fonte." in html
    assert 'id="review-changes"' not in html  # sem decisão fora de "em revisão"


# --- acesso e modos da tela ---


def test_reviewer_sees_text_decisions_checklist_and_history(client, article, author, reviewer):
    send_to_review(article, author, reviewer, can_publish=True)
    client.force_login(reviewer)

    response = client.get(review_url(article))

    assert response.status_code == 200
    html = response.content.decode()
    assert article.body_html in html
    assert "Olha a introdução" in html
    assert "Autores:</span> Carla Souza" in html
    for label in ("Editar texto", "Sugerir alterações", "Aprovar e publicar", "Recusar revisão"):
        assert label in html
    assert "Tudo pronto para publicar." in html
    assert "Carla Souza</span> pediu revisão" in html
    assert "Carla Souza</span> escolheu quem revisa" in html
    assert "Ver versões" not in html  # só editor+


def test_approve_and_publish_hidden_without_author_permission(client, article, author, reviewer):
    send_to_review(article, author, reviewer, can_publish=False)
    client.force_login(reviewer)

    html = client.get(review_url(article)).content.decode()

    assert "Aprovar e devolver aos autores" in html
    assert "Aprovar e publicar" not in html


def test_author_sees_screen_without_decisions(client, article, author, reviewer):
    send_to_review(article, author, reviewer)
    client.force_login(author)

    html = client.get(review_url(article)).content.decode()

    assert "Abrir no editor" in html
    for form_id in ("review-changes", "review-approve", "review-decline", "review-archive"):
        assert f'id="{form_id}"' not in html


def test_editor_decides_archives_with_note_and_sees_versions(
    client, article, author, reviewer, editor_user
):
    send_to_review(article, author, reviewer)
    client.force_login(editor_user)

    html = client.get(review_url(article)).content.decode()

    assert 'id="review-approve"' in html
    assert "Aprovar e publicar" in html
    assert 'id="review-decline"' not in html  # recusar é só do revisor designado
    assert 'id="review-archive"' in html
    assert "Ver versões (1)" in html
    assert "Envio para revisão" in html


def test_others_cannot_open_review_screen(client, article, author, reviewer):
    send_to_review(article, author, reviewer)

    client.force_login(UserFactory())
    assert client.get(review_url(article)).status_code == 403
    client.logout()
    assert client.get(review_url(article)).status_code == 302


def test_approve_from_screen_returns_to_screen_with_seal(client, article, author, reviewer):
    send_to_review(article, author, reviewer)
    client.force_login(reviewer)

    response = client.post(
        transition_url(article, "approve"), {"note": "Ótimo!", "next": review_url(article)}
    )

    assert response["Location"] == review_url(article)
    assert Article.objects.get(pk=article.pk).status == S.DRAFT
    html = client.get(review_url(article)).content.decode()
    assert "Revisado por Marcos Lima" in html
    assert "Marcos Lima</span> aprovou a revisão" in html


def test_decline_from_screen_goes_back_to_queue(client, article, author, reviewer):
    send_to_review(article, author, reviewer)
    client.force_login(reviewer)

    response = client.post(
        transition_url(article, "decline_review"),
        {"note": "Estou sem tempo", "next": reverse("editorial:queue")},
    )

    assert response["Location"] == reverse("editorial:queue")
    assert client.get(review_url(article)).status_code == 403  # saiu da revisão


def test_editor_actions_link_to_review_screen(client, article, author, reviewer):
    send_to_review(article, author, reviewer)
    client.force_login(reviewer)

    html = client.get(reverse("publications:edit", args=[article.pk])).content.decode()

    assert f'href="{review_url(article)}"' in html


# --- histórico legível ---


def test_history_entries_describe_the_flow(article, author, reviewer):
    send_to_review(article, author, reviewer)
    services.request_changes(reviewer, article, "Ajuste a tabela.")
    send_to_review(article, author, reviewer, note="")
    services.approve(reviewer, article)
    services.publish(author, article)

    texts = [f"{e.actor} {e.text}" for e in selectors.history_entries(article)]

    assert texts == [
        "Carla Souza pediu revisão",
        "Carla Souza escolheu quem revisa",
        "Marcos Lima sugeriu alterações",
        "Carla Souza reenviou para revisão",
        "Carla Souza escolheu quem revisa",
        "Marcos Lima voltou o texto a rascunho",
        "Marcos Lima aprovou a revisão",
        "Carla Souza publicou",
    ]


# --- aba "Revisões" ---


def test_queue_tabs(client, article, author, reviewer, editor_user):
    other = ArticleFactory(ready=True, author=reviewer, created_by=reviewer, title="Horta")
    send_to_review(article, author, reviewer, can_publish=True)
    send_to_review(other, reviewer, author)

    client.force_login(reviewer)
    response = client.get(reverse("editorial:queue"))
    assert [i["article"] for i in response.context["items"]] == [article]
    html = response.content.decode()
    assert "Olha a introdução" in html
    assert "Pode publicar pelos autores" in html
    assert f'href="{review_url(article)}"' in html
    assert "Todas em revisão" not in html

    response = client.get(reverse("editorial:queue"), {"aba": "que-eu-pedi"})
    assert [i["article"] for i in response.context["items"]] == [other]

    # Aba de editor pedida por quem não é editor volta para "Pedidas a mim".
    response = client.get(reverse("editorial:queue"), {"aba": "todas"})
    assert response.context["current"] == "pedidas-a-mim"

    client.force_login(editor_user)
    response = client.get(reverse("editorial:queue"), {"aba": "todas"})
    assert {i["article"] for i in response.context["items"]} == {article, other}
    assert [i["article"] for i in client.get(reverse("editorial:queue")).context["items"]] == []


def test_queue_only_lists_articles_in_review(client, article, author, reviewer):
    send_to_review(article, author, reviewer)
    services.request_changes(reviewer, article, "Ajuste.")
    client.force_login(reviewer)

    response = client.get(reverse("editorial:queue"))

    assert response.context["items"] == []
    assert "Nenhuma revisão pedida a você" in response.content.decode()


def test_menu_shows_reviews_with_counter(client, article, author, reviewer):
    assert menu_items(reviewer)[3].key == "reviews"
    assert menu_items(reviewer)[3].count == 0

    send_to_review(article, author, reviewer)

    item = next(i for i in menu_items(reviewer, "editorial:review") if i.key == "reviews")
    assert item.count == 1
    assert item.active
    client.force_login(reviewer)
    html = client.get(reverse("dashboard:home")).content.decode()
    assert f'href="{reverse("editorial:queue")}"' in html
    assert '1<span class="sr-only"> pendentes</span>' in html


# --- notificações apontam para a tela de revisão ---


def test_review_notifications_open_review_screen(article, author, reviewer):
    send_to_review(article, author, reviewer)
    services.update_article(author, article, title="Feira de Ciências 2026")
    services.request_changes(reviewer, article, "Ajuste.")

    requested = Notification.objects.get(user=reviewer, kind=Notification.Kind.REVIEW_REQUESTED)
    edited = Notification.objects.get(user=reviewer, kind=Notification.Kind.EDITED_BY_OTHER)
    changes = Notification.objects.get(user=author, kind=Notification.Kind.CHANGES_REQUESTED)
    assert requested.url == review_url(article)
    assert edited.url == review_url(article)
    assert changes.url == review_url(article)


def test_cancelled_review_notification_opens_queue(article, author, reviewer):
    send_to_review(article, author, reviewer)
    services.cancel_review(author, article)

    notice = Notification.objects.get(user=reviewer, kind=Notification.Kind.SYSTEM)
    assert notice.url == reverse("editorial:queue")
