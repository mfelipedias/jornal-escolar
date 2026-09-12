"""Regras de crédito de alunos (docs/04 "Papéis de contribuição", docs/23)."""

import re

from apps.core.site_settings import get_setting

# "Rafael S.", "Ana Clara M.", "João P." (primeiro nome, opcionalmente composto, e inicial)
FIRST_INITIAL_RE = re.compile(r"^[A-ZÀ-Ý][a-zà-ÿ'-]+(?: [A-ZÀ-Ý][a-zà-ÿ'-]+)? [A-ZÀ-Ý]\.$")


def student_name_error(name: str, *, full_name_authorized: bool = False) -> str | None:
    """Mensagem de erro se o nome do aluno não segue a política; None se está ok.

    Com a política "first_initial", o professor ainda pode usar o nome completo marcando
    explicitamente que há autorização para isso (docs/23).
    """
    name = " ".join(name.split())
    if not name:
        return "Informe o nome do aluno."
    policy = get_setting("credits.student_name_policy")
    if policy == "first_initial" and not full_name_authorized and not FIRST_INITIAL_RE.match(name):
        return "Use primeiro nome e inicial do sobrenome, ex.: Rafael S."
    return None
