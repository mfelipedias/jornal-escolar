import pytest

from apps.publications import rendering, services
from apps.publications.models import MediaAsset
from tests.factories import ArticleFactory, UserFactory

pytestmark = pytest.mark.django_db


def doc(*blocks):
    return {"type": "doc", "content": list(blocks)}


def p(*inline):
    return {"type": "paragraph", "content": list(inline)}


def t(text, *marks):
    node = {"type": "text", "text": text}
    if marks:
        node["marks"] = list(marks)
    return node


def link(href):
    return {"type": "link", "attrs": {"href": href}}


def make_asset(user=None, **kwargs):
    defaults = {
        "file": "media/2026/09/abc.jpg",
        "variants": {
            "w480": "media/2026/09/abc-w480.webp",
            "w960": "media/2026/09/abc-w960.webp",
            "w1600": "media/2026/09/abc-w1600.webp",
        },
        "width": 2000,
        "height": 1000,
        "size_bytes": 1000,
        "mime": "image/jpeg",
        "uploaded_by": user or UserFactory(),
    }
    defaults.update(kwargs)
    return MediaAsset.objects.create(**defaults)


# --- testes obrigatórios de docs/16 ---


def test_unknown_node_is_not_emitted():
    result = rendering.render(
        doc(p(t("Antes")), {"type": "iframe", "attrs": {"src": "https://evil"}}, p(t("Depois")))
    )

    assert result.html == "<p>Antes</p><p>Depois</p>"
    assert "iframe" not in str(result.document)


@pytest.mark.parametrize(
    "href",
    [
        "javascript:alert(1)",
        "JavaScript:alert(1)",
        " javascript:alert(1)",
        "java\nscript:alert(1)",
        "data:text/html;base64,PHNjcmlwdD4=",
        "vbscript:msgbox",
        "//evil.com/x",
        "http:/sem-host",
    ],
)
def test_dangerous_links_are_dropped(href):
    result = rendering.render(doc(p(t("clique", link(href)))))

    assert result.html == "<p>clique</p>"


def test_image_without_valid_asset_is_not_rendered():
    result = rendering.render(
        doc(
            {"type": "figure", "attrs": {"assetId": 999999}},
            {"type": "figure", "attrs": {"assetId": "abc"}},
            {"type": "figure", "attrs": {}},
        )
    )

    assert result.html == ""
    assert result.is_empty


# --- nós e marcas ---


def test_basic_structure():
    result = rendering.render(
        doc(
            {"type": "heading", "attrs": {"level": 2}, "content": [t("Seção")]},
            {"type": "heading", "attrs": {"level": 1}, "content": [t("H1 vira H2")]},
            {"type": "heading", "attrs": {"level": 4}, "content": [t("H4 vira H3")]},
            p(t("Negrito", {"type": "bold"}), t(" e "), t("itálico", {"type": "italic"})),
            {"type": "bulletList", "content": [{"type": "listItem", "content": [p(t("um"))]}]},
            {
                "type": "orderedList",
                "attrs": {"start": 3},
                "content": [{"type": "listItem", "content": [p(t("três"))]}],
            },
            {
                "type": "blockquote",
                "attrs": {"cite": "Paulo Freire"},
                "content": [p(t("Ninguém educa ninguém."))],
            },
            {"type": "horizontalRule"},
            p(t("linha 1"), {"type": "hardBreak"}, t("linha 2")),
        )
    )

    assert result.html == (
        "<h2>Seção</h2><h2>H1 vira H2</h2><h3>H4 vira H3</h3>"
        "<p><strong>Negrito</strong> e <em>itálico</em></p>"
        "<ul><li><p>um</p></li></ul>"
        '<ol start="3"><li><p>três</p></li></ol>'
        "<blockquote><p>Ninguém educa ninguém.</p><p><cite>Paulo Freire</cite></p></blockquote>"
        "<hr><p>linha 1<br>linha 2</p>"
    )


def test_text_is_escaped():
    result = rendering.render(doc(p(t('<script>alert("x")</script> & <b>'))))

    assert "<script>" not in result.html
    assert "&lt;script&gt;" in result.html
    assert "&amp;" in result.html


def test_unknown_marks_and_attributes_are_dropped():
    result = rendering.render(
        doc(
            {
                "type": "paragraph",
                "attrs": {"class": "x", "style": "color:red", "onclick": "evil()"},
                "content": [
                    t("oi", {"type": "underline"}, {"type": "textStyle", "attrs": {"color": "red"}})
                ],
            }
        )
    )

    assert result.html == "<p>oi</p>"
    assert result.document == doc(p(t("oi")))


def test_safe_links():
    result = rendering.render(
        doc(
            p(t("externo", link("https://www.gov.br/inep"))),
            p(t("interno", link("/sobre/"))),
            p(t("email", link("mailto:contato@escola.sp.gov.br"))),
        )
    )

    assert (
        '<a href="https://www.gov.br/inep" target="_blank" rel="noopener noreferrer">externo</a>'
        in result.html
    )
    assert '<a href="/sobre/">interno</a>' in result.html
    assert '<a href="mailto:contato@escola.sp.gov.br">email</a>' in result.html


def test_attribute_injection_in_href_is_escaped():
    result = rendering.render(doc(p(t("x", link('https://a.com/" onmouseover="alert(1)')))))

    assert ' onmouseover="' not in result.html
    assert result.html.count("<a ") == 1


