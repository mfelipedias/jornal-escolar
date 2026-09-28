"""Matriz de permissões de docs/02, célula a célula (E30).

MATRIZ copia a tabela do documento símbolo por símbolo; test_matriz_espelha_o_documento
falha se as duas divergirem. Cada célula vira um ou mais casos:

- ✅ sim: vale para a publicação/perfil da própria pessoa e para os de outras pessoas;
- 🔒 só nas próprias: sim no próprio, não no alheio;
- 🟡 se designado revisor: sim quando a pessoa é a revisora designada, não no alheio;
- ❌ não: não em todas as situações.

Na coluna Equipe, ações sobre publicação ganham também a situação "revisor" (a pessoa é a
revisora designada de um texto alheio): sim só se a célula tiver 🟡 ou ✅. Linhas que dependem
de recursos futuros ficam marcadas como fora do escopo desta fase (skip com a etapa).
"""

import re
from dataclasses import dataclass

import pytest
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.template import Context, Template, TemplateSyntaxError

from apps.editorial import permissions as p
from apps.editorial.templatetags.permissions import ACTIONS
from apps.publications import services
from apps.publications.models import Article, ArticleContributor
from tests.factories import ArticleFactory, UserFactory

pytestmark = pytest.mark.django_db

S = Article.Status
DOC = settings.REPO_DIR / "docs" / "02-personas-papeis-permissoes.md"
COLUNAS = ("visitante", "equipe", "editor", "admin")

# (ação, visitante, equipe, editor, admin): igual à tabela de docs/02.
MATRIZ = [
    ("Ler publicações publicadas", "✅", "✅", "✅", "✅"),
    ("Buscar e filtrar", "✅", "✅", "✅", "✅"),
    ("Reagir", "✅ (cookie anônimo)", "✅", "✅", "✅"),
    ("Comentar (vai para moderação)", "✅", "✅", "✅", "✅"),
    ("Ver perfil público da equipe", "✅", "✅", "✅", "✅"),
    ("Entrar (Microsoft ou senha)", "❌", "✅", "✅", "✅"),
    ("Editar o próprio perfil", "❌", "🔒", "🔒", "✅"),
    ("Criar rascunho", "❌", "✅", "✅", "✅"),
    ("Editar rascunho", "❌", "🔒 ou 🟡", "✅", "✅"),
    ("Creditar alunos e colegas", "❌", "🔒", "✅", "✅"),
    ("Publicar", "❌", "🔒", "✅", "✅"),
    ("Editar publicação publicada", "❌", "🔒", "✅", "✅"),
    ("Arquivar / despublicar", "❌", "🔒", "✅", "✅"),
    ("Pedir revisão a um colega", "❌", "🔒", "✅", "✅"),
    ("Comentar na revisão (interno)", "❌", "🔒 ou 🟡", "✅", "✅"),
    ("Aprovar / solicitar alterações em revisão", "❌", "🟡", "✅", "✅"),
    ("Moderar comentários públicos", "❌", "🔒", "✅", "✅"),
    ("Responder comentários como autor", "❌", "🔒", "✅", "✅"),
    ("Definir destaques da home", "❌", "❌", "✅", "✅"),
    ("Ver sugestões de pauta (Fase 4)", "❌", "✅", "✅", "✅"),
    ("Criar pauta a partir de sugestão (Fase 4)", "❌", "✅", "✅", "✅"),
    ("Upload de imagens", "❌", "✅", "✅", "✅"),
    ("Criar contas da equipe", "❌", "❌", "❌", "✅"),
    ("Mudar papel de um usuário", "❌", "❌", "❌", "✅"),
    ("Gerenciar áreas, disciplinas, tópicos, tipos", "❌", "❌", "❌", "✅"),
    ("Gerenciar fontes de notícia (Fase 4)", "❌", "❌", "❌", "✅"),
    ("Configurações, auditoria, anonimização", "❌", "❌", "❌", "✅"),
]

FORA_DO_ESCOPO = {
    "Buscar e filtrar": "busca e filtros completos: E35 a E37",
}


