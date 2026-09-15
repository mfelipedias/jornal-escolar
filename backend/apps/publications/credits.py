"""Regras de crédito de alunos (docs/04 "Papéis de contribuição", docs/23)."""

import re

from apps.core.site_settings import get_setting

# "Rafael S.", "Ana Clara M.", "João P." (primeiro nome, opcionalmente composto, e inicial)
FIRST_INITIAL_RE = re.compile(r"^[A-ZÀ-Ý][a-zà-ÿ'-]+(?: [A-ZÀ-Ý][a-zà-ÿ'-]+)? [A-ZÀ-Ý]\.$")

# "2ª série B", "2a serie", "9º ano A", "1° ano" → série ou ano, sem a letra da turma.
SERIES_RE = re.compile(r"(\d{1,2})\s*[ªºao°]?\s*(s[ée]rie|ano)(?![a-zà-ÿ])", re.IGNORECASE)
GENERIC_STUDENT = "Aluno"


def generic_student_name(class_group: str) -> str:
    """Crédito genérico que substitui o nome do aluno (docs/18: "aluno da 2ª série").

    Mantém só a série ou o ano, que não identifica ninguém; sem isso, "Aluno".
    """
    match = SERIES_RE.search(class_group or "")
    if not match:
        return GENERIC_STUDENT
    number, kind = match.group(1), match.group(2).lower()
    if kind == "ano":
        return f"Aluno do {number}º ano"
    return f"Aluno da {number}ª série"


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
