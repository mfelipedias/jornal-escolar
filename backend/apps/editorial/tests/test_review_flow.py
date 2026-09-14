"""Revisão por colega e EditorialEvent (E29, docs/04). Aceite: todas as transições testadas."""

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse

from apps.accounts import services as account_services
from apps.editorial import permissions
from apps.editorial.models import EditorialEvent, Notification
from apps.publications import services
from apps.publications.models import Article, ArticleContributor, ArticleRevision
from tests.factories import ArticleFactory, UserFactory, text_doc

pytestmark = pytest.mark.django_db

S = Article.Status
K = EditorialEvent.Kind
HTMX = {"HTTP_HX_REQUEST": "true"}


@pytest.fixture
def author():
    return UserFactory(full_name="Carla Souza")


@pytest.fixture
def reviewer():
    return UserFactory(full_name="Marcos Lima")


@pytest.fixture
def article(author):
    return ArticleFactory(ready=True, author=author, created_by=author, title="Feira")


def status_events(article):
    return list(
        article.events.filter(kind=K.STATUS_CHANGE)
        .order_by("pk")
        .values_list("from_status", "to_status")
    )


def kinds(article):
    return list(article.events.order_by("pk").values_list("kind", flat=True))


def inbox(user):
    return list(Notification.objects.filter(user=user).values_list("kind", flat=True))


def in_review(article, author, reviewer, **kwargs):
    return services.request_review(author, article, reviewer, **kwargs)


# --- tabela de transições (docs/04, "Diagrama de transições") ---


def _published(article, author, reviewer, editor):
    services.publish(author, article)


def _in_review(article, author, reviewer, editor):
    in_review(article, author, reviewer, can_publish=True)


def _changes(article, author, reviewer, editor):
    in_review(article, author, reviewer)
    services.request_changes(reviewer, article, "Revise a introdução.")


def _archived(article, author, reviewer, editor):
    services.archive(author, article)


SETUP = {
    S.DRAFT: lambda *a: None,
    S.IN_REVIEW: _in_review,
    S.CHANGES_REQUESTED: _changes,
    S.PUBLISHED: _published,
    S.ARCHIVED: _archived,
}

ACTIONS = {
    "publish": lambda a, u, r: services.publish(u, a),
    "request_review": lambda a, u, r: services.request_review(u, a, r),
    "archive": lambda a, u, r: services.archive(u, a),
    "restore": lambda a, u, r: services.restore(u, a),
    "request_changes": lambda a, u, r: services.request_changes(u, a, "Ajuste"),
    "approve": lambda a, u, r: services.approve(u, a),
    "approve_publish": lambda a, u, r: services.approve_and_publish(u, a),
    "decline_review": lambda a, u, r: services.decline_review(u, a),
    "cancel_review": lambda a, u, r: services.cancel_review(u, a),
    "resume": lambda a, u, r: services.resume(u, a),
}

# (estado inicial, quem age, ação, estado final)
TRANSITIONS = [
    (S.DRAFT, "author", "publish", S.PUBLISHED),
    (S.DRAFT, "author", "request_review", S.IN_REVIEW),
    (S.DRAFT, "author", "archive", S.ARCHIVED),
    (S.IN_REVIEW, "reviewer", "request_changes", S.CHANGES_REQUESTED),
    (S.IN_REVIEW, "reviewer", "approve", S.DRAFT),
    (S.IN_REVIEW, "reviewer", "approve_publish", S.PUBLISHED),
    (S.IN_REVIEW, "reviewer", "decline_review", S.DRAFT),
    (S.IN_REVIEW, "editor", "approve_publish", S.PUBLISHED),
    (S.IN_REVIEW, "editor", "publish", S.PUBLISHED),
    (S.IN_REVIEW, "author", "cancel_review", S.DRAFT),
    (S.CHANGES_REQUESTED, "author", "resume", S.DRAFT),
    (S.CHANGES_REQUESTED, "author", "request_review", S.IN_REVIEW),
    (S.CHANGES_REQUESTED, "author", "publish", S.PUBLISHED),
    (S.PUBLISHED, "author", "archive", S.ARCHIVED),
    (S.ARCHIVED, "author", "restore", S.DRAFT),
]