@dataclass(frozen=True)
class Regra:
    """Como testar uma linha: qual função, sobre o quê e em que estado."""

    funcao: str
    objeto: str | None = None  # None, "article", "profile" ou "person"
    estado: str = S.DRAFT
    estado_revisor: str = S.IN_REVIEW
    situacoes: tuple[str, ...] = ("proprio", "alheio", "revisor")


REGRAS = {
    "Ler publicações publicadas": Regra("can_view", "article", S.PUBLISHED, S.PUBLISHED),
    # Visitante reage pelo cookie anônimo; a regra do cookie é testada em engagement/tests.
    "Reagir": Regra("can_react", "article", S.PUBLISHED, S.PUBLISHED),
    # O formulário depende também de comments.enabled e de comments_enabled (engagement/tests).
    "Comentar (vai para moderação)": Regra("can_comment", "article", S.PUBLISHED, S.PUBLISHED),
    "Moderar comentários públicos": Regra(
        "can_moderate_comments", "article", S.PUBLISHED, S.PUBLISHED
    ),
    "Responder comentários como autor": Regra(
        "can_reply_comment", "article", S.PUBLISHED, S.PUBLISHED
    ),
    "Ver perfil público da equipe": Regra("can_view_profile", "profile"),
    "Entrar (Microsoft ou senha)": Regra("can_log_in"),
    "Editar o próprio perfil": Regra("can_edit_profile", "person"),
    "Criar rascunho": Regra("can_create_article"),
    # O revisor edita enquanto a revisão está com ele.
    "Editar rascunho": Regra("can_edit", "article", S.DRAFT, S.IN_REVIEW),
    # O revisor edita o texto, mas não os créditos (docs/17).
    "Creditar alunos e colegas": Regra("can_edit_credits", "article", S.DRAFT, S.IN_REVIEW),
    "Publicar": Regra("can_publish", "article", S.DRAFT, S.IN_REVIEW),
    "Editar publicação publicada": Regra("can_edit", "article", S.PUBLISHED, S.PUBLISHED),
    "Arquivar / despublicar": Regra("can_archive", "article", S.PUBLISHED, S.PUBLISHED),
    # O revisor não reenvia o texto de volta para revisão depois de sugerir alterações.
    "Pedir revisão a um colega": Regra(
        "can_request_review", "article", S.DRAFT, S.CHANGES_REQUESTED
    ),
    "Comentar na revisão (interno)": Regra(
        "can_comment_on_review", "article", S.IN_REVIEW, S.IN_REVIEW
    ),
    # Ninguém revisa o próprio texto (nota abaixo da matriz em docs/02).
    "Aprovar / solicitar alterações em revisão": Regra(
        "can_review", "article", S.IN_REVIEW, S.IN_REVIEW, situacoes=("alheio", "revisor")
    ),
    "Definir destaques da home": Regra("can_feature"),
    "Upload de imagens": Regra("can_upload_media"),
    # Contas, papéis, taxonomia e configurações moram no Django Admin.
    "Criar contas da equipe": Regra("can_access_admin"),
    "Mudar papel de um usuário": Regra("can_access_admin"),
    "Gerenciar áreas, disciplinas, tópicos, tipos": Regra("can_access_admin"),
    "Configurações, auditoria, anonimização": Regra("can_access_admin"),
    "Ver sugestões de pauta (Fase 4)": Regra("can_view_suggestions"),
    "Criar pauta a partir de sugestão (Fase 4)": Regra("can_create_story_idea"),
    # Fontes de notícia são cadastradas no Django Admin (E45).
    "Gerenciar fontes de notícia (Fase 4)": Regra("can_access_admin"),
}


