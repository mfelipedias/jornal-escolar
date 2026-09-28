"""Layout e menu do painel (E24, docs/15 "Menu lateral")."""

import pytest
from django.urls import reverse

from apps.dashboard.menu import menu_items

pytestmark = pytest.mark.django_db

BASE_KEYS = [
    "home",
    "my_articles",
    "create",
    "reviews",
    "comments",
    "suggestions",
    "profile",
    "account",
    "site",
]
LATER_PHASES = (
    "/painel/pautas/",
    "/painel/editorial/",
)


def test_menu_for_staff_has_only_current_items(staff_user):
    items = menu_items(staff_user, "dashboard:home")

    assert [item.key for item in items] == BASE_KEYS
    assert [item.key for item in items if item.active] == ["home"]


def test_only_admin_sees_administration(admin_user, editor_user):
    assert "admin" in [item.key for item in menu_items(admin_user)]
    assert "admin" not in [item.key for item in menu_items(editor_user)]


@pytest.mark.parametrize(
    ("url_name", "active"),
    [
        ("dashboard:home", "Início"),
        ("dashboard:my_articles", "Minhas publicações"),
        ("publications:create", "Nova publicação"),
        ("accounts:profile_edit", "Perfil"),
        ("accounts:account_settings", "Conta"),
        ("editorial:notifications", "Início"),
        ("editorial:queue", "Revisões"),
        ("engagement:moderation", "Comentários"),
        ("curation:suggestions", "Sugestões"),
    ],
)
def test_panel_pages_use_dashboard_layout(client, staff_user, url_name, active):
    client.force_login(staff_user)
    html = client.get(reverse(url_name)).content.decode()

    assert 'aria-label="Menu do painel"' in html
    assert 'id="notification-bell"' in html
    assert 'name="robots" content="noindex"' in html
    for later in LATER_PHASES:
        assert later not in html
    before_current = html.split('aria-current="page"')[0]
    assert f'title="{active}"' in before_current.rsplit("<a ", 1)[1]


def test_version_in_menu_footer(client, staff_user, settings):
    client.force_login(staff_user)
    html = client.get(reverse("dashboard:home")).content.decode()
    assert f"v{settings.APP_VERSION}" in html


def test_admin_link_only_for_admin(client, admin_user, editor_user):
    client.force_login(admin_user)
    assert 'href="/admin/"' in client.get(reverse("dashboard:home")).content.decode()
    client.force_login(editor_user)
    assert 'href="/admin/"' not in client.get(reverse("dashboard:home")).content.decode()


def test_masthead_links_to_panel(client, staff_user):
    client.force_login(staff_user)
    assert 'href="/painel/"' in client.get("/").content.decode()
