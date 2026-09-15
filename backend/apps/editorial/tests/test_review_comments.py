"""Comentários editoriais da revisão (E32, docs/17 "Comentários editoriais").

Aceite: a âncora sobrevive a edição de outro trecho. Editar outro parágrafo do documento
(JSON ProseMirror) muda as posições, mas o comentário continua apontando para o mesmo trecho;
mexer no próprio trecho mostra "trecho alterado", sem esconder o comentário.
"""

from html.parser import HTMLParser

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse

from apps.editorial import anchors, selectors
from apps.editorial import services as comments
from apps.editorial.models import EditorialComment, EditorialEvent, Notification
from apps.publications import rendering, services
from apps.publications.models import Article
from tests.factories import ArticleFactory, UserFactory

pytestmark = pytest.mark.django_db

S = Article.Status
HTMX = {"HTTP_HX_REQUEST": "true"}
QUOTE = "a água ferve a 100 graus"


def paragraph(text: str) -> dict:
    return {"type": "paragraph", "content": [{"type": "text", "text": text}]}


def doc(*texts: str) -> dict:
    return {"type": "doc", "content": [paragraph(t) for t in texts]}


# O trecho aparece duas vezes: só o contexto diz qual das duas foi comentada.
PARAGRAPHS = (
    "Introdução do experimento.",
    f"Na cozinha da escola, {QUOTE} ao nível do mar.",
    f"Na serra, ninguém diz que {QUOTE}: depende da pressão.",
)


@pytest.fixture
def author():
    return UserFactory(full_name="Carla Souza")


@pytest.fixture
def reviewer():
    return UserFactory(full_name="Marcos Lima")


@pytest.fixture
def article(author, reviewer):
    article = ArticleFactory(ready=True, author=author, created_by=author, title="Água")
    services.update_article(author, article, body_json=doc(*PARAGRAPHS))
    services.request_review(author, article, reviewer, note="Confere os dados?")
    article.refresh_from_db()
    return article


def selection_of(article: Article, occurrence: int = 0) -> dict:
    """O que o navegador manda ao comentar um trecho (review-comments.js, readSelection)."""
    text = anchors.document_text(article.body_json)
    start = -1
    for _ in range(occurrence + 1):
        start = text.index(QUOTE, start + 1)
    end = start + len(QUOTE)
    prefix, suffix = anchors.context(text, start, end)
    return {
        "anchor_text": QUOTE,
        "anchor_prefix": prefix,
        "anchor_suffix": suffix,
        "anchor_from": str(start),
    }


def thread_for(article: Article, comment: EditorialComment) -> selectors.CommentThread:
    board = selectors.comment_board(Article.objects.get(pk=article.pk))
    return next(t for t in [*board.open, *board.resolved] if t.comment.pk == comment.pk)


def located_text(article: Article, thread: selectors.CommentThread) -> str:
    text = anchors.document_text(Article.objects.get(pk=article.pk).body_json)
    return text[thread.anchor_start : thread.anchor_end]


def review_url(article):
    return reverse("editorial:review", args=[article.pk])


# --- aceite: a âncora sobrevive a edição de outro trecho ---


def test_anchor_survives_edit_of_another_paragraph(article, reviewer, author):
    comment = comments.add_comment(
        reviewer, article, "Depende da altitude.", **selection_of(article, occurrence=1)
    )
    before = thread_for(article, comment)
    assert before.anchor_state == "found"
    text = anchors.document_text(article.body_json)
    assert text[before.anchor_start : before.anchor_end] == QUOTE
    assert text[before.anchor_end :].startswith(": depende da pressão")

    # O autor reescreve a introdução e acrescenta um parágrafo antes do trecho comentado.
    edited = doc(
        "Introdução do experimento, agora bem mais longa e com outra frase.",
        "Um parágrafo novo com mais contexto.",
        PARAGRAPHS[1],
        PARAGRAPHS[2],
    )
    services.update_article(author, Article.objects.get(pk=article.pk), body_json=edited)

    after = thread_for(article, comment)
    assert after.anchor_state == "found"
    assert after.anchor_start != before.anchor_start  # as posições mudaram
    assert located_text(article, after) == QUOTE
    new_text = anchors.document_text(edited)
    # Continua na terceira frase (a da serra), não na primeira ocorrência do trecho.
    assert new_text[after.anchor_end :].startswith(": depende da pressão")
    assert new_text[: after.anchor_start].endswith("ninguém diz que ")


