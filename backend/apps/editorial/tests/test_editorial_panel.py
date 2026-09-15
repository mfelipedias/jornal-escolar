"""Painel editorial (E33, docs/18): visão geral, alertas, todas as publicações e ações em massa.

Aceite: os alertas aparecem. Cada alerta tem um cenário montado com fábricas; o teste confere
que ele aparece na tela e que some quando a condição deixa de valer.
"""

from datetime import timedelta

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse
from django.utils import timezone

from apps.dashboard.menu import menu_items
from apps.editorial import alerts, permissions, selectors
from apps.editorial import services as comments
from apps.editorial.models import EditorialComment, EditorialEvent, Notification
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

S = Article.Status
OVERVIEW = "/painel/editorial/"
ARTICLES = "/painel/editorial/publicacoes/"
BULK = "/painel/editorial/publicacoes/acoes/"


@pytest.fixture
def author():
    return UserFactory(full_name="Carla Souza")


@pytest.fixture
def reviewer():
    return UserFactory(full_name="Marcos Lima")


@pytest.fixture
def editor_client(client, editor_user):
    client.force_login(editor_user)
    return client


def in_review(author, reviewer, title="Em leitura", **kwargs):
    article = ArticleFactory(ready=True, author=author, created_by=author, title=title, **kwargs)
    services.request_review(author, article, reviewer, note="Pode ler?")
    article.refresh_from_db()
    return article


def age(article: Article, days: int) -> None:
    """Empurra o pedido de revisão e todos os eventos da publicação para o passado."""
    when = timezone.now() - timedelta(days=days)
    Article.objects.filter(pk=article.pk).update(submitted_at=when)
    EditorialEvent.objects.filter(article=article).update(created_at=when)


def published(author, title="No ar", **kwargs):
    article = ArticleFactory(ready=True, author=author, created_by=author, title=title, **kwargs)
    services.publish(author, article)
    article.refresh_from_db()
    return article


def overview_html(client) -> str:
    response = client.get(OVERVIEW)
    assert response.status_code == 200
    return response.content.decode()


def alert_block(html: str, key: str) -> str:
    """Trecho da página com o grupo de alertas; vazio se o grupo não aparece."""
    marker = f'data-alert-group="{key}"'
    if marker not in html:
        return ""
    return html.split(marker, 1)[1].split("</section>", 1)[0]


# --- acesso, menu e abas ---


def test_urls():
    assert reverse("editorial:overview") == OVERVIEW
    assert reverse("editorial:articles") == ARTICLES
    assert reverse("editorial:bulk_action") == BULK


@pytest.mark.parametrize("url", [OVERVIEW, ARTICLES])
def test_only_editors_open_the_panel(client, staff_user, editor_user, admin_user, url):
    assert client.get(url).status_code == 302
    client.force_login(staff_user)
    assert client.get(url).status_code == 403
    assert client.post(BULK, {"acao": "arquivar"}).status_code == 403
    for user in (editor_user, admin_user):
        client.force_login(user)
        assert client.get(url).status_code == 200


def test_permissions(staff_user, editor_user, admin_user, author, reviewer):
    article = in_review(author, reviewer)
    draft = ArticleFactory(author=author, created_by=author)
    assert not permissions.can_access_editorial(staff_user)
    assert permissions.can_access_editorial(editor_user)
    assert permissions.can_access_editorial(admin_user)
    assert permissions.can_reassign_reviewer(editor_user, article)
    assert not permissions.can_reassign_reviewer(editor_user, draft)
    assert not permissions.can_reassign_reviewer(author, article)
    assert not permissions.can_reassign_reviewer(reviewer, article)


def test_menu_groups_featured_and_pages_under_editorial(staff_user, editor_user, admin_user):
    assert "editorial" not in [item.key for item in menu_items(staff_user)]
    for user in (editor_user, admin_user):
        keys = [item.key for item in menu_items(user)]
        assert "editorial" in keys
        assert {"featured", "pages"}.isdisjoint(keys)
        assert keys.index("reviews") < keys.index("editorial") < keys.index("profile")
    for view in (
        "editorial:overview",
        "editorial:articles",
        "editorial:featured",
        "core:page_list",
    ):
        active = [item.key for item in menu_items(editor_user, view) if item.active]
        assert active == ["editorial"]


