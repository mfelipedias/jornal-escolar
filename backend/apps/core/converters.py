from .models import StaticPage


class StaticPageSlugConverter:
    """Aceita só os endereços das páginas institucionais: sobre, privacidade, colaborar."""

    regex = "|".join(StaticPage.Slug.values)

    def to_python(self, value: str) -> str:
        return value

    def to_url(self, value: str) -> str:
        return value
