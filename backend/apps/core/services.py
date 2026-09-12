from django.db import DEFAULT_DB_ALIAS, DatabaseError, connections, transaction
from django.db.migrations.executor import MigrationExecutor

from . import site_settings
from .models import StaticPage


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
        _, created = StaticPage.objects.get_or_create(
            slug=data["slug"], defaults={k: v for k, v in data.items() if k != "slug"}
        )
        created_pages += created
    return {"configurações": site_settings.ensure_defaults(), "páginas": created_pages}