def expandir(simbolo: str, coluna: str, regra: Regra) -> list[tuple[str, bool]]:
    """Célula da matriz → lista de (situação, esperado)."""
    sim = simbolo.startswith("✅")
    if regra.objeto is None:
        return [("sem_objeto", sim)]
    if coluna == "visitante":  # visitante não é dono nem revisor de nada
        return [("alheio", sim)]
    esperado = {
        "proprio": sim or "🔒" in simbolo,
        "alheio": sim,
        "revisor": sim or "🟡" in simbolo,
    }
    situacoes = [s for s in regra.situacoes if s != "revisor" or regra.objeto == "article"]
    if coluna != "equipe":  # editor e admin já podem tudo o que o revisor pode
        situacoes = [s for s in situacoes if s != "revisor"]
    return [(s, esperado[s]) for s in situacoes]


def casos():
    for acao, *celulas in MATRIZ:
        for coluna, simbolo in zip(COLUNAS, celulas, strict=True):
            if acao in FORA_DO_ESCOPO:
                motivo = f"fora do escopo desta fase ({FORA_DO_ESCOPO[acao]})"
                marca = pytest.mark.skip(reason=motivo)
                yield pytest.param(acao, coluna, "-", False, marks=marca, id=f"{acao}|{coluna}")
                continue
            for situacao, esperado in expandir(simbolo, coluna, REGRAS[acao]):
                yield pytest.param(
                    acao, coluna, situacao, esperado, id=f"{acao}|{coluna}|{situacao}"
                )


@pytest.fixture
def pessoas():
    return {
        "visitante": AnonymousUser(),
        "equipe": UserFactory(),
        "editor": UserFactory(editor=True),
        "admin": UserFactory(admin=True),
        "outro": UserFactory(),
    }


def publicacao(dono, estado, revisor=None):
    article = ArticleFactory(author=dono, created_by=dono)
    Article.objects.filter(pk=article.pk).update(status=estado)
    article.refresh_from_db()
    if revisor is not None:
        ArticleContributor.objects.create(
            article=article,
            user=revisor,
            display_name=revisor.public_name,
            role=ArticleContributor.Role.REVIEWER,
        )
    return article


def alvo(regra: Regra, situacao: str, usuario, outro):
    if regra.objeto == "article":
        if situacao == "proprio":
            return publicacao(usuario, regra.estado)
        if situacao == "revisor":
            return publicacao(outro, regra.estado_revisor, revisor=usuario)
        return publicacao(outro, regra.estado)
    dono = usuario if situacao == "proprio" else outro
    return dono.profile if regra.objeto == "profile" else dono


@pytest.mark.parametrize(("acao", "coluna", "situacao", "esperado"), list(casos()))
def test_celula_da_matriz(pessoas, acao, coluna, situacao, esperado):
    regra = REGRAS[acao]
    usuario = pessoas[coluna]
    funcao = getattr(p, regra.funcao)

    if regra.objeto is None:
        resultado = funcao(usuario)
    else:
        resultado = funcao(usuario, alvo(regra, situacao, usuario, pessoas["outro"]))

    assert resultado is esperado


def _tabela_do_documento() -> list[tuple[str, ...]]:
    texto = DOC.read_text(encoding="utf-8")
    bloco = texto.split("## Matriz de permissões", 1)[1].split("\n## ", 1)[0]
    linhas = [linha for linha in bloco.splitlines() if linha.startswith("| ")]
    cabecalho, *corpo = linhas
    assert cabecalho.startswith("| Ação | Visitante | Equipe | Editor | Admin |")
    return [tuple(c.strip() for c in re.split(r"\s*\|\s*", linha.strip("| "))) for linha in corpo]


def test_matriz_espelha_o_documento():
    assert _tabela_do_documento() == MATRIZ


def test_toda_linha_tem_regra_ou_esta_fora_do_escopo():
    acoes = {linha[0] for linha in MATRIZ}
    assert acoes == set(REGRAS) | set(FORA_DO_ESCOPO)
    assert not set(REGRAS) & set(FORA_DO_ESCOPO)


def test_ninguem_revisa_o_proprio_texto(pessoas):
    for coluna in ("equipe", "editor", "admin"):
        usuario = pessoas[coluna]
        assert not p.can_review(usuario, publicacao(usuario, S.IN_REVIEW))


