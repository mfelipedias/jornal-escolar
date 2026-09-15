"""Início do painel (E24, docs/15): pendências, rascunhos, publicadas e números.

Aceite: "pendências corretas" num cenário montado com fábricas.
"""

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.dashboard import selectors
from apps.editorial import notifications
from apps.editorial.models import Notification
from apps.publications import services
from apps.publications.models import Article, ArticleContributor
from tests.factories import ArticleFactory, DisciplineFactory, UserFactory, text_doc

pytestmark = pytest.mark.django_db

URL = "/painel/"


@pytest.fixture
def ana():
    return UserFactory(full_name="Ana Autora")


@pytest.fixture
def scenario(ana, editor_user):
    """Ana com rascunhos, publicadas, uma arquivada e avisos gerados pelas regras reais."""
    colleague = UserFactory(full_name="Bruno Colega")
    drafts = [
        ArticleFactory(author=ana, created_by=ana, title=f"Rascunho {i}") for i in range(1, 5)
    ]
    published = []
    for i in range(1, 5):
        article = ArticleFactory(ready=True, author=ana, created_by=ana, title=f"Publicada {i}")
        services.publish(ana, article)
        published.append(article)
    archived = ArticleFactory(ready=True, author=ana, created_by=ana, title="Velha")
    services.archive(ana, archived)
    # Texto de outra pessoa: não pode aparecer para Ana.
    ArticleFactory(author=colleague, created_by=colleague, title="Do Bruno")

    # Editor mexe no texto de Ana: aviso "editou" (regra da E17).
    services.update_article(editor_user, drafts[0], subtitle="Revisto pela coordenação")
    # Colega de outro texto publica algo em que Ana é coautora: aviso "publicou".
    shared = ArticleFactory(ready=True, author=colleague, created_by=colleague, title="Juntos")
    ArticleContributor.objects.create(
        article=shared, user=ana, display_name=ana.public_name, role="coauthor"
    )
    services.publish(colleague, shared)
    # Aviso já lido não é pendência.
    old = notifications.notify(ana, Notification.Kind.SYSTEM, "Aviso antigo")
    notifications.mark_read(old)
    return {"drafts": drafts, "published": [*published, shared], "archived": archived}


def test_url_and_login_required(client):
    assert reverse("dashboard:home") == URL
    response = client.get(URL)
    assert response.status_code == 302
    assert reverse("accounts:login") in response.url


def test_pending_items_from_seed(scenario, ana, editor_user):
    items, unread = selectors.pending_items(ana)

    assert unread == 2
    kinds = [item.kind for item in items]
    assert kinds == ["published_by_other", "edited_by_other", "profile"]
    assert f"{editor_user.public_name} editou “Rascunho 1”." in items[1].message
    assert "Bruno Colega publicou “Juntos”." in items[0].message
    assert items[2].message == "Complete seu perfil: falta foto, disciplinas, sobre mim."
    assert items[2].url == reverse("accounts:profile_edit")
    assert all("Aviso antigo" not in item.message for item in items)


def test_home_shows_blocks(client, scenario, ana):
    client.force_login(ana)
    html = client.get(URL).content.decode()

    assert "Pendências" in html
    assert "editou “Rascunho 1”" in html
    assert "Complete seu perfil: falta foto" in html
    # Pendência abre pelo endereço que marca a notificação como lida.
    notification = Notification.objects.get(user=ana, kind="edited_by_other")
    assert reverse("editorial:notification_open", args=[notification.pk]) in html

    # Continuar escrevendo: 3 rascunhos mais recentes (o editado pelo editor primeiro).
    drafts = selectors.recent_drafts(ana)
    assert [a.title for a in drafts] == ["Rascunho 1", "Rascunho 4", "Rascunho 3"]
    for article in drafts:
        assert reverse("publications:edit", args=[article.pk]) in html
    assert "Rascunho 2" not in html

    # Últimas publicadas: 3, mais recente primeiro.
    assert [a.title for a in selectors.recent_published(ana)] == [
        "Juntos",
        "Publicada 4",
        "Publicada 3",
    ]
    assert "Publicada 1" not in html
    assert "Do Bruno" not in html
    assert "Velha" not in html

    stats = selectors.stats(ana)
    assert stats == {"published": 5, "drafts": 4, "reads_30d": 0}


def test_pending_hidden_when_nothing_to_do(client, ana):
    services_profile_complete(ana)
    client.force_login(ana)
    html = client.get(URL).content.decode()

    assert selectors.pending_items(ana) == ([], 0)
    assert "Pendências" not in html
    assert "Nenhum rascunho aberto" in html


def test_read_notification_leaves_pending(client, scenario, ana):
    client.force_login(ana)
    notification = Notification.objects.get(user=ana, kind="edited_by_other")
    client.get(reverse("editorial:notification_open", args=[notification.pk]))

    items, unread = selectors.pending_items(ana)
    assert unread == 1
    assert "edited_by_other" not in [item.kind for item in items]


def test_many_unread_link_to_all_notifications(client, ana):
    for i in range(7):
        article = ArticleFactory(author=ana, created_by=ana, title=f"T{i}")
        notifications.notify(ana, Notification.Kind.EDITED_BY_OTHER, f"Aviso {i}", article=article)
    client.force_login(ana)
    html = client.get(URL).content.decode()

    assert html.count('data-kind="edited_by_other"') == selectors.HOME_NOTIFICATIONS
    assert "(mais 2)" in html
    assert reverse("editorial:notifications") in html


def test_collaborator_sees_only_published(ana):
    other = UserFactory()
    draft = ArticleFactory(author=other, created_by=other)
    ArticleContributor.objects.create(
        article=draft, user=ana, display_name=ana.public_name, role="collaborator"
    )
    assert selectors.status_counts(ana)[""] == 0

    draft.body_json = text_doc()
    draft.subtitle = "x"
    draft.save()
    draft.disciplines.add(DisciplineFactory())
    Article.objects.filter(pk=draft.pk).update(
        status=Article.Status.PUBLISHED, published_at=timezone.now()
    )
    assert selectors.status_counts(ana) == {
        "": 1,
        "rascunhos": 0,
        "em-revisao": 0,
        "alteracoes-sugeridas": 0,
        "publicados": 1,
        "arquivados": 0,
    }


def services_profile_complete(user):
    """Perfil sem pendências: foto, disciplina e bio (sem enviar imagem de verdade)."""
    from apps.publications.models import MediaAsset

    asset = MediaAsset.objects.create(
        file="media/x.jpg", width=10, height=10, size_bytes=1, mime="image/jpeg"
    )
    user.avatar = asset
    user.save()
    user.profile.bio = "Professora."
    user.profile.save()
    user.profile.disciplines.add(DisciplineFactory())