@pytest.mark.parametrize(
    ("url", "current"),
    [
        (OVERVIEW, "Visão geral"),
        (ARTICLES, "Todas as publicações"),
        ("/painel/destaques/", "Destaques"),
        ("/painel/paginas/", "Páginas"),
    ],
)
def test_sections_share_tabs_and_keep_addresses(editor_client, url, current):
    html = editor_client.get(url).content.decode()

    nav = html.split('aria-label="Seções do editorial"', 1)[1].split("</nav>", 1)[0]
    for href in (OVERVIEW, ARTICLES, "/painel/destaques/", "/painel/paginas/"):
        assert f'href="{href}"' in nav
    assert f'aria-current="page">{current}</a>' in nav
    assert 'href="/painel/editorial/"' in html.split('aria-label="Menu do painel"', 1)[1]


def test_staff_panel_does_not_link_to_editorial(client, staff_user):
    client.force_login(staff_user)
    assert OVERVIEW not in client.get("/painel/").content.decode()


# --- visão geral: contadores ---


def test_counts_by_state(editor_client, author, reviewer):
    ArticleFactory(author=author, created_by=author)
    ArticleFactory(author=author, created_by=author)
    in_review(author, reviewer)
    recent = published(author, "Recente")
    old = published(author, "Antiga")
    Article.objects.filter(pk=old.pk).update(published_at=timezone.now() - timedelta(days=40))
    archived = published(author, "Guardada")
    services.archive(author, archived)
    changes = in_review(author, reviewer, "Com sugestões")
    comments.add_comment(reviewer, changes, "Revise o título.")
    services.request_changes(reviewer, changes)
    resolved = comments.add_comment(reviewer, changes, "Outro ponto.")
    comments.resolve(reviewer, resolved)
    comments.add_comment(author, recent, "Comentário esquecido.")  # publicada: conta

    counts = selectors.editorial_counts()

    assert counts == {
        "drafts": 2,
        "in_review": 1,
        "changes_requested": 1,
        "published_recent": 1,
        "archived": 1,
        "open_comments": 2,
    }
    html = overview_html(editor_client)
    assert f'href="{ARTICLES}?estado=rascunhos"' in html
    assert "Publicadas nos últimos 30 dias" in html


def test_drafts_by_author(editor_client, author, reviewer):
    ArticleFactory(author=author, created_by=author)
    ArticleFactory(author=author, created_by=author)
    ArticleFactory(author=reviewer, created_by=reviewer)
    published(reviewer)

    people = selectors.draft_authors()

    assert [(p.full_name, p.drafts) for p in people] == [("Carla Souza", 2), ("Marcos Lima", 1)]
    html = overview_html(editor_client)
    assert f"?estado=rascunhos&amp;autor={author.pk}" in html


def test_no_alerts_message(editor_client):
    html = overview_html(editor_client)
    assert "data-no-alerts" in html
    assert "data-alert-group" not in html


# --- alertas: revisão parada ---


def test_stale_review_appears_and_goes_away_with_activity(editor_client, author, reviewer):
    article = in_review(author, reviewer, "Parada")
    fresh = in_review(author, reviewer, "Recente")
    age(fresh, alerts.STALE_REVIEW_DAYS - 1)
    age(article, alerts.STALE_REVIEW_DAYS + 2)

    block = alert_block(overview_html(editor_client), "revisoes-paradas")
    assert f'data-article="{article.pk}"' in block
    assert f'data-article="{fresh.pk}"' not in block
    assert "com Marcos Lima, sem movimento há 7 dias" in block
    assert reverse("editorial:review", args=[article.pk]) in block

    comments.add_comment(reviewer, article, "Comecei a ler.")  # gera evento: há movimento

    assert alert_block(overview_html(editor_client), "revisoes-paradas") == ""


def test_stale_review_goes_away_when_review_ends(editor_client, author, reviewer):
    article = in_review(author, reviewer, "Parada")
    age(article, 10)
    assert alert_block(overview_html(editor_client), "revisoes-paradas")

    services.cancel_review(author, article)

    assert alert_block(overview_html(editor_client), "revisoes-paradas") == ""


def test_stale_review_goes_away_when_reviewer_is_replaced(editor_client, editor_user, author):
    old, new = UserFactory(), UserFactory()
    article = in_review(author, old, "Parada")
    age(article, 10)
    assert alert_block(overview_html(editor_client), "revisoes-paradas")

    services.reassign_reviewer(editor_user, article, new)

    assert alert_block(overview_html(editor_client), "revisoes-paradas") == ""