@pytest.mark.parametrize(("start", "who", "action", "end"), TRANSITIONS)
def test_every_transition_changes_status_and_records_event(
    article, author, reviewer, editor_user, start, who, action, end
):
    SETUP[start](article, author, reviewer, editor_user)
    article.refresh_from_db()
    assert article.status == start
    actor = {"author": author, "reviewer": reviewer, "editor": editor_user}[who]

    ACTIONS[action](article, actor, reviewer)

    article.refresh_from_db()
    assert article.status == end
    last = article.events.filter(kind=K.STATUS_CHANGE).latest("pk")
    assert (last.from_status, last.to_status, last.actor) == (start, end, actor)


# Transições que o diagrama não prevê (ou que a pessoa não pode fazer) são recusadas.
FORBIDDEN = [
    (S.DRAFT, "reviewer", "approve"),
    (S.DRAFT, "author", "cancel_review"),
    (S.DRAFT, "author", "resume"),
    (S.IN_REVIEW, "author", "publish"),
    (S.IN_REVIEW, "author", "request_review"),
    (S.IN_REVIEW, "author", "approve"),
    (S.IN_REVIEW, "reviewer", "publish"),
    (S.IN_REVIEW, "reviewer", "cancel_review"),
    (S.IN_REVIEW, "reviewer", "archive"),
    (S.CHANGES_REQUESTED, "reviewer", "approve"),
    (S.CHANGES_REQUESTED, "reviewer", "resume"),
    (S.CHANGES_REQUESTED, "reviewer", "request_review"),
    (S.PUBLISHED, "author", "request_review"),
    (S.PUBLISHED, "author", "resume"),
    (S.ARCHIVED, "author", "request_review"),
]


@pytest.mark.parametrize(("start", "who", "action"), FORBIDDEN)
def test_transitions_outside_the_diagram_are_denied(
    article, author, reviewer, editor_user, start, who, action
):
    SETUP[start](article, author, reviewer, editor_user)
    article.refresh_from_db()
    before = article.events.count()
    actor = {"author": author, "reviewer": reviewer}[who]

    with pytest.raises(PermissionDenied):
        ACTIONS[action](article, actor, reviewer)

    article.refresh_from_db()
    assert article.status == start
    assert article.events.count() == before


# --- pedir revisão ---


def test_request_review_assigns_reviewer_and_notifies(article, author, reviewer):
    services.request_review(author, article, reviewer, note="Olha a introdução", can_publish=True)

    article.refresh_from_db()
    assert article.status == S.IN_REVIEW
    assert article.submitted_at is not None
    credit = article.contributors.get(role=ArticleContributor.Role.REVIEWER)
    assert (credit.user, credit.can_publish) == (reviewer, True)
    assert article.revisions.filter(reason=ArticleRevision.Reason.SUBMITTED).exists()
    assert status_events(article) == [(S.DRAFT, S.IN_REVIEW)]
    change = article.events.get(kind=K.STATUS_CHANGE)
    assert change.note == "Olha a introdução"
    assigned = article.events.get(kind=K.REVIEWER_ASSIGNED)
    assert assigned.note == "Marcos Lima (pode publicar)."
    notification = Notification.objects.get(user=reviewer)
    assert notification.kind == Notification.Kind.REVIEW_REQUESTED
    assert "pediu que você revise “Feira”" in notification.message
    assert "Olha a introdução" in notification.message
    assert inbox(author) == []


