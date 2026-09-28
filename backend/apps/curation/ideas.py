"""Pautas (E49; docs/15 "Sugestões e Pautas", docs/21 "Da sugestão à publicação").

Caminho de uma pauta no quadro:

    Aberta ──pegar──▶ Atribuída ──criar rascunho──▶ Em produção ──publicar──▶ Concluída
       ▲                 │
       └────devolver─────┘

- "Virar pauta" numa sugestão cria a pauta já atribuída a quem clicou, com a notícia de origem,
  os tópicos e as disciplinas visíveis da notícia; a sugestão fica como "virou pauta".
- Pauta escrita à mão nasce aberta (ou com quem a criou, se a pessoa marcar).
- Criar rascunho: publicação em rascunho com o título da pauta, a notícia nas fontes (título,
  link, veículo), as disciplinas e os tópicos da pauta e `origin_news_item`. A checklist
  passa a exigir uma fonte citada. Ao publicar, a pauta vai para "Concluída".
- Ajustar os tópicos ou as disciplinas de uma pauta com notícia corrige a classificação dela:
  grava linhas `manual` (score 1,0), que a reclassificação automática não apaga (docs/21).
"""

from collections.abc import Iterable

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.editorial import permissions
from apps.publications.models import Article
from apps.taxonomy.models import Discipline, Topic

from .classify import VISIBLE_SCORE
from .models import NewsItem, NewsItemClassification, NewsRecommendation, StoryIdea

Status = StoryIdea.Status
Method = NewsItemClassification.Method
TITLE_PREFIX = "Pauta: "


def _clean_title(title: str) -> str:
    title = " ".join((title or "").split())
    if not title:
        raise ValidationError({"title": "Dê um título à pauta."})
    return title[:200]


def _visible(item: NewsItem, field: str) -> list[int]:
    rows = item.classifications.filter(**{f"{field}__isnull": False, "score__gte": VISIBLE_SCORE})
    return list(rows.values_list(f"{field}_id", flat=True).distinct())


def _notify_assigned(idea: StoryIdea, actor: User) -> None:
    from apps.editorial.models import Notification
    from apps.editorial.notifications import notify

    if idea.assigned_to_id and idea.assigned_to_id != actor.pk:
        notify(
            idea.assigned_to,
            Notification.Kind.STORY_IDEA,
            f"{actor.public_name} passou a pauta “{idea.title}” para você",
            actor=actor,
            url=reverse("curation:story_ideas"),
        )


def _sync_manual_classification(idea: StoryIdea) -> None:
    """Os tópicos e disciplinas da pauta viram a classificação manual da notícia."""
    if idea.item_id is None:
        return
    manual = NewsItemClassification.objects.filter(item_id=idea.item_id, method=Method.MANUAL)
    topic_ids = set(idea.topics.values_list("pk", flat=True))
    discipline_ids = set(idea.disciplines.values_list("pk", flat=True))
    manual.filter(topic__isnull=False).exclude(topic_id__in=topic_ids).delete()
    manual.filter(discipline__isnull=False).exclude(discipline_id__in=discipline_ids).delete()
    rows = [
        NewsItemClassification(item_id=idea.item_id, topic_id=pk, score=1.0, method=Method.MANUAL)
        for pk in topic_ids
    ] + [
        NewsItemClassification(
            item_id=idea.item_id, discipline_id=pk, score=1.0, method=Method.MANUAL
        )
        for pk in discipline_ids
    ]
    NewsItemClassification.objects.bulk_create(rows, ignore_conflicts=True)


@transaction.atomic
def create_idea(
    user: User,
    *,
    title: str,
    notes: str = "",
    topics: Iterable[Topic] = (),
    disciplines: Iterable[Discipline] = (),
    keep: bool = False,
) -> StoryIdea:
    """Pauta escrita à mão. keep=True: fica com quem criou."""
    if not permissions.can_create_story_idea(user):
        raise PermissionDenied
    idea = StoryIdea.objects.create(
        title=_clean_title(title),
        notes=(notes or "").strip()[:2000],
        proposed_by=user,
        status=Status.ASSIGNED if keep else Status.OPEN,
        assigned_to=user if keep else None,
    )
    idea.topics.set(topics)
    idea.disciplines.set(disciplines)
    return idea


