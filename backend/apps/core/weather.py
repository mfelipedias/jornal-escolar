"""Clima "Hoje na escola" (docs/29): tempo atual e previsão do dia via Open-Meteo.

A chamada é feita pelo servidor, sem chave e sem dados do visitante. O resultado fica em cache
por 30 minutos; em falha (rede, timeout, resposta estranha) o último valor bom vale por até
6 horas e, sem nada guardado, get_weather() devolve None e a home esconde o bloco.
"""

import json
import logging
from dataclasses import dataclass
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

CACHE_KEY = "core:weather:v1"
STALE_CACHE_KEY = "core:weather:stale:v1"
CACHE_TIMEOUT = 30 * 60
STALE_TIMEOUT = 6 * 60 * 60
REQUEST_TIMEOUT = 3

# Códigos WMO usados pelo Open-Meteo → (chave do ícone, rótulo). Ícones em components/weather.html.
_CONDITIONS: list[tuple[range, str, str]] = [
    (range(0, 1), "clear", "Céu limpo"),
    (range(1, 3), "partly", "Parcialmente nublado"),
    (range(3, 4), "cloudy", "Nublado"),
    (range(45, 49), "fog", "Nevoeiro"),
    (range(51, 58), "drizzle", "Chuvisco"),
    (range(61, 68), "rain", "Chuva"),
    (range(71, 78), "snow", "Neve"),
    (range(80, 83), "rain", "Chuva"),
    (range(85, 87), "snow", "Neve"),
    (range(95, 100), "thunder", "Trovoada"),
]


@dataclass(frozen=True)
class Weather:
    temperature: int
    icon: str
    label: str
    temp_min: int
    temp_max: int
    rain_chance: int | None
    is_day: bool


def describe(code: int, is_day: bool = True) -> tuple[str, str]:
    """Ícone e rótulo em português de um código WMO; códigos desconhecidos viram "Nublado"."""
    for codes, icon, label in _CONDITIONS:
        if code in codes:
            if icon == "clear" and not is_day:
                return "night", label
            return icon, label
    return "cloudy", "Nublado"


def _fetch() -> Weather:
    query = urlencode(
        {
            "latitude": settings.WEATHER_LAT,
            "longitude": settings.WEATHER_LON,
            "current": "temperature_2m,weather_code,is_day",
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
            "timezone": settings.WEATHER_TIMEZONE,
            "forecast_days": 1,
        }
    )
    url = f"{settings.WEATHER_API_BASE.rstrip('/')}/v1/forecast?{query}"
    request = Request(url, headers={"User-Agent": f"JornalEscolar/{settings.APP_VERSION}"})
    with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
        data = json.load(response)
    return parse(data)


def parse(data: dict) -> Weather:
    """Monta o Weather a partir do JSON do Open-Meteo; levanta erro se faltar campo."""
    current = data["current"]
    daily = data["daily"]
    is_day = bool(current.get("is_day", 1))
    icon, label = describe(int(current["weather_code"]), is_day)
    chance = daily["precipitation_probability_max"][0]
    return Weather(
        temperature=round(current["temperature_2m"]),
        icon=icon,
        label=label,
        temp_min=round(daily["temperature_2m_min"][0]),
        temp_max=round(daily["temperature_2m_max"][0]),
        rain_chance=None if chance is None else int(chance),
        is_day=is_day,
    )


def get_weather() -> Weather | None:
    """Tempo atual, do cache ou da API. None quando não há como saber."""
    if not settings.WEATHER_API_BASE:
        return None
    weather = cache.get(CACHE_KEY)
    if weather is not None:
        return weather
    try:
        weather = _fetch()
    except (URLError, TimeoutError, ValueError, KeyError, IndexError, TypeError) as exc:
        logger.warning("Clima indisponível: %s", exc)
        return cache.get(STALE_CACHE_KEY)
    cache.set(CACHE_KEY, weather, CACHE_TIMEOUT)
    cache.set(STALE_CACHE_KEY, weather, STALE_TIMEOUT)
    return weather