def test_nobody_reviews_own_text(article, author):
    coauthor = UserFactory()
    services.add_staff_credit(author, article, coauthor, ArticleContributor.Role.COAUTHOR)

    with pytest.raises(ValidationError):
        services.request_review(author, article, author)
    with pytest.raises(ValidationError):
        services.request_review(author, article, coauthor)
    with pytest.raises(ValidationError):
        services.request_review(author, article, UserFactory(is_active=False))
    article.refresh_from_db()
    assert article.status == S.DRAFT


def test_only_authors_and_editors_request_review(article, reviewer, editor_user):
    with pytest.raises(PermissionDenied):
        services.request_review(UserFactory(), article, reviewer)

    services.request_review(editor_user, article, reviewer)
    assert Article.objects.get(pk=article.pk).status == S.IN_REVIEW


def test_resend_to_another_colleague_replaces_reviewer(article, author, reviewer):
    in_review(article, author, reviewer)
    services.request_changes(reviewer, article, "Faltam fontes.")
    other = UserFactory(full_name="Rita Alves")

    services.request_review(author, article, other, can_publish=False)

    reviewers = article.contributors.filter(role=ArticleContributor.Role.REVIEWER)
    assert [c.user for c in reviewers] == [other]
    assert status_events(article) == [
        (S.DRAFT, S.IN_REVIEW),
        (S.IN_REVIEW, S.CHANGES_REQUESTED),
        (S.CHANGES_REQUESTED, S.IN_REVIEW),
    ]
    assert article.events.filter(kind=K.CONTRIBUTOR_CHANGED, note__contains="Marcos").exists()


def test_resend_to_same_reviewer_updates_permission(article, author, reviewer):
    in_review(article, author, reviewer, can_publish=False)
    services.request_changes(reviewer, article, "Ajuste o título.")

    services.request_review(author, article, reviewer, can_publish=True)

    credit = article.contributors.get(role=ArticleContributor.Role.REVIEWER)
    assert credit.can_publish is True
    assert article.events.filter(kind=K.REVIEWER_ASSIGNED).count() == 2


# --- decisões do revisor ---


def test_request_changes_needs_note_and_notifies_authors(article, author, reviewer):
    in_review(article, author, reviewer)

    with pytest.raises(ValidationError):
        services.request_changes(reviewer, article, "   ")
    assert Article.objects.get(pk=article.pk).status == S.IN_REVIEW

    services.request_changes(reviewer, article, "Confira os dados do gráfico.")

    article.refresh_from_db()
    assert article.status == S.CHANGES_REQUESTED
    notification = Notification.objects.get(user=author, kind=Notification.Kind.CHANGES_REQUESTED)
    assert "Confira os dados do gráfico." in notification.message
    assert article.events.filter(kind=K.STATUS_CHANGE).latest("pk").note == (
        "Confira os dados do gráfico."
    )


def test_approve_returns_to_draft_with_seal(article, author, reviewer):
    in_review(article, author, reviewer)

    services.approve(reviewer, article, note="Ficou ótimo.")

    article.refresh_from_db()
    assert article.status == S.DRAFT
    assert kinds(article)[-2:] == [K.STATUS_CHANGE, K.APPROVED]
    assert article.events.get(kind=K.APPROVED).actor == reviewer
    assert inbox(author) == [Notification.Kind.APPROVED]
    # O crédito de revisão fica: aparece quando o autor publicar.
    assert article.contributors.filter(user=reviewer, role="reviewer").exists()
    # O revisor já não edita; o autor publica quando quiser.
    assert not permissions.can_edit(reviewer, article)
    services.publish(author, article)


def test_approve_and_publish_requires_author_permission(article, author, reviewer):
    in_review(article, author, reviewer, can_publish=False)
    with pytest.raises(PermissionDenied):
        services.approve_and_publish(reviewer, article)

    services.cancel_review(author, article)
    in_review(article, author, reviewer, can_publish=True)
    services.approve_and_publish(reviewer, article)

    article.refresh_from_db()
    assert article.status == S.PUBLISHED
    assert article.slug
    assert article.events.filter(kind=K.APPROVED, actor=reviewer).exists()
    assert Notification.Kind.PUBLISHED_BY_OTHER in inbox(author)