# --- alertas: comentários da revisão sem resposta ---


def backdate(comment: EditorialComment, days: int) -> None:
    EditorialComment.objects.filter(pk=comment.pk).update(
        created_at=timezone.now() - timedelta(days=days)
    )


def test_stale_comment_appears_and_goes_away_with_reply(editor_client, author, reviewer):
    article = in_review(author, reviewer, "Com sugestões")
    old = comments.add_comment(reviewer, article, "O título está longo.")
    recent = comments.add_comment(reviewer, article, "Faltou a fonte.")
    services.request_changes(reviewer, article)
    backdate(old, alerts.STALE_COMMENT_DAYS + 1)
    backdate(recent, alerts.STALE_COMMENT_DAYS - 1)

    block = alert_block(overview_html(editor_client), "comentarios-parados")
    assert f'data-article="{article.pk}"' in block
    assert "1 comentário aberto sem resposta há 4 dias (alterações sugeridas)" in block

    comments.reply(author, EditorialComment.objects.get(pk=old.pk), "Vou encurtar.")

    assert alert_block(overview_html(editor_client), "comentarios-parados") == ""


def test_stale_comment_goes_away_when_resolved_or_published(editor_client, author, reviewer):
    article = in_review(author, reviewer, "Com sugestões")
    first = comments.add_comment(reviewer, article, "Primeiro.")
    second = comments.add_comment(reviewer, article, "Segundo.")
    services.request_changes(reviewer, article)
    backdate(first, 5)
    backdate(second, 6)
    assert "2 comentários abertos sem resposta há 6 dias" in alert_block(
        overview_html(editor_client), "comentarios-parados"
    )

    comments.resolve(author, EditorialComment.objects.get(pk=first.pk))
    assert "1 comentário aberto sem resposta" in alert_block(
        overview_html(editor_client), "comentarios-parados"
    )

    services.publish(author, Article.objects.get(pk=article.pk))  # texto saiu do andamento
    assert alert_block(overview_html(editor_client), "comentarios-parados") == ""


def test_old_reply_still_counts_as_stale(author, reviewer):
    article = in_review(author, reviewer)
    comment = comments.add_comment(reviewer, article, "Ponto.")
    answer = comments.reply(author, comment, "Resposta antiga.")
    backdate(comment, 9)
    backdate(answer, 4)

    group = alerts.stale_comments()

    assert [a.article.pk for a in group.items] == [article.pk]
    assert "há 4 dias" in group.items[0].message


# --- alertas: autorização de alunos e de imagens ---


def test_student_without_consent_appears_and_goes_away(editor_client, author):
    article = published(author, "Feira de ciências")
    credit = ArticleContributor.objects.create(
        article=article, display_name="Ana", is_student=True, consent_ok=False, order=2
    )
    draft = ArticleFactory(author=author, created_by=author, title="Rascunho com aluno")
    ArticleContributor.objects.create(
        article=draft, display_name="Bia", is_student=True, consent_ok=False, order=2
    )

    block = alert_block(overview_html(editor_client), "alunos-sem-autorizacao")
    assert f'data-article="{article.pk}"' in block
    assert f'data-article="{draft.pk}"' not in block  # a checklist ainda vai barrar
    assert "1 crédito de aluno sem autorização marcada" in block
    assert reverse("publications:edit", args=[article.pk]) in block
    assert "Ana" not in block  # nome do aluno não vai para o alerta

    credit.consent_ok = True
    credit.save()

    assert alert_block(overview_html(editor_client), "alunos-sem-autorizacao") == ""


def image(author, article=None, **fields):
    return MediaAsset.objects.create(
        file="media/foto.jpg",
        uploaded_by=author,
        article=article,
        width=1600,
        height=900,
        size_bytes=1,
        mime="image/jpeg",
        alt_text="Foto",
        **fields,
    )


def figure_doc(asset_id: int) -> dict:
    doc = text_doc()
    doc["content"].append({"type": "figure", "attrs": {"assetId": asset_id}})
    return doc


