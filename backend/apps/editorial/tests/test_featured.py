"""Destaques da home: regras, tela do editor e reflexo na home (E25, docs/18)."""

from datetime import timedelta

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse
from django.utils import timezone

from apps.dashboard.menu import menu_items
from apps.publications import home, services
from apps.publications.models import Article, MediaAsset
from tests.factories import ArticleFactory

pytestmark = pytest.mark.django_db

HX = {"HTTP_HX_REQUEST": "true"}


def publish(author, title, *, days_ago=0, cover=True, **fields):
    article = ArticleFactory(ready=True, author=author, created_by=author, title=title)
    services.publish(author, article)
    if cover:
        fields["cover"] = MediaAsset.objects.create(
            file=f"media/{article.pk}.jpg",
            uploaded_by=author,
            width=1600,
            height=900,
            size_bytes=1,
            mime="image/jpeg",
            alt_text="Capa",
        )
    Article.objects.filter(pk=article.pk).update(
        published_at=timezone.now() - timedelta(days=days_ago), **fields
    )
    return Article.objects.get(pk=article.pk)


@pytest.fixture
def three(staff_user):
    return [publish(staff_user, f"Texto {n}", days_ago=n) for n in (1, 2, 3)]


def feature_url(article):
    return reverse("editorial:feature", args=[article.pk])


# --- regras (services) ---


def test_set_featured_keeps_order_and_clears_others(editor_user, three):
    a, _, c = three
    services.set_featured(editor_user, [c.pk, a.pk])

    assert services.featured_ids() == [c.pk, a.pk]
    assert Article.objects.get(pk=c.pk).featured_order == 1
    services.set_featured(editor_user, [a.pk])
    c_after = Article.objects.get(pk=c.pk)
    assert not c_after.is_featured
    assert c_after.featured_order is None


def test_staff_cannot_feature(staff_user, three):
    with pytest.raises(PermissionDenied):
        services.set_featured(staff_user, [three[0].pk])


def test_at_most_three(editor_user, staff_user, three):
    extra = publish(staff_user, "Quarto")
    services.set_featured(editor_user, [a.pk for a in three])

    with pytest.raises(ValidationError):
        services.feature(editor_user, extra)
    with pytest.raises(ValidationError):
        services.set_featured(editor_user, [*[a.pk for a in three], extra.pk])


def test_new_featured_requires_cover(editor_user, staff_user):
    no_cover = publish(staff_user, "Sem capa", cover=False)

    with pytest.raises(ValidationError, match="capa"):
        services.feature(editor_user, no_cover)


def test_old_featured_without_cover_can_be_reordered(editor_user, staff_user, three):
    old = publish(staff_user, "Antigo", cover=False, is_featured=True, featured_order=1)
    services.feature(editor_user, three[0])

    services.move_featured(editor_user, three[0], -1)

    assert services.featured_ids() == [three[0].pk, old.pk]


def test_only_published_can_be_featured(editor_user, staff_user):
    draft = ArticleFactory(author=staff_user, created_by=staff_user)

    with pytest.raises(ValidationError, match="no ar"):
        services.feature(editor_user, draft)


def test_move_and_remove(editor_user, three):
    a, b, c = three
    services.set_featured(editor_user, [a.pk, b.pk, c.pk])

    services.move_featured(editor_user, c, -1)
    assert services.featured_ids() == [a.pk, c.pk, b.pk]
    services.move_featured(editor_user, a, -1)  # já é o primeiro: nada muda
    assert services.featured_ids() == [a.pk, c.pk, b.pk]
    services.unfeature(editor_user, c)
    assert services.featured_ids() == [a.pk, b.pk]


def test_archive_clears_featured(editor_user, three):
    services.set_featured(editor_user, [three[0].pk])

    services.archive(editor_user, three[0], note="Retirada")

    article = Article.objects.get(pk=three[0].pk)
    assert not article.is_featured
    assert article.featured_order is None


# --- aceite: reordenar reflete na home ---


