"""Seed de demonstração (E28): idempotente, realista, recusado fora de desenvolvimento."""

import pytest
from django.core.files.storage import default_storage
from django.core.management import CommandError, call_command

from apps.accounts.models import User
from apps.core import demo, demo_data
from apps.publications import selectors
from apps.publications.credits import student_name_error
from apps.publications.models import Article, ArticleContributor, MediaAsset
from tests.factories import ArticleFactory, UserFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def dev(settings, tmp_path):
    settings.DEBUG = True
    settings.MEDIA_ROOT = tmp_path
    return settings


def test_recusa_sem_debug(settings):
    settings.DEBUG = False

    with pytest.raises(CommandError, match="só roda em desenvolvimento"):
        call_command("seed_demo")
    with pytest.raises(CommandError):
        call_command("seed_demo", "--apagar")
    assert not demo.demo_users().exists()


def test_cria_site_de_demonstracao_e_e_idempotente(dev, client):
    call_command("seed_demo")

    people = demo.demo_users()
    assert people.count() == len(demo_data.STAFF)
    assert not any(user.has_usable_password() for user in people)
    assert people.filter(role=User.Role.EDITOR).exists()
    assert people.exclude(avatar=None).exists()

    articles = Article.objects.filter(created_by__in=people)
    assert articles.count() == len(demo_data.ARTICLES)
    published = articles.filter(status=Article.Status.PUBLISHED)
    assert published.count() >= 15
    assert articles.filter(status=Article.Status.DRAFT).exists()
    assert articles.filter(status=Article.Status.ARCHIVED).exists()
    # Revisão por colega (E29): uma com o revisor e uma devolvida com alterações sugeridas.
    in_review = articles.get(status=Article.Status.IN_REVIEW)
    assert in_review.contributors.filter(role="reviewer", user__in=people).exists()
    assert in_review.events.filter(kind="reviewer_assigned").exists()
    assert articles.filter(status=Article.Status.CHANGES_REQUESTED).exists()
    assert published.values("type").distinct().count() >= 8
    assert published.values("disciplines__area").distinct().count() >= 5
    assert published.exclude(cover=None).count() >= 6

    # Alunos seguem a política de nome e têm autorização marcada (docs/23).
    students = ArticleContributor.objects.filter(article__in=articles, is_student=True)
    assert students.exists()
    assert all(student_name_error(s.display_name) is None for s in students)
    assert not students.filter(consent_ok=False).exists()

    # Agenda com eventos futuros e destaques com capa na home.
    upcoming, past = selectors.upcoming_events()
    assert len(upcoming) >= 3
    assert not past
    featured = Article.objects.filter(is_featured=True)
    assert featured.count() == 3
    assert not featured.filter(cover=None).exists()
    home = client.get("/")
    assert home.status_code == 200
    assert "Feira de Ciências reúne 40 projetos sobre energia" in home.content.decode()

    # Imagens são arquivos de verdade no armazenamento (geradas localmente).
    asset = MediaAsset.objects.filter(uploaded_by__in=people).first()
    assert default_storage.exists(asset.file.name)

    # Rodar de novo não duplica nada.
    counts = (people.count(), articles.count(), MediaAsset.objects.count())
    result = demo.seed_demo()
    assert (result.people, result.articles, result.images) == (0, 0, 0)
    assert (people.count(), articles.count(), MediaAsset.objects.count()) == counts


def test_nao_troca_destaques_escolhidos_de_verdade(dev):
    real = ArticleFactory(ready=True, status=Article.Status.PUBLISHED, is_featured=True)

    demo.seed_demo()

    assert list(Article.objects.filter(is_featured=True)) == [real]


def test_apagar_remove_so_o_que_o_seed_criou(dev, django_capture_on_commit_callbacks):
    real_user = UserFactory()
    real_article = ArticleFactory(created_by=real_user)
    with django_capture_on_commit_callbacks(execute=True):
        demo.seed_demo()
    paths = [p for a in MediaAsset.objects.all() for p in a.all_paths()]
    assert paths

    with django_capture_on_commit_callbacks(execute=True):
        call_command("seed_demo", "--apagar")

    assert not demo.demo_users().exists()
    assert not MediaAsset.objects.exists()
    assert list(Article.objects.all()) == [real_article]
    assert User.objects.filter(pk=real_user.pk).exists()
    assert not any(default_storage.exists(path) for path in paths)