def test_image_without_consent_appears_and_goes_away(editor_client, author):
    cover_article = published(author, "Capa com pessoas")
    cover = image(author, cover_article, has_people=True, consent_ok=False)
    Article.objects.filter(pk=cover_article.pk).update(cover=cover)
    loose = published(author, "Imagem fora do texto")
    image(author, loose, has_people=True, consent_ok=False)  # ligada, mas não aparece
    unflagged = published(author, "Paisagem")
    Article.objects.filter(pk=unflagged.pk).update(cover=image(author, unflagged))

    block = alert_block(overview_html(editor_client), "imagens-sem-autorizacao")
    assert f'data-article="{cover_article.pk}"' in block
    assert f'data-article="{loose.pk}"' not in block
    assert f'data-article="{unflagged.pk}"' not in block

    MediaAsset.objects.filter(pk=cover.pk).update(consent_ok=True)

    assert alert_block(overview_html(editor_client), "imagens-sem-autorizacao") == ""


def test_image_in_body_counts(author):
    article = published(author, "Corpo com foto")
    asset = image(author, article, has_people=True, consent_ok=False)
    Article.objects.filter(pk=article.pk).update(body_json=figure_doc(asset.pk))

    assert [a.article.pk for a in alerts.image_consent().items] == [article.pk]


def test_home_shows_alert_count_to_editors_only(client, editor_user, staff_user, author):
    article = published(author)
    ArticleContributor.objects.create(
        article=article, display_name="Ana", is_student=True, consent_ok=False, order=2
    )
    client.force_login(editor_user)
    html = client.get("/painel/").content.decode()
    assert "data-editorial-alerts" in html
    assert "1 alerta no editorial" in html

    client.force_login(staff_user)
    assert "data-editorial-alerts" not in client.get("/painel/").content.decode()


# --- todas as publicações: filtros ---


@pytest.fixture
def catalog(author, reviewer):
    news = ArticleTypeFactory(name="Notícia", slug="noticia")
    area = KnowledgeAreaFactory(name="Natureza", slug="natureza")
    other_area = KnowledgeAreaFactory(name="Humanas", slug="humanas")
    bio = DisciplineFactory(area=area, slug="biologia")
    hist = DisciplineFactory(area=other_area, slug="historia")
    other = UserFactory(full_name="Paula Reis")
    a = published(author, "Horta da escola", type=news, disciplines=[bio])
    b = in_review(other, reviewer, "Viagem ao museu", disciplines=[hist])
    c = ArticleFactory(author=other, created_by=other, title="Rascunho da horta")
    Article.objects.filter(pk=c.pk).update(updated_at=timezone.now() - timedelta(days=60))
    return {"a": a, "b": b, "c": c, "other": other, "reviewer": reviewer, "author": author}


def titles(client, query="") -> list[str]:
    response = client.get(ARTICLES + query)
    assert response.status_code == 200
    return [row["article"].title for row in response.context["rows"]]


def test_lists_everything_by_update(editor_client, catalog):
    assert titles(editor_client) == ["Viagem ao museu", "Horta da escola", "Rascunho da horta"]


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("?estado=publicados", ["Horta da escola"]),
        ("?estado=em-revisao", ["Viagem ao museu"]),
        ("?estado=inventado", ["Viagem ao museu", "Horta da escola", "Rascunho da horta"]),
        ("?tipo=noticia", ["Horta da escola"]),
        ("?area=humanas", ["Viagem ao museu"]),
        ("?q=HORTA", ["Horta da escola", "Rascunho da horta"]),
        ("?periodo=30", ["Viagem ao museu", "Horta da escola"]),
        ("?estado=rascunhos&q=horta", ["Rascunho da horta"]),
    ],
)
def test_filters(editor_client, catalog, query, expected):
    assert titles(editor_client, query) == expected


def test_filter_by_author_and_reviewer(editor_client, catalog):
    other, reviewer = catalog["other"], catalog["reviewer"]
    assert titles(editor_client, f"?autor={other.pk}") == ["Viagem ao museu", "Rascunho da horta"]
    assert titles(editor_client, f"?revisor={reviewer.pk}") == ["Viagem ao museu"]
    assert titles(editor_client, f"?autor={reviewer.pk}") == []
    assert titles(editor_client, "?autor=abc")  # valor inválido é ignorado


def test_rows_link_to_review_and_show_people(editor_client, catalog):
    html = editor_client.get(ARTICLES + "?estado=em-revisao").content.decode()
    b = catalog["b"]
    assert f'href="{reverse("editorial:review", args=[b.pk])}"' in html
    assert "Paula Reis" in html
    assert "Marcos Lima" in html
    assert 'name="ids"' in html


