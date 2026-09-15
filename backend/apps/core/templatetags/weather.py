"""Bloco "Hoje na escola" (docs/29). Uso: {% load weather %}{% weather_widget %}."""

from django import template

from apps.core.site_settings import get_setting
from apps.core.weather import get_weather

register = template.Library()


@register.inclusion_tag("components/weather.html")
def weather_widget(variant: str = "aside", css: str = "") -> dict:
    """variant "aside" (lateral, com título) ou "line" (uma linha, celular); css: classes extras."""
    weather = get_weather() if get_setting("weather.enabled") else None
    return {"weather": weather, "variant": variant, "css": css}