@pytest.mark.parametrize("coluna", ["equipe", "editor", "admin"])
def test_acesso_ao_admin_acompanha_is_staff(pessoas, coluna):
    usuario = pessoas[coluna]
    assert p.can_access_admin(usuario) is usuario.is_staff


def test_conta_desativada_nao_entra_nem_administra():
    admin = UserFactory(admin=True, is_active=False)
    assert not p.can_log_in(admin)
    assert not p.can_access_admin(admin)


def test_perfil_oculto_so_para_o_dono(pessoas):
    perfil = pessoas["equipe"].profile
    perfil.is_public = False
    assert p.can_view_profile(pessoas["equipe"], perfil)
    assert not p.can_view_profile(pessoas["admin"], perfil)
    assert not p.can_view_profile(pessoas["visitante"], perfil)


# --- duplicar (a E29 deixava o revisor duplicar um texto em revisão) ---


def test_revisor_nao_duplica_texto_em_revisao(pessoas):
    article = publicacao(pessoas["outro"], S.IN_REVIEW, revisor=pessoas["equipe"])

    assert p.can_edit(pessoas["equipe"], article)
    assert not p.can_duplicate(pessoas["equipe"], article)
    with pytest.raises(PermissionDenied):
        services.duplicate_article(pessoas["equipe"], article)


def test_autor_e_editor_duplicam(pessoas):
    article = publicacao(pessoas["equipe"], S.PUBLISHED)

    assert p.can_duplicate(pessoas["equipe"], article)
    assert p.can_duplicate(pessoas["editor"], article)
    assert not p.can_duplicate(pessoas["outro"], article)
    assert not p.can_duplicate(pessoas["visitante"], article)


# --- tag {% can %} ---


def render(texto: str, **contexto) -> str:
    return Template("{% load permissions %}" + texto).render(Context(contexto)).strip()


def test_tag_can_com_objeto(pessoas):
    article = publicacao(pessoas["equipe"], S.DRAFT)
    modelo = '{% can "publish" article as ok %}{{ ok }}'

    assert render(modelo, user=pessoas["equipe"], article=article) == "True"
    assert render(modelo, user=pessoas["outro"], article=article) == "False"
    assert render(modelo, user=pessoas["visitante"], article=article) == "False"


def test_tag_can_sem_objeto_e_com_objeto_ausente(pessoas):
    assert render('{% can "feature" as ok %}{{ ok }}', user=pessoas["editor"]) == "True"
    assert render('{% can "feature" as ok %}{{ ok }}', user=pessoas["equipe"]) == "False"
    assert render('{% can "edit" article as ok %}{{ ok }}', user=pessoas["admin"]) == "False"


def test_tag_can_sem_usuario_no_contexto_e_visitante(pessoas):
    assert render('{% can "create_article" as ok %}{{ ok }}') == "False"


def test_tag_can_recusa_acao_desconhecida(pessoas):
    with pytest.raises(TemplateSyntaxError):
        render('{% can "publicar" as ok %}{{ ok }}', user=pessoas["admin"])


def test_tag_can_conhece_todas_as_funcoes_da_matriz():
    for regra in REGRAS.values():
        assert regra.funcao.removeprefix("can_") in ACTIONS


# --- templates que usam a tag ---


@pytest.mark.parametrize(
    ("coluna", "mostra_admin"), [("equipe", False), ("editor", False), ("admin", True)]
)
def test_cabecalho_mostra_admin_so_para_admin(client, pessoas, coluna, mostra_admin):
    client.force_login(pessoas[coluna])

    html = client.get("/").content.decode()

    assert "Escrever" in html
    assert ('href="/admin/"' in html) is mostra_admin


def test_pagina_publica_mostra_editar_so_para_quem_edita(client, pessoas):
    article = publicacao(pessoas["equipe"], S.PUBLISHED)
    url = article.get_absolute_url()
    editar = f"/painel/publicacoes/{article.pk}/editar/"

    assert editar not in client.get(url).content.decode()
    client.force_login(pessoas["outro"])
    assert editar not in client.get(url).content.decode()
    client.force_login(pessoas["equipe"])
    assert editar in client.get(url).content.decode()
