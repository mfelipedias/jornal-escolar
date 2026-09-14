"""SEO da página de publicação: Open Graph, JSON-LD e compartilhar (docs/11, docs/23, E26)."""

import json
import re

import pytest

from apps.core.models import SiteSetting
from apps.core.site_settings import clear_cache
from apps.publications import seo as article_seo
from apps.publications import services
from apps.publications.models import Article, ArticleContributor, MediaAsset
from tests.factories import (
    ArticleFactory,
    ArticleTypeFactory,
    DisciplineFactory,
    KnowledgeAreaFactory,
    UserFactory,
    text_doc,
)

pytestmark = pytest.mark.django_db

SITE = "https://jornal.exemplo.org"
JSON_LD_RE = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)


def json_ld(html: str) -> list[dict]:
    """Todos os blocos JSON-LD da página; falha se algum não for JSON válido."""
    return [json.loads(block) for block in JSON_LD_RE.findall(html)]


def meta(html: str, prop: str) -> str | None:
    match = re.search(rf'<meta (?:property|name)="{re.escape(prop)}" content="([^"]*)"', html)
    return match.group(1) if match else None


@pytest.fixture(autouse=True)
def site_url(settings):
    settings.SITE_URL = SITE


@pytest.fixture
def author():
    user = UserFactory(full_name="Carla Souza", email="carla@professor.educacao.sp.gov.br")
    user.profile.headline = "Professora de Biologia"
    user.profile.save()
    return user


@pytest.fixture
def published(author):
    area = KnowledgeAreaFactory(name="Ciências da Natureza")
    article = ArticleFactory(
        ready=True,
        author=author,
        created_by=author,
        title="Feira de Ciências",
        subtitle="Projetos de energia solar",
        type=ArticleTypeFactory(name="Notícia", slug="noticia"),
        disciplines=[DisciplineFactory(name="Física", area=area)],
    )
    services.update_article(author, article, body_json=text_doc("Texto </script> com <b>."))
    services.add_student_credit(
        author, article, name="Rafael S.", class_group="2ª série B", consent_ok=True
    )
    hidden = services.add_student_credit(
        author, article, name="Bruna T.", class_group="1ª série A", consent_ok=True
    )
    ArticleContributor.objects.filter(pk=hidden.pk).update(show_in_credits=False)
    services.add_guest_credit(author, article, name="Grêmio Estudantil", contribution_note="fotos")
    services.publish(author, article)
    return Article.objects.get(pk=article.pk)


def test_news_article_json_ld_has_required_fields(client, published, author):
    html = client.get(published.get_absolute_url()).content.decode()

    [data] = json_ld(html)
    url = f"{SITE}{published.get_absolute_url()}"
    assert data["@context"] == "https://schema.org"
    assert data["@type"] == "NewsArticle"
    assert data["headline"] == "Feira de Ciências"
    assert data["description"] == "Projetos de energia solar"
    assert data["url"] == url
    assert data["mainEntityOfPage"] == {"@type": "WebPage", "@id": url}
    assert data["datePublished"].startswith(published.published_at.date().isoformat())
    assert data["dateModified"] >= data["datePublished"]
    assert data["inLanguage"] == "pt-BR"
    assert data["articleSection"] == "Ciências da Natureza"
    assert data["keywords"] == "Física"
    publisher = data["publisher"]
    assert publisher["@type"] == "NewsMediaOrganization"
    assert publisher["name"] == "Jornal Escolar"
    assert publisher["url"] == f"{SITE}/"
    assert publisher["logo"]["url"] == f"{SITE}/static/img/logo.png"


def test_authors_staff_with_profile_url_students_only_name(client, published, author):
    html = client.get(published.get_absolute_url()).content.decode()

    [data] = json_ld(html)
    assert data["author"] == [
        {
            "@type": "Person",
            "name": "Carla Souza",
            "url": f"{SITE}{author.profile.get_absolute_url()}",
        },
        {"@type": "Person", "name": "Rafael S."},
    ]