def test_approve_and_publish_respects_checklist(author, reviewer):
    article = ArticleFactory(author=author, created_by=author)  # sem tipo, corpo, disciplina
    in_review(article, author, reviewer, can_publish=True)
    before = article.events.count()

    with pytest.raises(services.ChecklistError):
        services.approve_and_publish(reviewer, article)

    article.refresh_from_db()
    assert article.status == S.IN_REVIEW
    assert article.events.count() == before


def test_editor_reviews_any_text_but_not_their_own(article, author, reviewer, editor_user):
    in_review(article, author, reviewer)
    assert permissions.can_review(editor_user, article)
    assert permissions.can_approve_and_publish(editor_user, article)
    assert not permissions.can_decline_review(editor_user, article)

    own = ArticleFactory(ready=True, author=editor_user, created_by=editor_user)
    services.request_review(editor_user, own, reviewer)
    assert not permissions.can_review(editor_user, own)


def test_other_staff_cannot_decide(article, author, reviewer):
    in_review(article, author, reviewer)
    intruder = UserFactory()

    for action in (services.approve, services.decline_review):
        with pytest.raises(PermissionDenied):
            action(intruder, article)
    with pytest.raises(PermissionDenied):
        services.request_changes(intruder, article, "Não sou o revisor.")


def test_decline_review_removes_reviewer_and_notifies(article, author, reviewer):
    in_review(article, author, reviewer)

    services.decline_review(reviewer, article, note="Estou em semana de provas.")

    article.refresh_from_db()
    assert article.status == S.DRAFT
    assert not article.contributors.filter(role="reviewer").exists()
    removed = article.events.get(kind=K.REVIEWER_REMOVED)
    assert removed.note == "Marcos Lima: revisão recusada."
    notification = Notification.objects.get(user=author)
    assert "Estou em semana de provas." in notification.message
    assert not permissions.can_view(reviewer, article)


def test_cancel_review_notifies_reviewer(article, author, reviewer):
    in_review(article, author, reviewer)

    services.cancel_review(author, article)

    article.refresh_from_db()
    assert article.status == S.DRAFT
    assert not article.contributors.filter(role="reviewer").exists()
    assert article.events.filter(kind=K.REVIEWER_REMOVED).exists()
    assert sorted(inbox(reviewer)) == [Notification.Kind.REVIEW_REQUESTED, Notification.Kind.SYSTEM]


# --- permissões durante a revisão ---


def test_reviewer_sees_and_edits_only_while_in_review(article, author, reviewer):
    assert not permissions.can_view(reviewer, article)
    in_review(article, author, reviewer)

    assert permissions.can_view(reviewer, article)
    assert permissions.can_edit(reviewer, article)
    assert not permissions.can_edit_credits(reviewer, article)
    assert not permissions.can_publish(reviewer, article)
    assert not permissions.can_archive(reviewer, article)

    services.request_changes(reviewer, article, "Ajuste.")
    assert permissions.can_view(reviewer, article)
    assert not permissions.can_edit(reviewer, article)


def test_reviewer_edit_is_third_party_event_and_notifies_author(article, author, reviewer):
    in_review(article, author, reviewer)

    services.update_article(reviewer, article, body_json=text_doc("Corrigido"))
    services.update_article(reviewer, article, body_json=text_doc("Corrigido de novo"))

    assert article.events.filter(kind=K.EDITED_BY_THIRD_PARTY, actor=reviewer).count() == 1
    assert Notification.Kind.EDITED_BY_OTHER in inbox(author)
    with pytest.raises(PermissionDenied):
        services.add_student_credit(reviewer, article, name="Rafael S.", consent_ok=True)


def test_author_editing_during_review_warns_reviewer(article, author, reviewer):
    in_review(article, author, reviewer)

    services.update_article(author, article, subtitle="Nova linha fina")

    notification = Notification.objects.get(user=reviewer, kind=Notification.Kind.EDITED_BY_OTHER)
    assert "durante a revisão" in notification.message
    assert not article.events.filter(kind=K.EDITED_BY_THIRD_PARTY).exists()


