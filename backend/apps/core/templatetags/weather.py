"""Tempo agora na escola, no cabeçalho (docs/29). Uso: {% load weather %}{% weather_widget %}."""

from django import template

from apps.core.site_settings import get_setting
from apps.core.weather import get_weather

register = template.Library()


@register.inclusion_tag("components/weather.html")
def weather_widget(css: str = "", as_item: bool = False) -> dict:
    """Linha do clima; sem dados ou com weather.enabled desligado, não renderiza nada.

    as_item=True embrulha a linha num <li>, para abrir a barra de seções no celular.
    """
    weather = get_weather() if get_setting("weather.enabled") else None
    return {"weather": weather, "css": css, "as_item": as_item}