def test_anchor_survives_edit_after_the_quote_and_in_the_same_paragraph_elsewhere(
    article, reviewer, author
):
    comment = comments.add_comment(reviewer, article, "Ok.", **selection_of(article, occurrence=0))
    edited = doc(
        PARAGRAPHS[0],
        f"Na cozinha da escola, {QUOTE} ao nível do mar, como medimos.",
        "Parágrafo trocado por completo.",
    )
    services.update_article(author, Article.objects.get(pk=article.pk), body_json=edited)

    thread = thread_for(article, comment)
    assert thread.anchor_state == "found"
    assert located_text(article, thread) == QUOTE
    assert anchors.document_text(edited)[: thread.anchor_start].endswith("Na cozinha da escola, ")


def test_changed_quote_is_shown_as_changed_and_stays_visible(client, article, reviewer, author):
    comment = comments.add_comment(
        reviewer, article, "Depende da altitude.", **selection_of(article, occurrence=1)
    )
    edited = doc(PARAGRAPHS[0], PARAGRAPHS[1], "Na serra, a água ferve antes: depende da pressão.")
    services.update_article(author, Article.objects.get(pk=article.pk), body_json=edited)

    thread = thread_for(article, comment)
    # A outra ocorrência do trecho continua no texto, mas com outro contexto: não é a comentada.
    assert thread.anchor_state == "changed"
    assert thread.anchor_start is None

    client.force_login(author)
    html = client.get(review_url(article)).content.decode()
    item = html.split(f'id="comentario-{comment.pk}"')[1].split("</li>")[0]
    assert "Trecho alterado" in item
    assert "Depende da altitude." in item
    assert "data-anchor-start" not in item  # nada é marcado no texto


def test_page_sends_current_anchor_positions_to_the_browser(client, article, reviewer, author):
    comment = comments.add_comment(reviewer, article, "Veja.", **selection_of(article, 1))
    services.update_article(
        author,
        Article.objects.get(pk=article.pk),
        body_json=doc("Outro começo.", PARAGRAPHS[1], PARAGRAPHS[2]),
    )
    thread = thread_for(article, comment)
    client.force_login(reviewer)

    html = client.get(review_url(article)).content.decode()

    item = html.split(f'id="comentario-{comment.pk}"')[1].split(">")[0]
    assert f'data-anchor-start="{thread.anchor_start}"' in item
    assert f'data-anchor-end="{thread.anchor_end}"' in item
    assert f'data-anchor-text="{QUOTE}"' in item


# --- o texto da âncora do servidor é igual ao que o navegador lê do HTML ---


class BrowserText(HTMLParser):
    """Repete readText (frontend/src/js/review-comments.js) sobre o HTML renderizado."""

    BLOCKS = {"p", "h2", "h3", "li", "blockquote"}
    VOID = {"br", "hr", "img"}

    def __init__(self) -> None:
        super().__init__()
        self.stack: list[tuple[str, int]] = []
        self.counter = 0
        self.text = ""
        self.last_block: int | None = None

    def handle_starttag(self, tag, attrs):
        if tag == "br":
            self.emit("\n")
        if tag in self.VOID:
            return
        self.counter += 1
        self.stack.append((tag, self.counter))

    def handle_endtag(self, tag):
        if tag in self.VOID:
            return
        while self.stack:
            if self.stack.pop()[0] == tag:
                break

    def handle_data(self, data):
        if data:
            self.emit(data)

    def emit(self, piece: str) -> None:
        if any(tag in ("figure", "hr") for tag, _ in self.stack):
            return
        block = next((i for tag, i in reversed(self.stack) if tag in self.BLOCKS), 0)
        if self.last_block is not None and block != self.last_block:
            self.text += "\n"
        self.last_block = block
        self.text += piece