def test_empty_with_filters(editor_client, catalog):
    html = editor_client.get(ARTICLES + "?q=nada-assim").content.decode()
    assert "Nada com esses filtros" in html


# --- ações em massa ---


def test_bulk_archive_requires_note(editor_client, catalog):
    a = catalog["a"]
    response = editor_client.post(BULK, {"acao": "arquivar", "ids": [a.pk]}, follow=True)

    assert "Explique o motivo" in response.content.decode()
    assert Article.objects.get(pk=a.pk).status == S.PUBLISHED


def test_bulk_archive(editor_client, editor_user, catalog):
    a, c = catalog["a"], catalog["c"]
    services.archive(editor_user, catalog["b"], note="Duplicada")
    b = catalog["b"]
    next_url = ARTICLES + "?estado=publicados"

    response = editor_client.post(
        BULK,
        {
            "acao": "arquivar",
            "ids": [a.pk, c.pk, b.pk, a.pk],
            "note": "Pedido da família",
            "next": next_url,
        },
    )

    assert response.status_code == 302
    assert response.url == next_url
    assert Article.objects.get(pk=a.pk).status == S.ARCHIVED
    assert Article.objects.get(pk=c.pk).status == S.ARCHIVED
    event = EditorialEvent.objects.filter(article=a, to_status=S.ARCHIVED).get()
    assert event.note == "Pedido da família"
    assert event.actor == editor_user
    texts = [str(m) for m in response.wsgi_request._messages]
    assert "2 publicações arquivadas." in texts
    assert any("Viagem ao museu" in t and "já está arquivada" in t for t in texts)


def test_bulk_rejects_outside_next_and_empty_selection(editor_client, catalog):
    response = editor_client.post(
        BULK, {"acao": "arquivar", "note": "x", "next": "https://exemplo.com/"}
    )
    assert response.url == ARTICLES
    assert "Marque ao menos uma" in str(next(iter(response.wsgi_request._messages)))
    response = editor_client.post(BULK, {"acao": "apagar", "ids": [catalog["a"].pk]})
    assert any("Escolha uma ação" in str(m) for m in response.wsgi_request._messages)


def test_bulk_reassign_reviewer(editor_client, editor_user, catalog):
    b, a = catalog["b"], catalog["a"]
    old, other = catalog["reviewer"], catalog["other"]
    ArticleContributor.objects.filter(article=b, role="reviewer").update(can_publish=True)
    new = UserFactory(full_name="Nina Alves")

    response = editor_client.post(
        BULK,
        {"acao": "trocar-revisor", "ids": [b.pk, a.pk], "reviewer": new.pk, "note": "Urgente"},
    )

    credit = permissions.reviewer_credit(b)
    assert credit.user == new
    assert credit.can_publish is False
    assert Article.objects.get(pk=b.pk).status == S.IN_REVIEW
    kinds = list(
        EditorialEvent.objects.filter(article=b).order_by("-pk").values_list("kind", flat=True)[:2]
    )
    assert kinds == [EditorialEvent.Kind.REVIEWER_ASSIGNED, EditorialEvent.Kind.REVIEWER_REMOVED]
    assert Notification.objects.filter(user=new, kind="review_requested", article=b).exists()
    assert "outro colega" in Notification.objects.get(user=old, article=b, kind="system").message
    assert "Nina Alves" in Notification.objects.get(user=other, article=b, kind="system").message
    texts = [str(m) for m in response.wsgi_request._messages]
    assert "1 publicação com revisor trocado." in texts
    assert any("Horta da escola" in t and "não está em revisão" in t for t in texts)


def test_bulk_reassign_requires_reviewer(editor_client, catalog):
    response = editor_client.post(BULK, {"acao": "trocar-revisor", "ids": [catalog["b"].pk]})
    assert "Escolha o colega" in str(next(iter(response.wsgi_request._messages)))


def test_reassign_rules(editor_user, staff_user, catalog):
    b = catalog["b"]
    with pytest.raises(PermissionDenied):
        services.reassign_reviewer(staff_user, b, UserFactory())
    with pytest.raises(ValidationError):
        services.reassign_reviewer(editor_user, b, catalog["other"])  # autora do texto
    with pytest.raises(ValidationError):
        services.reassign_reviewer(editor_user, b, catalog["reviewer"])  # já é o revisor
    with pytest.raises(PermissionDenied):
        services.reassign_reviewer(editor_user, catalog["a"], UserFactory())  # publicada