def test_reorder_reflects_on_home(client, editor_user, three):
    a, b, c = three
    services.set_featured(editor_user, [a.pk, b.pk, c.pk])
    assert [card.title for card in home.blocks().featured] == ["Texto 1", "Texto 2", "Texto 3"]
    client.get("/")  # blocos da home em cache

    client.force_login(editor_user)
    response = client.post(feature_url(c), {"acao": "subir"}, **HX)
    client.post(feature_url(c), {"acao": "subir"}, **HX)

    assert response.status_code == 200
    assert [card.title for card in home.blocks().featured] == ["Texto 3", "Texto 1", "Texto 2"]
    html = client.get("/").content.decode()
    assert html.index("Texto 3") < html.index("Texto 1") < html.index("Texto 2")


def test_adding_through_screen_reflects_on_home(client, editor_user, staff_user, three):
    old = publish(staff_user, "Reportagem antiga", days_ago=40)
    assert "Reportagem antiga" not in [card.title for card in home.blocks().featured]

    client.force_login(editor_user)
    client.post(feature_url(old), {"acao": "adicionar"}, **HX)

    assert home.blocks().featured[0].title == "Reportagem antiga"


# --- tela ---


def test_screen_requires_editor(client, staff_user):
    assert client.get(reverse("editorial:featured")).status_code == 302
    client.force_login(staff_user)

    assert client.get(reverse("editorial:featured")).status_code == 403
    assert client.get(reverse("editorial:featured_search")).status_code == 403


def test_staff_cannot_post_feature(client, staff_user, three):
    client.force_login(staff_user)

    response = client.post(feature_url(three[0]), {"acao": "adicionar"}, **HX)

    assert response.status_code == 403
    assert not Article.objects.filter(is_featured=True).exists()


def test_screen_lists_chosen_candidates_and_preview(client, editor_user, staff_user, three):
    publish(staff_user, "Sem capa", cover=False)
    services.set_featured(editor_user, [three[1].pk])
    client.force_login(editor_user)

    response = client.get(reverse("editorial:featured"))

    html = response.content.decode()
    assert response.status_code == 200
    assert f'data-featured="{three[1].pk}"' in html
    assert f'data-candidate="{three[0].pk}"' in html
    assert f'data-candidate="{three[1].pk}"' not in html  # já escolhido
    assert "Sem capa" not in html.split('id="featured-candidates"')[1].split("</section>")[0]
    assert "data-featured-preview" in html
    assert "Mais recente (automático)" in html
    assert 'title="Destaques"' in html.split('aria-current="page"')[0].rsplit("<a ", 1)[1]


def test_search_filters_by_title(client, editor_user, staff_user, three):
    publish(staff_user, "Feira de Ciências")
    client.force_login(editor_user)

    html = client.get(reverse("editorial:featured_search"), {"q": "feira"}, **HX)
    html = html.content.decode()

    assert "Feira de Ciências" in html
    assert "Texto 1" not in html
    assert 'id="featured-candidates"' in html


def test_error_is_shown_in_board(client, editor_user, staff_user, three):
    no_cover = publish(staff_user, "Sem capa", cover=False)
    client.force_login(editor_user)

    response = client.post(feature_url(no_cover), {"acao": "adicionar"}, **HX)

    html = response.content.decode()
    assert 'role="alert"' in html
    assert "precisam de capa" in html
    assert 'id="featured-board"' in html


def test_full_disables_add_buttons(client, editor_user, staff_user, three):
    publish(staff_user, "Quarto")
    services.set_featured(editor_user, [a.pk for a in three])
    client.force_login(editor_user)

    html = client.get(reverse("editorial:featured")).content.decode()

    assert "Remova um para adicionar outro" in html
    assert "disabled" in html.split('id="featured-candidates"')[1]


def test_without_htmx_redirects_back(client, editor_user, three):
    client.force_login(editor_user)

    response = client.post(feature_url(three[0]), {"acao": "adicionar"})

    assert response.status_code == 302
    assert response.url == reverse("editorial:featured")
    assert services.featured_ids() == [three[0].pk]


def test_menu_shows_featured_and_pages_only_to_editors(staff_user, editor_user, admin_user):
    assert {"featured", "pages"}.isdisjoint(item.key for item in menu_items(staff_user))
    for user in (editor_user, admin_user):
        keys = [item.key for item in menu_items(user)]
        assert keys.index("create") < keys.index("featured") < keys.index("pages")