def browser_text(markup: str) -> str:
    parser = BrowserText()
    parser.feed(markup)
    parser.close()
    return parser.text


def test_document_text_matches_what_the_browser_reads():
    document = {
        "type": "doc",
        "content": [
            {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "T"}]},
            {
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": "Negrito ", "marks": [{"type": "bold"}]},
                    {
                        "type": "text",
                        "text": "e link",
                        "marks": [{"type": "link", "attrs": {"href": "https://exemplo.org"}}],
                    },
                    {"type": "hardBreak"},
                    {"type": "text", "text": "nova linha <tag> & “aspas”"},
                ],
            },
            {"type": "paragraph"},
            {"type": "horizontalRule"},
            {
                "type": "bulletList",
                "content": [
                    {"type": "listItem", "content": [paragraph("um")]},
                    {"type": "listItem", "content": [paragraph("dois"), paragraph("três")]},
                ],
            },
            {
                "type": "blockquote",
                "attrs": {"cite": "Fulana"},
                "content": [paragraph("Citação.")],
            },
            {
                "type": "figure",
                "attrs": {"assetId": 999999, "caption": "Legenda", "credit": "Foto"},
            },
            paragraph("Fim."),
        ],
    }
    result = rendering.render(document)

    text = anchors.document_text(result.document)

    assert text == browser_text(result.html)
    assert text == (
        "T\nNegrito e link\nnova linha <tag> & “aspas”\num\ndois\ntrês\nCitação.\nFulana\nFim."
    )


def test_document_text_skips_figure_captions():
    document = {
        "type": "doc",
        "content": [
            paragraph("Antes."),
            {"type": "figure", "attrs": {"assetId": 1, "caption": "Legenda", "credit": "X"}},
            paragraph("Depois."),
        ],
    }

    assert anchors.document_text(document) == "Antes.\nDepois."


# --- locate ---


def test_locate_prefers_context_then_closest_position():
    text = "abc QUOTE def ... xyz QUOTE uvw"

    assert anchors.locate(text, "QUOTE", "xyz ", " uvw") == (22, 27)
    assert anchors.locate(text, "QUOTE", "", "", hint=20) == (22, 27)
    assert anchors.locate(text, "QUOTE") == (4, 9)


def test_locate_rejects_short_quote_with_different_context_but_accepts_long_one():
    assert anchors.locate("outro lugar: palavra aqui", "palavra", "contexto ", " antigo") is None
    long_quote = "um trecho comprido o bastante para valer"
    text = f"mudou tudo em volta, {long_quote}, sim"
    assert anchors.locate(text, long_quote, "antes ", " depois") is not None
    assert anchors.locate(text, "não existe") is None
    assert anchors.locate(text, "") is None


# --- criar, responder, resolver ---


def test_add_general_and_anchored_comments_record_events(article, reviewer):
    general = comments.add_comment(reviewer, article, "  Faltou a fonte.  ")
    anchored = comments.add_comment(reviewer, article, "Cite a pressão.", **selection_of(article))

    assert general.body == "Faltou a fonte."
    assert not general.is_anchored
    assert anchored.anchor_text == QUOTE
    assert anchored.anchor_from == anchors.document_text(article.body_json).index(QUOTE)
    assert anchored.anchor_to == anchored.anchor_from + len(QUOTE)
    assert anchored.anchor_suffix.startswith(" ao nível do mar")
    events = article.events.filter(kind=EditorialEvent.Kind.COMMENT_ADDED)
    assert list(events.values_list("note", flat=True)) == [
        "Faltou a fonte.",
        f"“{QUOTE}”: Cite a pressão.",
    ]
    assert selectors.open_comment_count(article) == 2


@pytest.mark.parametrize(
    ("body", "selection", "message"),
    [
        ("   ", {}, "Escreva o comentário."),
        ("x" * 2001, {}, "até 2000 caracteres"),
        ("Ok", {"anchor_text": "y" * 301}, "até 300 caracteres"),
        ("Ok", {"anchor_text": "trecho que não existe"}, "não está mais no texto"),
    ],
)
def test_add_comment_validation(article, reviewer, body, selection, message):
    with pytest.raises(ValidationError) as exc:
        comments.add_comment(reviewer, article, body, **selection)

    assert message in " ".join(exc.value.messages)
    assert not EditorialComment.objects.exists()