def test_json_ld_has_no_private_data(client, published):
    html = client.get(published.get_absolute_url()).content.decode()

    [block] = JSON_LD_RE.findall(html)
    for private in (
        "2ª série",  # turma do aluno
        "1ª série",
        "Bruna T.",  # crédito oculto
        "Aluno",
        "consent",
        "@professor.educacao.sp.gov.br",
        "email",
        "worksFor",
        "Grêmio Estudantil",  # colaboração não é autoria
    ):
        assert private not in block
    assert "</script" not in block


def test_publisher_follows_site_name_setting(client, published):
    SiteSetting.objects.create(key="site.name", value="Folha da Turma")
    clear_cache()

    html = client.get(published.get_absolute_url()).content.decode()

    [data] = json_ld(html)
    assert data["publisher"]["name"] == "Folha da Turma"
    assert meta(html, "og:site_name") == "Folha da Turma"


def test_open_graph_and_canonical(client, published):
    html = client.get(published.get_absolute_url()).content.decode()
    url = f"{SITE}{published.get_absolute_url()}"

    assert f'<link rel="canonical" href="{url}">' in html
    assert meta(html, "og:type") == "article"
    assert meta(html, "og:title") == "Feira de Ciências"
    assert meta(html, "og:description") == "Projetos de energia solar"
    assert meta(html, "og:url") == url
    assert meta(html, "og:locale") == "pt_BR"
    assert meta(html, "og:image") == f"{SITE}/static/img/og-default.png"
    assert meta(html, "twitter:card") == "summary_large_image"
    assert meta(html, "article:published_time")


def test_cover_is_og_image_in_1600_variant(client, published, author):
    cover = MediaAsset.objects.create(
        file="media/2026/09/capa.jpg",
        variants={"w480": "media/2026/09/capa-w480.webp", "w1600": "media/2026/09/capa-w1600.webp"},
        width=3000,
        height=2000,
        size_bytes=1000,
        mime="image/jpeg",
        alt_text="Painéis solares",
        uploaded_by=author,
    )
    Article.objects.filter(pk=published.pk).update(cover=cover)

    html = client.get(published.get_absolute_url()).content.decode()

    image = f"{SITE}/media/media/2026/09/capa-w1600.webp"
    assert meta(html, "og:image") == image
    assert meta(html, "og:image:width") == "1600"
    assert meta(html, "og:image:height") == "1067"
    assert meta(html, "og:image:alt") == "Painéis solares"
    [data] = json_ld(html)
    assert data["image"] == [image]


@pytest.mark.parametrize(
    ("slug", "expected"),
    [
        ("noticia", "NewsArticle"),
        ("reportagem", "NewsArticle"),
        ("entrevista", "NewsArticle"),
        ("projeto", "Article"),
        ("resenha", "Article"),
    ],
)
def test_schema_type_by_article_type(slug, expected):
    article = Article(type=ArticleTypeFactory(slug=slug, name=slug))

    assert article_seo.schema_type(article) == expected


def test_article_without_type_is_article():
    assert article_seo.schema_type(Article()) == "Article"


def test_hidden_profile_author_has_no_url(client, published, author):
    author.profile.is_public = False
    author.profile.save()

    html = client.get(published.get_absolute_url()).content.decode()

    [data] = json_ld(html)
    assert data["author"][0] == {"@type": "Person", "name": "Carla Souza"}


def test_preview_is_noindex_without_json_ld(client, author):
    draft = ArticleFactory(author=author, created_by=author, title="Rascunho")
    client.force_login(author)

    html = client.get(draft.get_absolute_url()).content.decode()

    assert '<meta name="robots" content="noindex">' in html
    assert 'rel="canonical"' not in html
    assert meta(html, "og:url") is None
    assert json_ld(html) == []


def test_share_uses_canonical_url(client, published):
    html = client.get(published.get_absolute_url()).content.decode()
    url = f"{SITE}{published.get_absolute_url()}"

    assert 'x-data="share"' in html
    assert f'data-url="{url}"' in html
    assert "https://wa.me/?text=Feira%20de%20Ci%C3%AAncias%20https%3A%2F%2Fjornal" in html
    assert "connect.facebook" not in html
    assert "platform.twitter" not in html