def test_reviewer_credit_is_managed_only_by_review_flow(article, author, reviewer):
    with pytest.raises(ValidationError):
        services.add_staff_credit(author, article, reviewer, ArticleContributor.Role.REVIEWER)

    in_review(article, author, reviewer)
    credit = article.contributors.get(role="reviewer")
    with pytest.raises(ValidationError):
        services.remove_credit(author, article, credit)


# --- outros eventos ---


def test_publish_archive_restore_record_events_with_note(article, author, editor_user):
    services.publish(author, article)
    services.archive(editor_user, article, note="Dados desatualizados")
    services.restore(author, article)

    assert status_events(article) == [
        (S.DRAFT, S.PUBLISHED),
        (S.PUBLISHED, S.ARCHIVED),
        (S.ARCHIVED, S.DRAFT),
    ]
    archived = article.events.get(to_status=S.ARCHIVED)
    assert (archived.actor, archived.note) == (editor_user, "Dados desatualizados")


def test_editing_published_records_one_event_per_window(article, author, editor_user):
    services.publish(author, article)

    services.update_article(author, article, subtitle="Primeira correção")
    services.update_article(author, article, subtitle="Segunda correção")
    services.update_article(editor_user, article, subtitle="Correção do editor")

    assert article.events.filter(kind=K.EDITED_AFTER_PUBLISH, actor=author).count() == 1
    assert article.events.filter(kind=K.EDITED_AFTER_PUBLISH, actor=editor_user).count() == 1
    assert article.events.filter(kind=K.EDITED_BY_THIRD_PARTY, actor=editor_user).count() == 1
    assert not article.events.filter(kind=K.EDITED_BY_THIRD_PARTY, actor=author).exists()


def test_credit_changes_record_events_without_student_names(article, author):
    colleague = UserFactory(full_name="João Pereira")
    services.add_staff_credit(author, article, colleague)
    student = services.add_student_credit(
        author, article, name="Rafael S.", class_group="2ª B", consent_ok=True
    )
    services.remove_credit(author, article, student)

    notes = list(
        article.events.filter(kind=K.CONTRIBUTOR_CHANGED)
        .order_by("pk")
        .values_list("note", flat=True)
    )
    assert notes == [
        "João Pereira (Coautor) adicionado.",
        "Crédito de aluno (Autor) adicionado.",
        "Crédito de aluno (Autor) removido.",
    ]
    assert not any("Rafael" in note for note in notes)


def test_update_past_credits_records_event_per_article(author):
    first = ArticleFactory(author=author, created_by=author)
    second = ArticleFactory(author=author, created_by=author)
    author.display_name = "Profa. Carla"
    author.save()

    assert account_services.update_past_credits(author) == 2

    for article in (first, second):
        event = article.events.get(kind=K.CONTRIBUTOR_CHANGED)
        assert event.actor == author
        assert "Profa. Carla" in event.note


# --- telas ---


def edit_url(article):
    return reverse("publications:edit", args=[article.pk])


def transition_url(article, action):
    return reverse("publications:transition", args=[article.pk, action])


def test_author_requests_review_from_editor(client, article, author, reviewer):
    profile = account_services.ensure_profile(author)
    profile.reviewers_may_publish = True
    profile.save()
    client.force_login(author)

    page = client.get(edit_url(article)).content.decode()
    assert "Pedir revisão" in page
    assert f'value="{reviewer.pk}"' in page
    assert f'value="{author.pk}"' not in page  # ninguém revisa o próprio texto

    response = client.post(
        transition_url(article, "request_review"),
        {"reviewer": reviewer.pk, "note": "Veja os dados", "can_publish": "on"},
        **HTMX,
    )

    assert response["HX-Redirect"] == edit_url(article)
    article.refresh_from_db()
    assert article.status == S.IN_REVIEW
    assert article.contributors.get(role="reviewer").can_publish is True
    page = client.get(edit_url(article)).content.decode()
    assert "Em revisão com Marcos Lima" in page
    assert "Cancelar pedido" in page
    assert "Veja os dados" in page