def test_outsiders_cannot_comment_reply_or_resolve(article, reviewer):
    comment = comments.add_comment(reviewer, article, "Veja.")
    outsider = UserFactory()

    with pytest.raises(PermissionDenied):
        comments.add_comment(outsider, article, "Oi")
    with pytest.raises(PermissionDenied):
        comments.reply(outsider, comment, "Oi")
    with pytest.raises(PermissionDenied):
        comments.resolve(outsider, comment)


def test_replies_have_one_level_and_notify_the_thread(article, reviewer, author, editor_user):
    comment = comments.add_comment(reviewer, article, "Confira a tabela.")
    Notification.objects.all().delete()

    reply = comments.reply(author, comment, "Conferi, está certa.")
    with pytest.raises(ValidationError):
        comments.reply(reviewer, reply, "Resposta da resposta")
    comments.reply(editor_user, comment, "Concordo.")

    assert reply.parent == comment
    reviewer_note = Notification.objects.get(user=reviewer, actor=author)
    assert reviewer_note.kind == Notification.Kind.REVIEW_COMMENT
    assert reviewer_note.url == f"{review_url(article)}#comentario-{comment.pk}"
    # A resposta do editor avisa quem já escreveu na conversa.
    assert Notification.objects.filter(actor=editor_user, user__in=[reviewer, author]).count() == 2
    assert not Notification.objects.filter(user=editor_user).exists()


def test_comment_notifications_follow_the_review(article, reviewer, author):
    Notification.objects.all().delete()

    comments.add_comment(reviewer, article, "Durante a leitura.")
    assert not Notification.objects.filter(user=author).exists()  # vão junto ao "Sugerir"

    comments.add_comment(author, article, "Olha o segundo parágrafo também.")
    assert Notification.objects.get(user=reviewer).message == "Carla Souza comentou “Água”."

    services.request_changes(reviewer, article)
    Notification.objects.filter(user=author).delete()
    comments.add_comment(reviewer, Article.objects.get(pk=article.pk), "Mais uma coisa.")
    assert Notification.objects.get(user=author, kind=Notification.Kind.REVIEW_COMMENT)


def test_resolve_and_reopen(article, reviewer, author):
    comment = comments.add_comment(reviewer, article, "Veja.")

    comments.resolve(author, comment)
    comment.refresh_from_db()
    assert comment.status == EditorialComment.Status.RESOLVED
    assert comment.resolved_by == author
    assert comment.resolved_at is not None
    assert selectors.open_comment_count(article) == 0

    comments.reopen(reviewer, comment)
    comment.refresh_from_db()
    assert comment.is_open
    assert comment.resolved_by is None
    kinds = list(article.events.values_list("kind", flat=True))
    assert EditorialEvent.Kind.COMMENT_RESOLVED in kinds
    assert EditorialEvent.Kind.COMMENT_REOPENED in kinds
    history = [entry.text for entry in selectors.history_entries(article)]
    assert "resolveu um comentário" in history
    assert "reabriu um comentário" in history


# --- sugerir alterações exige ao menos um comentário aberto ---


def test_request_changes_needs_an_open_comment(article, reviewer, author):
    comment = comments.add_comment(reviewer, article, "Veja.")
    comments.resolve(reviewer, comment)

    with pytest.raises(ValidationError):
        services.request_changes(reviewer, article, "")
    assert Article.objects.get(pk=article.pk).status == S.IN_REVIEW

    comments.add_comment(reviewer, article, "Falta a fonte.", **selection_of(article))
    comments.add_comment(reviewer, article, "E a conclusão.")
    services.request_changes(reviewer, article)

    assert Article.objects.get(pk=article.pk).status == S.CHANGES_REQUESTED
    notification = Notification.objects.get(user=author, kind=Notification.Kind.CHANGES_REQUESTED)
    assert "2 comentários abertos" in notification.message


