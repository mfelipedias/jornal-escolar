from datetime import datetime
from typing import Any

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DEFAULT_DB_ALIAS, DatabaseError, connections, transaction
from django.db.migrations.executor import MigrationExecutor

from apps.accounts.models import User
from apps.editorial import permissions
from apps.publications import rendering

from . import site_settings
from .models import StaticPage

PAGE_TITLE_MAX = 120
PAGE_LEAD_MAX = 240


def check_database() -> bool:
    """O banco responde a uma consulta simples."""
    try:
        with connections[DEFAULT_DB_ALIAS].cursor() as cursor:
            cursor.execute("SELECT 1")
    except DatabaseError:
        return False
    return True


def check_migrations() -> bool:
    """Todas as migrações conhecidas pelo código já foram aplicadas no banco."""
    try:
        executor = MigrationExecutor(connections[DEFAULT_DB_ALIAS])
        plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
    except DatabaseError:
        return False
    return not plan


# Textos iniciais das páginas institucionais. Sem nome da escola (docs/27).
# Privacidade nasce despublicada: precisa de revisão da direção (docs/23).
INITIAL_PAGES = [
    {
        "slug": StaticPage.Slug.ABOUT,
        "title": "Sobre o jornal",
        "lead": "Um jornal digital feito pela comunidade escolar.",
        "body": (
            "Aqui professores, monitores e a equipe da escola publicam notícias, "
            "reportagens, projetos e produções de alunos.\n\n"
            "Os textos são organizados por área do conhecimento, para que seja fácil "
            "encontrar o que se estuda e se produz em cada uma.\n\n"
            "Alunos participam entregando seus textos a um professor, que revisa, publica "
            "e dá o crédito."
        ),
        "is_published": True,
    },
    {
        "slug": StaticPage.Slug.CONTRIBUTE,
        "title": "Como participar",
        "lead": "Tem uma ideia, um texto ou um projeto para mostrar?",
        "body": (
            "Alunos: converse com um professor. Ele ajuda a preparar o texto e publica "
            "com o seu nome nos créditos.\n\n"
            "Professores e equipe: peça à coordenação o seu acesso ao jornal.\n\n"
            "Leitores: comente as publicações. Os comentários aparecem depois de "
            "aprovados por quem publicou."
        ),
        "is_published": True,
    },
    {
        "slug": StaticPage.Slug.PRIVACY,
        "title": "Privacidade",
        "lead": "Como o jornal trata os dados de quem lê e de quem participa.",
        "body": (
            "RASCUNHO: revisar com a direção antes de publicar.\n\n"
            "O jornal não usa rastreadores de publicidade nem ferramentas de análise que "
            "identifiquem visitantes.\n\n"
            "Alunos não têm conta. Nos créditos aparece o primeiro nome e a inicial do "
            "sobrenome, com autorização registrada pelo professor.\n\n"
            "Comentários mostram o nome informado por quem comenta e só aparecem depois "
            "de aprovados.\n\n"
            "Para pedir correção ou remoção de dados, escreva para o e-mail de contato "
            "no rodapé."
        ),
        "is_published": False,
    },
]


@transaction.atomic
def seed_site() -> dict[str, int]:
    """Cria configurações e páginas institucionais que faltam, sem alterar as existentes."""
    created_pages = 0
    for data in INITIAL_PAGES:
        defaults = {k: v for k, v in data.items() if k not in ("slug", "body")}
        document = text_to_document(data["body"])
        defaults.update(body_json=document, body_html=rendering.render(document, set()).html)
        _, created = StaticPage.objects.get_or_create(slug=data["slug"], defaults=defaults)
        created_pages += created
    return {"configurações": site_settings.ensure_defaults(), "páginas": created_pages}


def text_to_document(text: str) -> dict:
    """Texto simples (parágrafos separados por linha em branco) → documento do editor."""
    blocks = [b.strip() for b in text.replace("\r\n", "\n").split("\n\n") if b.strip()]
    content = []
    for block in blocks:
        inline: list[dict] = []
        for index, line in enumerate(block.split("\n")):
            if index:
                inline.append({"type": "hardBreak"})
            if line:
                inline.append({"type": "text", "text": line})
        content.append({"type": "paragraph", "content": inline})
    return {"type": "doc", "content": content}


class PageConflictError(Exception):
    """Outra pessoa salvou a página depois da versão que o editor carregou."""


@transaction.atomic
def update_page(
    user: User, page: StaticPage, *, expected_updated_at: datetime | None = None, **fields: Any
) -> StaticPage:
    """Autosave de título, linha fina e corpo de uma página institucional (editor+).

    O HTML é sempre gerado aqui, a partir do documento limpo; figuras são descartadas
    (páginas institucionais não têm imagens).
    """
    if not permissions.can_edit_pages(user):
        raise PermissionDenied
    unknown = set(fields) - {"title", "lead", "body_json"}
    if unknown:
        raise ValueError(f"Campos não editáveis: {sorted(unknown)}")
    current = StaticPage.objects.select_for_update().get(pk=page.pk)
    if (
        expected_updated_at is not None
        and current.updated_at != expected_updated_at
        and current.updated_by_id not in (None, user.pk)
    ):
        raise PageConflictError
    if "title" in fields:
        title = " ".join(str(fields["title"] or "").split())
        if len(title) > PAGE_TITLE_MAX:
            raise ValidationError({"title": f"O título pode ter até {PAGE_TITLE_MAX} caracteres."})
        # Título apagado no meio da digitação: mantém o anterior em vez de falhar o autosave.
        current.title = title or current.title
    if "lead" in fields:
        current.lead = " ".join(str(fields["lead"] or "").split())[:PAGE_LEAD_MAX]
    if "body_json" in fields:
        result = rendering.render(fields["body_json"], allowed_assets=set())
        current.body_json = result.document
        current.body_html = result.html
    current.updated_by = user
    current.save()
    return current


def set_page_published(user: User, page: StaticPage, published: bool) -> StaticPage:
    if not permissions.can_edit_pages(user):
        raise PermissionDenied
    page.is_published = published
    page.updated_by = user
    page.save(update_fields=["is_published", "updated_by", "updated_at"])
    return page