def test_invalid_documents_become_empty():
    for value in [None, "texto", [], {"type": "paragraph"}, {"type": "doc", "content": "x"}]:
        result = rendering.render(value)
        assert result.html == ""
        assert result.document == {"type": "doc", "content": []}


def test_deeply_nested_document_is_cut():
    node = p(t("fundo"))
    for _ in range(100):
        node = {"type": "blockquote", "content": [node]}

    result = rendering.render(doc(node))

    assert "fundo" not in result.html


def test_empty_blocks_are_not_emitted():
    result = rendering.render(
        doc(p(), {"type": "heading", "attrs": {"level": 2}}, {"type": "bulletList"})
    )

    assert result.html == ""
    assert result.is_empty


# --- figura ---


def test_figure_with_asset():
    asset = make_asset(alt_text="Alt salvo", credit="Foto: Grêmio")

    result = rendering.render(
        doc(
            {
                "type": "figure",
                "attrs": {"assetId": asset.pk, "caption": "Feira de ciências", "size": "wide"},
            }
        )
    )

    html = result.html
    assert html.startswith('<figure class="figure figure--wide"><img ')
    assert 'src="/media/media/2026/09/abc-w960.webp"' in html
    assert 'srcset="/media/media/2026/09/abc-w480.webp 480w' in html
    assert 'alt="Alt salvo"' in html
    assert 'width="2000" height="1000"' in html
    assert 'loading="lazy"' in html
    assert (
        '<figcaption>Feira de ciências<span class="figure-credit">Foto: Grêmio</span></figcaption>'
        in html
    )
    assert result.asset_ids == {asset.pk}
    assert not result.is_empty


def test_decorative_figure_has_empty_alt():
    asset = make_asset(alt_text="não usar", is_decorative=True)

    result = rendering.render(doc({"type": "figure", "attrs": {"assetId": asset.pk, "alt": "x"}}))

    assert 'alt=""' in result.html


def test_figure_attributes_are_escaped():
    asset = make_asset()

    result = rendering.render(
        doc(
            {
                "type": "figure",
                "attrs": {"assetId": asset.pk, "alt": '"><script>x</script>', "caption": "<b>"},
            }
        )
    )

    assert "<script>" not in result.html
    assert "<b>" not in result.html


def test_figures_limited_to_allowed_assets():
    mine, other = make_asset(), make_asset()

    result = rendering.render(
        doc(
            {"type": "figure", "attrs": {"assetId": mine.pk}},
            {"type": "figure", "attrs": {"assetId": other.pk}},
        ),
        allowed_assets={mine.pk},
    )

    assert result.asset_ids == {mine.pk}
    assert result.html.count("<figure") == 1


# --- texto e leitura ---


def test_text_and_reading_time():
    words = " ".join(["palavra"] * 401)

    result = rendering.render(
        doc({"type": "heading", "attrs": {"level": 2}, "content": [t("Título")]}, p(t(words)))
    )

    assert result.text.startswith("Título\n\npalavra")
    assert result.words == 402
    assert result.reading_minutes == 3


def test_minimum_reading_time_is_one_minute():
    assert rendering.render(doc(p(t("curto")))).reading_minutes == 1


# --- integração com services ---


def test_update_article_renders_body(staff_user):
    article = services.create_article(staff_user)

    services.update_article(
        staff_user,
        article,
        body_json=doc(p(t("Olá, ", {"type": "bold"}), t("mundo")), {"type": "iframe"}),
    )

    article.refresh_from_db()
    assert article.body_html == "<p><strong>Olá, </strong>mundo</p>"
    assert article.body_text == "Olá, mundo"
    assert article.reading_minutes == 1
    assert article.body_json == doc(p(t("Olá, ", {"type": "bold"}), t("mundo")))


def test_update_article_links_own_images_and_drops_others(staff_user):
    article = services.create_article(staff_user)
    mine = make_asset(staff_user)
    someone_elses = make_asset(UserFactory())

    services.update_article(
        staff_user,
        article,
        body_json=doc(
            p(t("texto")),
            {"type": "figure", "attrs": {"assetId": mine.pk}},
            {"type": "figure", "attrs": {"assetId": someone_elses.pk}},
        ),
    )

    article.refresh_from_db()
    mine.refresh_from_db()
    someone_elses.refresh_from_db()
    assert article.body_html.count("<figure") == 1
    assert mine.article == article
    assert someone_elses.article is None


def test_image_of_another_article_cannot_be_reused_by_staff(staff_user):
    other_article = ArticleFactory(author=staff_user, created_by=staff_user)
    asset = make_asset(staff_user, article=other_article)
    article = services.create_article(staff_user)

    services.update_article(
        staff_user, article, body_json=doc({"type": "figure", "attrs": {"assetId": asset.pk}})
    )

    assert "<figure" not in stored_html(article)


def test_editor_can_use_any_image(editor_user):
    asset = make_asset(UserFactory())
    article = ArticleFactory(author=editor_user, created_by=editor_user)

    services.update_article(
        editor_user, article, body_json=doc({"type": "figure", "attrs": {"assetId": asset.pk}})
    )

    assert "<figure" in stored_html(article)


def test_checklist_uses_renderer():
    article = ArticleFactory(
        ready=True, body_json=doc({"type": "figure", "attrs": {"assetId": 123456}})
    )

    assert "body_empty" in {item.code for item in services.checklist(article) if item.blocking}


def stored_html(article):
    article.refresh_from_db()
    return article.body_html