def test_request_changes_note_becomes_general_comment(article, reviewer, author):
    services.request_changes(reviewer, article, "Faltou citar a fonte.")

    comment = EditorialComment.objects.get()
    assert comment.body == "Faltou citar a fonte."
    assert comment.author == reviewer
    assert comment.is_open
    assert not comment.is_anchored
    notification = Notification.objects.get(user=author, kind=Notification.Kind.CHANGES_REQUESTED)
    assert "1 comentário aberto" in notification.message
    assert "Faltou citar a fonte." in notification.message


# --- tela e endpoints ---


def test_review_screen_shows_comments_panel_and_mobile_button(client, article, reviewer):
    comments.add_comment(reviewer, article, "Confira.", **selection_of(article))
    comments.resolve(reviewer, comments.add_comment(reviewer, article, "Já foi."))
    client.force_login(reviewer)

    html = client.get(review_url(article)).content.decode()

    assert 'x-data="reviewPage(1)"' in html
    assert 'id="review-comments"' in html
    assert "(1 aberto)" in html
    assert "Resolvidos (1)" in html
    assert "review-fab" in html
    assert "data-review-text" in html
    assert html.index('id="review-comments"') < html.index('id="history-title"')
    assert "<script>" not in html  # CSP: nada inline


def test_create_comment_via_htmx_returns_panel(client, article, reviewer):
    client.force_login(reviewer)
    url = reverse("editorial:comment_create", args=[article.pk])

    response = client.post(url, {"body": "Veja isso.", **selection_of(article)}, **HTMX)

    assert response.status_code == 200
    html = response.content.decode()
    assert 'id="review-comments"' in html
    assert "<html" not in html
    assert "Veja isso." in html
    assert f'data-anchor-text="{QUOTE}"' in html
    assert EditorialComment.objects.get().anchor_text == QUOTE


def test_create_comment_error_keeps_draft(client, article, reviewer):
    client.force_login(reviewer)
    url = reverse("editorial:comment_create", args=[article.pk])

    response = client.post(url, {"body": "Rascunho", "anchor_text": "sumiu"}, **HTMX)

    html = response.content.decode()
    assert 'data-error="1"' in html
    assert "não está mais no texto" in html
    assert ">Rascunho</textarea>" in html
    assert not EditorialComment.objects.exists()


def test_comment_endpoints_without_htmx_redirect_to_review(client, article, reviewer, author):
    client.force_login(author)
    create = reverse("editorial:comment_create", args=[article.pk])

    response = client.post(create, {"body": "Pergunta geral."})
    comment = EditorialComment.objects.get()
    assert response.status_code == 302
    assert response["Location"] == f"{review_url(article)}#comentario-{comment.pk}"

    reply = client.post(reverse("editorial:comment_reply", args=[comment.pk]), {"body": ""})
    assert reply["Location"] == review_url(article)
    assert not comment.replies.exists()

    client.force_login(reviewer)
    resolve = reverse("editorial:comment_status", args=[comment.pk, "resolve"])
    assert client.post(resolve).status_code == 302
    assert EditorialComment.objects.get().status == EditorialComment.Status.RESOLVED
    bad = reverse("editorial:comment_status", args=[comment.pk, "apagar"])
    assert client.post(bad).status_code == 404


def test_comment_endpoints_forbid_outsiders(client, article, reviewer):
    comment = comments.add_comment(reviewer, article, "Veja.")
    client.force_login(UserFactory())

    urls = [
        reverse("editorial:comment_create", args=[article.pk]),
        reverse("editorial:comment_reply", args=[comment.pk]),
        reverse("editorial:comment_status", args=[comment.pk, "resolve"]),
    ]
    for url in urls:
        assert client.post(url, {"body": "Oi"}, **HTMX).status_code == 403
    assert EditorialComment.objects.count() == 1


def test_editor_sidebar_links_open_comments_for_the_author(client, article, reviewer, author):
    comments.add_comment(reviewer, article, "Veja a tabela.")
    services.request_changes(reviewer, article, "E a conclusão.")
    client.force_login(author)

    html = client.get(reverse("publications:edit", args=[article.pk])).content.decode()

    assert f'href="{review_url(article)}#review-comments"' in html
    assert "2 comentários abertos" in html
