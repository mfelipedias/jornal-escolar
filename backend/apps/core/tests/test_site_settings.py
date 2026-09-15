import pytest
from django.urls import reverse

from apps.core import site_settings
from apps.core.admin import SiteSettingForm
from apps.core.models import SiteSetting
from apps.core.site_settings import REGISTRY, get_setting, get_settings

pytestmark = pytest.mark.django_db


def test_defaults_when_database_is_empty():
    assert get_setting("site.name") == "Jornal Escolar"
    assert get_setting("home.featured_count") == 3
    assert get_setting("comments.enabled") is True


def test_unknown_key_raises():
    with pytest.raises(KeyError):
        get_setting("nao.existe")


def test_database_value_overrides_default():
    SiteSetting.objects.create(key="site.name", value="Gazeta da Escola")

    assert get_setting("site.name") == "Gazeta da Escola"


def test_saving_clears_cache():
    setting = SiteSetting.objects.create(key="site.tagline", value="Primeira")
    assert get_setting("site.tagline") == "Primeira"

    setting.value = "Segunda"
    setting.save()

    assert get_setting("site.tagline") == "Segunda"


def test_values_are_cached(django_assert_num_queries):
    get_setting("site.name")

    with django_assert_num_queries(0):
        get_setting("site.tagline")
        get_settings("site.")


def test_ensure_defaults_is_idempotent_and_keeps_edits():
    SiteSetting.objects.create(key="site.name", value="Editado")

    created = site_settings.ensure_defaults()

    assert created == len(REGISTRY) - 1
    assert site_settings.ensure_defaults() == 0
    assert SiteSetting.objects.get(key="site.name").value == "Editado"


def test_school_name_is_not_a_default():
    for spec in REGISTRY.values():
        assert "[omitido]" not in str(spec.default).lower()


def test_masthead_uses_setting_from_database(client):
    SiteSetting.objects.create(key="site.name", value="Gazeta da Escola")

    html = client.get("/").content.decode()

    assert "Gazeta da" in html
    assert '<span class="wordmark-accent">Escola</span>' in html
    assert "<title>Gazeta da Escola · " in html  # nome + tagline (docs/10)


def test_date_can_be_hidden(client):
    SiteSetting.objects.create(key="site.show_date", value=False)

    html = client.get("/").content.decode()

    assert " de 20" not in html


@pytest.mark.parametrize(
    ("key", "raw", "expected"),
    [
        ("site.name", "Novo Nome", "Novo Nome"),
        ("home.featured_count", "5", 5),
        ("comments.enabled", "", False),
        ("comments.enabled", "on", True),
        ("editorial.self_publish", "never", "never"),
    ],
)
def test_admin_form_converts_values_by_type(key, raw, expected):
    setting = SiteSetting.objects.create(key=key, value=REGISTRY[key].default)

    form = SiteSettingForm(data={"value": raw}, instance=setting)

    assert form.is_valid(), form.errors
    assert form.save().value == expected


def test_admin_form_rejects_invalid_values():
    setting = SiteSetting.objects.create(key="home.featured_count", value=3)

    assert not SiteSettingForm(data={"value": "0"}, instance=setting).is_valid()
    assert not SiteSettingForm(data={"value": "abc"}, instance=setting).is_valid()


def test_admin_changelist_creates_all_settings(admin_client):
    response = admin_client.get(reverse("admin:core_sitesetting_changelist"))

    assert response.status_code == 200
    assert SiteSetting.objects.count() == len(REGISTRY)
    assert "Nome do jornal" in response.content.decode()


def test_admin_change_page_and_no_add(admin_client):
    site_settings.ensure_defaults()

    change = admin_client.get(reverse("admin:core_sitesetting_change", args=["site.name"]))
    add = admin_client.get(reverse("admin:core_sitesetting_add"))

    assert change.status_code == 200
    assert add.status_code == 403
