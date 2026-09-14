"""Tag {% can %}: a matriz de permissões nos templates, sem repetir regra (docs/02).

Uso:
    {% load permissions %}
    {% can "publish" article as pode_publicar %}
    {% if pode_publicar %}...{% endif %}
    {% can "access_admin" as mostra_admin %}   {# ações sem objeto #}

"publish" chama apps.editorial.permissions.can_publish(usuário, article). O usuário vem do
contexto (context processor auth). Ação desconhecida é erro de template, para o nome errado
não virar um "não pode" silencioso.
"""

import inspect
from collections.abc import Callable

from django import template
from django.contrib.auth.models import AnonymousUser

from apps.editorial import permissions

register = template.Library()


def _actions() -> dict[str, Callable[..., bool]]:
    return {
        name.removeprefix("can_"): func
        for name, func in vars(permissions).items()
        if name.startswith("can_") and inspect.isfunction(func)
    }


ACTIONS = _actions()


def _takes_object(func: Callable[..., bool]) -> bool:
    return len(inspect.signature(func).parameters) > 1


@register.simple_tag(takes_context=True)
def can(context: template.Context, action: str, obj: object = None) -> bool:
    func = ACTIONS.get(action)
    if func is None:
        raise template.TemplateSyntaxError(f'{{% can %}}: ação desconhecida "{action}".')
    user = context.get("user")
    if user is None:
        request = context.get("request")
        user = getattr(request, "user", None) or AnonymousUser()
    if not _takes_object(func):
        return func(user)
    # Objeto ausente no contexto (None ou string vazia): não há o que permitir.
    if not obj:
        return False
    return func(user, obj)