def test_request_review_without_reviewer_shows_error(client, article, author):
    client.force_login(author)

    response = client.post(transition_url(article, "request_review"), {"reviewer": ""})

    assert response.status_code == 302
    assert Article.objects.get(pk=article.pk).status == S.DRAFT
    messages = [str(m) for m in response.wsgi_request._messages]
    assert messages == ["Escolha o colega que vai revisar."]


def test_reviewer_decision_without_next_goes_back_to_panel(client, article, author, reviewer):
    in_review(article, author, reviewer, can_publish=True)
    client.force_login(reviewer)

    page = client.get(edit_url(article)).content.decode()
    assert reverse("editorial:review", args=[article.pk]) in page  # decisão na tela de revisão
    assert "Pedir revisão" not in page

    response = client.post(transition_url(article, "approve"), {"note": ""}, **HTMX)

    assert response["HX-Redirect"] == reverse("dashboard:home")
    assert Article.objects.get(pk=article.pk).status == S.DRAFT
    client.force_login(author)
    assert "Revisado por Marcos Lima" in client.get(edit_url(article)).content.decode()


def test_request_changes_without_note_is_blocked_in_view(client, article, author, reviewer):
    in_review(article, author, reviewer)
    client.force_login(reviewer)

    response = client.post(transition_url(article, "request_changes"), {"note": ""}, **HTMX)

    assert response["HX-Redirect"] == edit_url(article)
    assert Article.objects.get(pk=article.pk).status == S.IN_REVIEW


def test_changes_requested_editor_shows_note_and_resend(client, article, author, reviewer):
    in_review(article, author, reviewer)
    services.request_changes(reviewer, article, "Faltou citar a fonte.")
    client.force_login(author)

    page = client.get(edit_url(article)).content.decode()

    assert "Alterações sugeridas" in page
    assert "Faltou citar a fonte." in page
    assert "Reenviar para revisão" in page
    assert "Voltar a rascunho" in page
    assert f'value="{reviewer.pk}"\n' in page or f'value="{reviewer.pk}"' in page


def test_unknown_transition_is_404(client, article, author):
    client.force_login(author)

    assert client.post(transition_url(article, "aprovar-tudo")).status_code == 404


def test_other_staff_cannot_review_via_view(client, article, author, reviewer):
    in_review(article, author, reviewer)
    client.force_login(UserFactory())

    assert client.post(transition_url(article, "approve")).status_code == 403
    assert client.get(edit_url(article)).status_code == 403


def test_my_articles_shows_review_states(client, article, author, reviewer):
    other = ArticleFactory(ready=True, author=author, created_by=author, title="Horta")
    in_review(article, author, reviewer)
    in_review(other, author, reviewer)
    services.request_changes(reviewer, other, "Ajuste.")
    client.force_login(author)

    response = client.get(reverse("dashboard:my_articles"), {"estado": "em-revisao"})
    assert [row.article for row in response.context["rows"]] == [article]
    response = client.get(reverse("dashboard:my_articles"), {"estado": "alteracoes-sugeridas"})
    assert [row.article for row in response.context["rows"]] == [other]
    html = response.content.decode()
    assert "Em revisão" in html
    assert "Alterações sugeridas" in html


def test_article_in_review_is_not_public(client, article, author, reviewer):
    services.publish(author, article)
    services.archive(author, article)
    services.restore(author, article)
    in_review(article, author, reviewer)
    url = reverse("publications:detail", args=[article.slug])

    assert client.get(url).status_code == 404
    client.force_login(reviewer)
    assert client.get(url).status_code == 200  # pré-visualização para o revisor
