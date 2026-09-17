"""Aviso de revisão parada há mais de 5 dias (docs/04, "Notificações"; E44).

O worker roda remind_stale_reviews todo dia; o comando notify_stale_reviews faz o mesmo à mão.
O critério é o do alerta do painel editorial (alerts.stale_reviews).
"""

from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from apps.editorial import alerts
from apps.editorial import services as editorial
from apps.editorial.models import EditorialEvent, Notification
from apps.publications import services
from apps.publications.models import Article
from tests.factories import ArticleFactory, UserFactory

pytestmark = pytest.mark.django_db

STALE = Notification.Kind.REVIEW_STALE


@pytest.fixture
def author():
    return UserFactory(full_name="Carla Souza")


@pytest.fixture
def reviewer():
    return UserFactory(full_name="Marcos Lima")


def in_review(author, reviewer, title="Em leitura"):
    article = ArticleFactory(ready=True, author=author, created_by=author, title=title)
    services.request_review(author, article, reviewer, note="Pode ler?")
    article.refresh_from_db()
    return article


def age(article: Article, days: int) -> None:
    when = timezone.now() - timedelta(days=days)
    Article.objects.filter(pk=article.pk).update(submitted_at=when)
    EditorialEvent.objects.filter(article=article).update(created_at=when)


def stale_notifications():
    return Notification.objects.filter(kind=STALE)


def test_revisao_parada_avisa_revisor_e_autor_uma_vez(author, reviewer):
    article = in_review(author, reviewer, "Horta vertical")
    fresh = in_review(author, reviewer, "Recente")
    age(fresh, alerts.STALE_REVIEW_DAYS - 3)
    age(article, alerts.STALE_REVIEW_DAYS + 2)

    out = StringIO()
    call_command("notify_stale_reviews", stdout=out)

    assert "Avisos de revisão parada: 2." in out.getvalue()
    assert set(stale_notifications().values_list("user_id", flat=True)) == {
        author.pk,
        reviewer.pk,
    }
    notification = stale_notifications().get(user=reviewer)
    assert notification.article == article
    assert notification.message == "A revisão de “Horta vertical” está parada há 7 dias."
    assert notification.url == reverse("editorial:review", args=[article.pk])

    # Rodar de novo (no mesmo dia ou depois de ler o aviso) não repete nem empilha.
    assert editorial.remind_stale_reviews() == 0
    stale_notifications().update(read_at=timezone.now())
    assert editorial.remind_stale_reviews() == 0
    assert editorial.remind_stale_reviews(timezone.now() + timedelta(days=1)) == 0
    assert stale_notifications().count() == 2


def test_revisao_que_andou_e_parou_de_novo_avisa_outra_vez(author, reviewer):
    article = in_review(author, reviewer)
    age(article, 10)
    assert editorial.remind_stale_reviews() == 2
    stale_notifications().update(read_at=timezone.now() - timedelta(days=9))
    past = timezone.now() - timedelta(days=9)
    stale_notifications().update(updated_at=past, created_at=past)

    # Um comentário há 8 dias movimentou a revisão; depois disso, nada.
    EditorialEvent.objects.filter(article=article).update(
        created_at=timezone.now() - timedelta(days=8)
    )

    assert editorial.remind_stale_reviews() == 2
    assert stale_notifications().count() == 4


def test_revisao_com_movimento_ou_encerrada_nao_avisa(author, reviewer):
    moving = in_review(author, reviewer, "Com movimento")
    age(moving, 10)
    EditorialEvent.objects.filter(article=moving).update(created_at=timezone.now())
    cancelled = in_review(author, reviewer, "Cancelada")
    age(cancelled, 10)
    services.cancel_review(author, cancelled)

    assert editorial.remind_stale_reviews() == 0
    assert not stale_notifications().exists()


def test_revisor_inativo_nao_recebe(author, reviewer):
    article = in_review(author, reviewer)
    age(article, 10)
    reviewer.is_active = False
    reviewer.save()

    assert editorial.remind_stale_reviews() == 1
    assert stale_notifications().get().user == author