@transaction.atomic
def idea_from_recommendation(user: User, rec: NewsRecommendation) -> StoryIdea:
    """ "Virar pauta" (docs/21): nasce atribuída a quem clicou."""
    if not permissions.can_create_story_idea(user) or rec.user_id != user.pk:
        raise PermissionDenied
    rec = NewsRecommendation.objects.select_for_update().select_related("item").get(pk=rec.pk)
    if rec.status == NewsRecommendation.Status.CONVERTED and rec.story_idea_id:
        return rec.story_idea
    item = rec.item
    idea = StoryIdea.objects.create(
        title=f"{TITLE_PREFIX}{item.title}"[:200],
        proposed_by=user,
        item=item,
        status=Status.ASSIGNED,
        assigned_to=user,
    )
    idea.topics.set(_visible(item, "topic"))
    idea.disciplines.set(_visible(item, "discipline"))
    rec.status = NewsRecommendation.Status.CONVERTED
    rec.story_idea = idea
    rec.acted_at = timezone.now()
    rec.save(update_fields=["status", "story_idea", "acted_at", "updated_at"])
    return idea


_UNCHANGED = object()


@transaction.atomic
def update_idea(
    user: User,
    idea: StoryIdea,
    *,
    title: str,
    notes: str = "",
    topics: Iterable[Topic] = (),
    disciplines: Iterable[Discipline] = (),
    assigned_to: User | object | None = _UNCHANGED,
) -> StoryIdea:
    if not permissions.can_edit_story_idea(user, idea):
        raise PermissionDenied
    idea.title = _clean_title(title)
    idea.notes = (notes or "").strip()[:2000]
    fields = ["title", "notes", "updated_at"]
    reassigned = False
    if assigned_to is not _UNCHANGED and assigned_to != idea.assigned_to:
        if not permissions.can_assign_story_idea(user, idea):
            raise PermissionDenied
        idea.assigned_to = assigned_to
        idea.status = Status.ASSIGNED if assigned_to else Status.OPEN
        fields += ["assigned_to", "status"]
        reassigned = assigned_to is not None
    idea.save(update_fields=fields)
    idea.topics.set(topics)
    idea.disciplines.set(disciplines)
    _sync_manual_classification(idea)
    if reassigned:
        _notify_assigned(idea, user)
    return idea


def _locked(idea: StoryIdea) -> StoryIdea:
    return StoryIdea.objects.select_for_update().get(pk=idea.pk)


@transaction.atomic
def take(user: User, idea: StoryIdea) -> StoryIdea:
    idea = _locked(idea)
    if not permissions.can_take_story_idea(user, idea):
        raise PermissionDenied
    idea.status = Status.ASSIGNED
    idea.assigned_to = user
    idea.save(update_fields=["status", "assigned_to", "updated_at"])
    return idea


@transaction.atomic
def release(user: User, idea: StoryIdea) -> StoryIdea:
    idea = _locked(idea)
    if not permissions.can_release_story_idea(user, idea):
        raise PermissionDenied
    idea.status = Status.OPEN
    idea.assigned_to = None
    idea.save(update_fields=["status", "assigned_to", "updated_at"])
    return idea


@transaction.atomic
def delete(user: User, idea: StoryIdea) -> None:
    idea = _locked(idea)
    if not permissions.can_delete_story_idea(user, idea):
        raise PermissionDenied
    # A sugestão que virou esta pauta volta a ficar salva, para a notícia não se perder.
    idea.recommendations.update(status=NewsRecommendation.Status.SAVED, story_idea=None)
    idea.delete()


@transaction.atomic
def start_draft(user: User, idea: StoryIdea) -> Article:
    """ "Criar rascunho" (docs/21, passo 2)."""
    from apps.publications import services as publications

    idea = _locked(idea)
    if not permissions.can_start_draft(user, idea):
        raise PermissionDenied
    item = idea.item
    sources = []
    if item is not None:
        sources = [{"title": item.title, "url": item.canonical_url, "publisher": item.source.name}]
    title = idea.title.removeprefix(TITLE_PREFIX).strip() or idea.title
    article = publications.create_article(
        user, title=title[: publications.TITLE_MAX], sources=publications.clean_sources(sources)
    )
    article.origin_news_item = item
    article.save(update_fields=["origin_news_item"])
    article.topics.set(idea.topics.all())
    article.disciplines.set(idea.disciplines.all())
    idea.article = article
    idea.assigned_to = user
    idea.status = Status.IN_PROGRESS
    idea.save(update_fields=["article", "assigned_to", "status", "updated_at"])
    return article


def article_published(article: Article) -> int:
    """Chamado ao publicar: a pauta do texto vai para "Concluída" (docs/21, passo 4)."""
    return (
        StoryIdea.objects.filter(article=article)
        .exclude(status=Status.DONE)
        .update(status=Status.DONE, done_at=timezone.now(), updated_at=timezone.now())
    )
