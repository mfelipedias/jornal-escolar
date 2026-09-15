"""Índice e consulta da busca (docs/19; E35)."""

from io import StringIO

import pytest
from django.core.management import call_command
from django.db import connection

from apps.accounts import privacy
from apps.publications import search, selectors, services
from apps.publications.models import Article
from tests.factories import ArticleFactory, DisciplineFactory, UserFactory, text_doc

pytestmark = pytest.mark.django_db


def publish(user, title="Publicação", body="Texto da publicação.", **fields):
    article = ArticleFactory(ready=True, created_by=user, title=title)
    services.update_article(user, article, body_json=text_doc(body), **fields)
    return services.publish(user, article)


def found(query):
    return list(selectors.search_published(query).values_list("title", flat=True))


# --- banco: extensões e configuração criadas pela migração ---


def test_migration_creates_extensions_function_and_config():
    with connection.cursor() as cursor:
        cursor.execute("SELECT extname FROM pg_extension WHERE extname IN ('unaccent', 'pg_trgm')")
        assert {row[0] for row in cursor.fetchall()} == {"unaccent", "pg_trgm"}
        cursor.execute("SELECT f_unaccent('Educação Física')")
        assert cursor.fetchone()[0] == "Educacao Fisica"
        cursor.execute("SELECT to_tsvector('pt_unaccent', 'Física')::text")
        assert cursor.fetchone()[0] == "'fisic':1"


# --- aceite ---


def test_fisica_without_accent_finds_fisica_with_accent(staff_user):
    publish(staff_user, title="Física no pátio da escola")

    assert found("fisica") == ["Física no pátio da escola"]
    assert found("FÍSICA") == ["Física no pátio da escola"]
    assert found("patio") == ["Física no pátio da escola"]


def test_body_text_is_searchable_by_stem(staff_user):
    publish(staff_user, title="Feira", body="Os alunos mostraram experiências com ímãs.")

    assert found("experiencia") == ["Feira"]
    assert found("imas") == ["Feira"]


def test_only_published_articles_are_found(staff_user):
    publish(staff_user, title="Astronomia publicada")
    draft = ArticleFactory(ready=True, created_by=staff_user, title="Astronomia rascunho")
    services.update_article(staff_user, draft, title="Astronomia rascunho")

    assert Article.objects.get(pk=draft.pk).search_vector is not None
    assert found("astronomia") == ["Astronomia publicada"]


def test_empty_query_returns_nothing(staff_user):
    publish(staff_user, title="Qualquer coisa")

    assert found("") == []
    assert found("   ") == []


def test_title_ranks_above_body(staff_user):
    publish(staff_user, title="Horta comunitária", body="Plantamos alface e química do solo.")
    publish(staff_user, title="Química na cozinha", body="Receitas e reações.")

    assert found("quimica") == ["Química na cozinha", "Horta comunitária"]


def test_websearch_syntax_excludes_and_matches_phrase(staff_user):
    publish(staff_user, title="Robótica com sucata", body="Motores reaproveitados.")
    publish(staff_user, title="Robótica educacional", body="Kits prontos de montagem.")

    assert found("robotica -sucata") == ["Robótica educacional"]
    assert found('"robotica educacional"') == ["Robótica educacional"]


# --- search_meta: disciplinas, tópicos e créditos ---


def test_discipline_and_contributor_names_are_searchable(staff_user):
    author = UserFactory(full_name="Joana Prado", display_name="Joana Prado")
    article = publish(author, title="Mural de ciências")
    services.set_metadata(
        author,
        article,
        type_id=article.type_id,
        discipline_ids=[DisciplineFactory(name="Geografia").pk],
        topic_ids=[],
        event_at=None,
        event_location="",
        sources=[],
    )
    services.add_guest_credit(author, article, name="Grêmio Estudantil")

    article.refresh_from_db()
    assert "Geografia" in article.search_meta
    assert found("geografia") == ["Mural de ciências"]
    assert found("prado") == ["Mural de ciências"]
    assert found("gremio") == ["Mural de ciências"]


def test_editing_title_updates_index(staff_user):
    article = publish(staff_user, title="Título antigo")

    services.update_article(staff_user, article, title="Olimpíada de matemática")

    assert found("antigo") == []
    assert found("olimpiada") == ["Olimpíada de matemática"]


def test_discipline_rename_updates_index(staff_user):
    discipline = DisciplineFactory(name="Artes")
    article = publish(staff_user, title="Exposição")
    article.disciplines.set([discipline])
    search.update_search_vector(article)

    discipline.name = "Arte e cultura"
    discipline.save()

    assert found("cultura") == ["Exposição"]


def test_anonymized_student_name_leaves_index(staff_user, admin_user):
    article = publish(staff_user, title="Entrevista")
    credit = services.add_student_credit(
        staff_user, article, name="Bianca T.", class_group="2ª série B", consent_ok=True
    )
    assert found("bianca") == ["Entrevista"]

    services.anonymize_student_credit(admin_user, credit)

    assert found("bianca") == []


def test_anonymized_staff_name_leaves_index(admin_user):
    person = UserFactory(full_name="Heitor Valadares", display_name="Heitor Valadares")
    publish(person, title="Coral da escola")
    assert found("valadares") == ["Coral da escola"]

    privacy.anonymize_user(admin_user, person)

    assert found("valadares") == []
    assert found("coral") == ["Coral da escola"]


# --- reindexação ---


def test_reindex_search_is_idempotent(staff_user):
    publish(staff_user, title="Biologia marinha")
    publish(staff_user, title="História local")
    Article.objects.update(search_vector=None, search_meta="")
    assert found("biologia") == []

    for _ in range(2):
        out = StringIO()
        call_command("reindex_search", stdout=out)
        assert "2 publicação(ões)" in out.getvalue()
        assert found("biologia") == ["Biologia marinha"]
        assert found("historia") == ["História local"]
