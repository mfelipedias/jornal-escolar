"""Configurações do site editáveis no Django Admin (docs/05, D10; docs/06, core.SiteSetting).

Cada chave conhecida está em REGISTRY, com tipo, valor padrão e explicação.
O banco só guarda o valor atual; se a linha não existir, vale o padrão.

Uso: get_setting("site.name")
"""

from dataclasses import dataclass, field
from typing import Any, Literal

from django.core.cache import cache

Kind = Literal["text", "email", "bool", "int", "choice"]

CACHE_KEY = "core:site_settings:v1"
# Cada processo do servidor tem seu cache em memória; este prazo limita a defasagem entre eles.
CACHE_TIMEOUT = 60


@dataclass(frozen=True)
class SettingSpec:
    key: str
    label: str
    kind: Kind
    default: Any
    help_text: str = ""
    choices: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    min_value: int | None = None


REGISTRY: dict[str, SettingSpec] = {
    spec.key: spec
    for spec in [
        SettingSpec(
            "site.name",
            "Nome do jornal",
            "text",
            "Jornal Escolar",
            "Aparece no cabeçalho, no título das páginas e nos compartilhamentos. "
            "A última palavra aparece na cor de destaque.",
        ),
        SettingSpec(
            "site.tagline",
            "Frase de apresentação",
            "text",
            "Jornal digital da comunidade escolar",
        ),
        SettingSpec(
            "site.description",
            "Descrição para buscadores",
            "text",
            "",
            "Texto curto (até 160 caracteres) que o Google e as redes sociais mostram para a "
            "página inicial. Se vazio, usa a frase de apresentação. Não cite o nome da escola.",
        ),
        SettingSpec(
            "site.footer_credit",
            "Crédito no rodapé",
            "text",
            "Desenvolvido por Professor Marcos Felipe A. D. da Silva",
        ),
        SettingSpec(
            "site.contact_email",
            "E-mail de contato",
            "email",
            "marcossilva06@professor.educacao.sp.gov.br",
            "Mostrado no rodapé. Também é o contato para pedidos de privacidade.",
        ),
        SettingSpec(
            "site.show_date",
            "Mostrar a data no cabeçalho",
            "bool",
            True,
        ),
        SettingSpec(
            "auth.microsoft_enabled",
            "Login com a conta Microsoft da escola ligado",
            "bool",
            True,
            "Desligue se a Secretaria bloquear o aplicativo; todos passam a entrar com senha "
            "criada por link de acesso. O botão só aparece se MS_CLIENT_ID e MS_CLIENT_SECRET "
            "estiverem configurados no servidor.",
        ),
        SettingSpec(
            "auth.self_signup",
            "Cadastro próprio ligado",
            "bool",
            True,
            "Professores com e-mail @prof ou @professor criam a própria conta, que espera a "
            "aprovação de um editor. Só aparece se o e-mail (Gmail) estiver configurado no "
            "servidor (docs/35).",
        ),
        SettingSpec(
            "editorial.self_publish",
            "Quem publica",
            "choice",
            "staff",
            "Define se cada membro da equipe publica os próprios textos.",
            choices=(
                ("staff", "Cada membro da equipe publica os próprios textos"),
                ("never", "Toda publicação precisa de aprovação de outra pessoa"),
            ),
        ),
        SettingSpec(
            "credits.student_name_policy",
            "Nome de alunos nos créditos",
            "choice",
            "first_initial",
            choices=(
                ("first_initial", "Primeiro nome e inicial do sobrenome (Rafael S.)"),
                ("full", "Nome completo"),
            ),
        ),
        SettingSpec(
            "home.featured_count",
            "Quantidade de destaques na página inicial",
            "int",
            3,
            min_value=1,
        ),
        SettingSpec(
            "reactions.require_login",
            "Reações só para quem entrou no sistema",
            "bool",
            False,
        ),
        SettingSpec(
            "reads.min_seconds",
            "Segundos na página para contar uma leitura",
            "int",
            15,
            min_value=1,
        ),
        SettingSpec(
            "comments.enabled",
            "Comentários de leitores ligados",
            "bool",
            True,
        ),
        SettingSpec(
            "weather.enabled",
            "Mostrar o clima no cabeçalho",
            "bool",
            True,
        ),
    ]
}


def _load_overrides() -> dict[str, Any]:
    from .models import SiteSetting

    values = cache.get(CACHE_KEY)
    if values is None:
        values = dict(SiteSetting.objects.filter(key__in=REGISTRY).values_list("key", "value"))
        cache.set(CACHE_KEY, values, CACHE_TIMEOUT)
    return values


def get_setting(key: str) -> Any:
    """Valor atual da configuração; KeyError para chaves que não existem no REGISTRY."""
    spec = REGISTRY[key]
    return _load_overrides().get(key, spec.default)


def get_settings(prefix: str = "") -> dict[str, Any]:
    overrides = _load_overrides()
    return {
        key: overrides.get(key, spec.default)
        for key, spec in REGISTRY.items()
        if key.startswith(prefix)
    }


def clear_cache() -> None:
    cache.delete(CACHE_KEY)


def ensure_defaults() -> int:
    """Cria no banco as linhas que faltam, com o valor padrão. Devolve quantas criou."""
    from .models import SiteSetting

    existing = set(SiteSetting.objects.values_list("key", flat=True))
    missing = [
        SiteSetting(key=spec.key, value=spec.default, description=spec.label)
        for spec in REGISTRY.values()
        if spec.key not in existing
    ]
    SiteSetting.objects.bulk_create(missing)
    if missing:
        clear_cache()
    return len(missing)
