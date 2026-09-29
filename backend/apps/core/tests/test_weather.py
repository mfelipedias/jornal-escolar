"""Clima "Hoje na escola" (docs/29, E42)."""

import io
import json
from unittest import mock
from urllib.error import URLError

import pytest
from django.core.cache import cache

from apps.core import weather
from apps.core.models import SiteSetting
from apps.publications import services
from tests.factories import ArticleFactory, UserFactory

pytestmark = pytest.mark.django_db

API = "https://api.open-meteo.com"

PAYLOAD = {
    "current": {"temperature_2m": 22.6, "weather_code": 3, "is_day": 1},
    "daily": {
        "temperature_2m_max": [26.4],
        "temperature_2m_min": [17.2],
        "precipitation_probability_max": [40],
    },
}


def fake_response(payload=PAYLOAD):
    body = io.BytesIO(json.dumps(payload).encode())
    return mock.MagicMock(__enter__=mock.Mock(return_value=body), __exit__=mock.Mock())


@pytest.fixture
def api(settings):
    """Liga a API (os testes rodam com ela desligada) e simula a resposta do Open-Meteo."""
    settings.WEATHER_API_BASE = API
    with mock.patch.object(weather, "urlopen", return_value=fake_response()) as urlopen:
        yield urlopen


@pytest.mark.parametrize(
    ("code", "is_day", "expected"),
    [
        (0, True, ("clear", "Céu limpo")),
        (0, False, ("night", "Céu limpo")),
        (2, True, ("partly", "Parcialmente nublado")),
        (3, True, ("cloudy", "Nublado")),
        (45, True, ("fog", "Nevoeiro")),
        (53, True, ("drizzle", "Chuvisco")),
        (63, True, ("rain", "Chuva")),
        (81, True, ("rain", "Chuva")),
        (75, True, ("snow", "Neve")),
        (95, True, ("thunder", "Trovoada")),
        (99, False, ("thunder", "Trovoada")),
        (42, True, ("cloudy", "Nublado")),  # código fora da tabela
    ],
)
def test_describe_maps_wmo_codes(code, is_day, expected):
    assert weather.describe(code, is_day) == expected


def test_parse_rounds_and_labels():
    result = weather.parse(PAYLOAD)

    assert result == weather.Weather(
        temperature=23,
        icon="cloudy",
        label="Nublado",
        temp_min=17,
        temp_max=26,
        rain_chance=40,
        is_day=True,
    )


def test_parse_without_rain_probability():
    payload = json.loads(json.dumps(PAYLOAD))
    payload["daily"]["precipitation_probability_max"] = [None]

    assert weather.parse(payload).rain_chance is None


def test_disabled_without_api_base():
    """A configuração de teste deixa WEATHER_API_BASE vazio: nada de rede."""
    with mock.patch.object(weather, "urlopen") as urlopen:
        assert weather.get_weather() is None
    urlopen.assert_not_called()


def test_fetches_with_coordinates_and_caches(api, settings):
    settings.WEATHER_LAT = -23.5
    settings.WEATHER_LON = -46.7

    first = weather.get_weather()
    second = weather.get_weather()

    assert first.temperature == 23
    assert second == first
    assert api.call_count == 1
    request = api.call_args.args[0]
    assert request.full_url.startswith(f"{API}/v1/forecast?")
    assert "latitude=-23.5" in request.full_url
    assert "longitude=-46.7" in request.full_url
    assert "timezone=America%2FSao_Paulo" in request.full_url
    assert "forecast_days=1" in request.full_url
    assert api.call_args.kwargs["timeout"] == weather.REQUEST_TIMEOUT


def test_failure_returns_none_when_nothing_cached(api):
    api.side_effect = URLError("sem rede")

    assert weather.get_weather() is None


@pytest.mark.parametrize("error", [TimeoutError(), URLError("x"), ValueError("json")])
def test_failure_keeps_last_good_value(api, error):
    good = weather.get_weather()
    cache.delete(weather.CACHE_KEY)  # os 30 minutos passaram
    api.side_effect = error

    assert weather.get_weather() == good


def test_stale_value_expires_after_six_hours(api):
    weather.get_weather()
    cache.delete(weather.CACHE_KEY)
    cache.delete(weather.STALE_CACHE_KEY)  # as 6 horas passaram
    api.side_effect = URLError("x")

    assert weather.get_weather() is None


def test_bad_payload_is_a_failure(api):
    api.return_value = fake_response({"current": {}})

    assert weather.get_weather() is None


# --- Clima no cabeçalho ---


@pytest.fixture
def widget():
    with mock.patch("apps.core.templatetags.weather.get_weather") as get_weather:
        get_weather.return_value = weather.parse(PAYLOAD)
        yield get_weather


def test_masthead_shows_weather_under_date(client, widget):
    html = client.get("/").content.decode()

    masthead = html[html.index("<header") : html.index("</header>")]
    # Ao lado da busca (tablet e computador) e abrindo a barra de seções (celular).
    assert masthead.count("Tempo agora na escola:") == 2
    assert "max-sm:hidden" in masthead
    assert '<li class="flex items-center pr-2 sm:hidden" data-weather>' in masthead
    # Embaixo da data e antes do botão de busca.
    date = masthead.index("hidden text-meta text-ink-3 lg:block")
    assert date < masthead.index("Tempo agora na escola:") < masthead.index("masthead-search")
    assert ">23°</span>" in masthead
    assert "Nublado" in masthead
    assert "mín 17° máx 26°" in masthead
    assert "chuva 40%" in masthead
    # Abaixo de 1024px só ícone e temperatura aparecem; o resto fica para leitores de tela.
    assert "max-lg:sr-only" in masthead


def test_weather_appears_on_other_public_pages(client, widget):
    author = UserFactory()
    article = ArticleFactory(ready=True, author=author, created_by=author)
    services.publish(author, article)

    html = client.get(article.get_absolute_url()).content.decode()

    assert "Tempo agora na escola:" in html


def test_home_body_has_no_weather_block(client, widget):
    author = UserFactory()
    article = ArticleFactory(ready=True, author=author, created_by=author)
    services.publish(author, article)

    html = client.get("/").content.decode()
    main = html[html.index("<main") : html.index("</main>")]

    assert "Tempo agora na escola" not in main
    assert "Hoje na escola" not in html


def test_masthead_hides_weather_when_unavailable(client, widget):
    widget.return_value = None

    html = client.get("/").content.decode()

    assert "Tempo agora na escola" not in html


def test_masthead_hides_weather_when_setting_is_off(client, widget):
    SiteSetting.objects.create(key="weather.enabled", value=False)

    html = client.get("/").content.decode()

    assert "Tempo agora na escola" not in html
    widget.assert_not_called()


def test_weather_without_rain_chance(client, widget):
    payload = json.loads(json.dumps(PAYLOAD))
    payload["daily"]["precipitation_probability_max"] = [None]
    widget.return_value = weather.parse(payload)

    html = client.get("/").content.decode()

    assert "mín 17° máx 26°" in html
    assert "chuva" not in html[html.index("<header") : html.index("</header>")]
