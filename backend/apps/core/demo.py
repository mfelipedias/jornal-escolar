"""Seed de demonstração (E28): equipe fictícia, publicações, agenda e destaques.

SÓ PARA DESENVOLVIMENTO E APRESENTAÇÕES. Recusa rodar sem DEBUG=True, o que exclui a
produção (config/settings/prod.py fixa DEBUG=False).

- Idempotente: pessoas são procuradas pelo e-mail e publicações pelo título e autor; rodar
  de novo só cria o que falta.
- Tudo passa pelos mesmos serviços das telas (criar, salvar, checklist, publicar, destaques).
- Capas e fotos de perfil são desenhadas aqui com o Pillow; nada é baixado da internet.
- As contas fictícias usam o domínio DEMO_EMAIL_DOMAIN e não têm senha (não entram no site).
- Curadoria: duas fontes e oito notícias inventadas (domínios exemplo.org/example.org), já
  classificadas e sugeridas às pessoas fictícias, e pautas de exemplo no quadro. As fontes
  nunca são coletadas de verdade (intervalo de um ano e endereços que não existem).
- remove_demo() apaga tudo o que o seed criou, inclusive os arquivos das imagens.
"""

import io
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from PIL import Image, ImageDraw, ImageFont

from apps.accounts import services as account_services
from apps.accounts.models import User
from apps.publications import media
from apps.publications import services as publications
from apps.publications.cache import invalidate_public_content
from apps.publications.models import Article, MediaAsset
from apps.taxonomy.models import ArticleType, Discipline, Topic
from apps.taxonomy.services import seed_taxonomy

from . import demo_data
from .services import seed_site, text_to_document

# Cores das áreas (mesmos valores dos tokens de frontend/src/css/app.css), para as capas.
AREA_RGB = {
    "coral": ("#b23a1f", "#fde6df"),
    "verde": ("#2f7a3e", "#e2f3e4"),
    "azul": ("#1d5fb8", "#e1ebfa"),
    "ambar": ("#8f5a00", "#fbefd3"),
    "violeta": ("#6a3fb5", "#ece4fa"),
    "petroleo": ("#1c6f6b", "#ddf2f0"),
    "magenta": ("#a8174f", "#fbe4ec"),
    "grafite": ("#4a4f5a", "#e9eaee"),
}
COVER_SIZE = (1200, 750)
AVATAR_SIDE = 400


class DemoNotAllowed(Exception):
    pass


@dataclass
class DemoResult:
    people: int = 0
    articles: int = 0
    images: int = 0
    news: int = 0
    ideas: int = 0
    featured: list[int] = field(default_factory=list)


def ensure_allowed() -> None:
    if not settings.DEBUG:
        raise DemoNotAllowed(
            "O seed de demonstração só roda em desenvolvimento (DEBUG=True). "
            "Nunca rode em produção: ele cria pessoas e publicações fictícias."
        )


def demo_users():
    return User.objects.filter(email__endswith=f"@{demo_data.DEMO_EMAIL_DOMAIN}")


def email_for(key: str) -> str:
    return f"{key}@{demo_data.DEMO_EMAIL_DOMAIN}"


# --- imagens geradas ---


def _hex(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def _mix(a: tuple[int, ...], b: tuple[int, ...], t: float) -> tuple[int, ...]:
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b, strict=True))


def cover_image(color: str, variant: int) -> bytes:
    """Capa abstrata nas cores da área: gradiente com círculos, barras ou faixas."""
    solid, soft = (_hex(c) for c in AREA_RGB.get(color, AREA_RGB["grafite"]))
    width, height = COVER_SIZE
    image = Image.new("RGB", COVER_SIZE, soft)
    draw = ImageDraw.Draw(image)
    for y in range(height):
        draw.line([(0, y), (width, y)], fill=_mix(soft, _mix(soft, solid, 0.45), y / height))
    light = _mix(soft, (255, 255, 255), 0.5)
    dark = _mix(solid, (0, 0, 0), 0.15)
    pattern = variant % 3
    if pattern == 0:
        for i in range(7):
            radius = 60 + i * 38
            cx, cy = width - 260 - i * 20, 220 + i * 30
            box = [cx - radius, cy - radius, cx + radius, cy + radius]
            draw.ellipse(box, outline=light if i % 2 else dark, width=10)
    elif pattern == 1:
        bar = 90
        for i in range(9):
            bar_height = 120 + ((i * 97) % 380)
            x = 120 + i * (bar + 24)
            fill = dark if i % 3 == 0 else light
            draw.rectangle([x, height - 80 - bar_height, x + bar, height - 80], fill=fill)
    else:
        for i in range(-4, 14):
            x = i * 110
            fill = dark if i % 2 else light
            draw.polygon([(x, height), (x + 60, height), (x + 460, 0), (x + 400, 0)], fill=fill)
    draw.ellipse([80, 80, 200, 200], fill=_mix(solid, (255, 255, 255), 0.1))
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=88)
    return buffer.getvalue()


def avatar_image(name: str, color: str) -> bytes:
    solid, soft = (_hex(c) for c in AREA_RGB.get(color, AREA_RGB["grafite"]))
    image = Image.new("RGB", (AVATAR_SIDE, AVATAR_SIDE), solid)
    draw = ImageDraw.Draw(image)
    draw.ellipse([-80, 220, 480, 780], fill=_mix(solid, soft, 0.3))
    letters = "".join(part[0] for part in name.split()[:2]).upper()
    try:
        font = ImageFont.load_default(size=150)
    except (TypeError, OSError):  # Pillow sem FreeType: fica só o fundo
        font = None
    if font is not None:
        draw.text((AVATAR_SIDE / 2, AVATAR_SIDE / 2), letters, fill=soft, font=font, anchor="mm")
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()


def _upload(data: bytes, name: str, user: User, article: Article | None = None, **kw):
    uploaded = SimpleUploadedFile(name, data)
    return media.process_upload(uploaded, user, article, **kw)


# --- pessoas ---


def _area_color(discipline_names: list[str]) -> str:
    first = Discipline.objects.filter(name__in=discipline_names).select_related("area").first()
    return first.area.color if first else "grafite"


def _ensure_people(result: DemoResult) -> dict[str, User]:
    people: dict[str, User] = {}
    for data in demo_data.STAFF:
        user = User.objects.filter(email=email_for(data["key"])).first()
        if user is None:
            user = User.objects.create_user(
                email=email_for(data["key"]),
                password=None,
                full_name=data["full_name"],
                display_name=data["display_name"],
                role=data["role"],
                staff_kind=data["staff_kind"],
                date_joined=timezone.now() - timedelta(days=120),
            )
            disciplines = list(Discipline.objects.filter(name__in=data["disciplines"]))
            account_services.save_profile(
                user,
                profile_fields={
                    "headline": data["headline"],
                    "bio": data["bio"],
                    "since_year": data["since_year"],
                    "education": data["education"],
                },
                disciplines=disciplines,
                areas=[],
                topics=list(Topic.objects.filter(name__in=data["topics"])),
            )
            account_services.complete_onboarding(user)
            if data["avatar"]:
                png = avatar_image(user.public_name, _area_color(data["disciplines"]))
                account_services.set_avatar(user, SimpleUploadedFile("avatar.png", png))
                result.images += 1
            result.people += 1
        people[data["key"]] = user
    return people


# --- publicações ---


def _event_datetime(event: tuple[int, int, str]) -> datetime:
    days, hour, _ = event
    day = timezone.localtime() + timedelta(days=days)
    return day.replace(hour=hour, minute=0, second=0, microsecond=0)


def _create_article(data: dict, people: dict[str, User], variant: int, result: DemoResult):
    author = people[data["author"]]
    if Article.objects.filter(created_by=author, title=data["title"]).exists():
        return None
    article = publications.create_article(author, title=data["title"], subtitle=data["subtitle"])
    if data["body"]:
        publications.update_article(author, article, body_json=text_to_document(data["body"]))
    article_type = ArticleType.objects.filter(name=data["type"]).first() if data["type"] else None
    event = data.get("event")
    publications.set_metadata(
        author,
        article,
        type_id=article_type.pk if article_type else None,
        discipline_ids=list(
            Discipline.objects.filter(name__in=data["disciplines"]).values_list("pk", flat=True)
        ),
        topic_ids=list(Topic.objects.filter(name__in=data["topics"]).values_list("pk", flat=True)),
        event_at=_event_datetime(event) if event else None,
        event_location=event[2] if event else "",
        sources=data.get("sources", []),
    )
    for key in data.get("coauthors", []):
        publications.add_staff_credit(author, article, people[key])
    for name, class_group in data.get("students", []):
        publications.add_student_credit(
            author, article, name=name, class_group=class_group, consent_ok=True
        )
    for name, note in data.get("guests", []):
        publications.add_guest_credit(author, article, name=name, contribution_note=note)
    if data.get("cover"):
        color = _area_color(data["disciplines"])
        asset = _upload(cover_image(color, variant), "capa.jpg", author, article)
        asset.alt_text = data["cover_alt"]
        asset.credit = "Ilustração gerada para demonstração"
        asset.save(update_fields=["alt_text", "credit"])
        publications.set_cover(author, article, asset, data.get("caption", ""))
        result.images += 1

    status = data.get("status", "published")
    if status in ("published", "archived"):
        published_at = timezone.now() - timedelta(days=data["days_ago"], hours=variant % 7)
        Article.objects.filter(pk=article.pk).update(published_at=published_at)
        publications.publish(author, article)
        Article.objects.filter(pk=article.pk).update(
            created_at=published_at - timedelta(days=2),
            updated_at=published_at,
            reads_count=data.get("reads", 0),
        )
        if status == "archived":
            publications.archive(author, article)
    elif status in ("in_review", "changes_requested"):
        reviewer = people[data["reviewer"]]
        publications.request_review(
            author,
            article,
            reviewer,
            note=data.get("review_note", ""),
            can_publish=data.get("reviewer_may_publish", False),
        )
        if status == "changes_requested":
            publications.request_changes(reviewer, article, data["changes_note"])
    result.articles += 1
    return article


def _ensure_featured(people: dict[str, User], result: DemoResult) -> None:
    """Marca os destaques da demonstração, só se ninguém escolheu destaques de verdade."""
    current = publications.featured_ids()
    demo_ids = set(Article.objects.filter(created_by__in=demo_users()).values_list("pk", flat=True))
    if current and not set(current) <= demo_ids:
        return
    ordered = sorted(
        (d for d in demo_data.ARTICLES if d.get("featured")), key=lambda d: d["featured"]
    )
    ids = []
    for data in ordered:
        article = Article.objects.filter(
            created_by=people[data["author"]], title=data["title"], status="published"
        ).first()
        if article and article.cover_id:
            ids.append(article.pk)
    if ids and ids != current:
        editor = next(u for u in people.values() if u.role == User.Role.EDITOR)
        result.featured = publications.set_featured(editor, ids)


# --- curadoria de notícias e pautas ---

DEMO_FETCH_INTERVAL = 60 * 24 * 365  # um ano: o worker nunca tenta coletar estes endereços


def _ensure_curation(people: dict[str, User], result: DemoResult) -> None:
    from apps.curation import classify, ideas, normalize, recommend
    from apps.curation.models import NewsItem, NewsRecommendation, NewsSource, StoryIdea

    now = timezone.now()
    sources: dict[str, NewsSource] = {}
    for data in demo_data.NEWS_SOURCES:
        source, created = NewsSource.objects.get_or_create(
            feed_url=data["feed_url"],
            defaults={
                "name": data["name"],
                "site_url": data["site_url"],
                "language": data["language"],
                "trust_level": data["trust_level"],
                "fetch_interval_minutes": DEMO_FETCH_INTERVAL,
                "last_fetched_at": now,
                "last_success_at": now,
            },
        )
        if created:
            source.default_topics.set(Topic.objects.filter(name__in=data["default_topics"]))
        sources[data["key"]] = source

    new_items = []
    for key, days, title, summary in demo_data.NEWS_ITEMS:
        slug = normalize.title_key(title).replace(" ", "-")[:80]
        url = f"{sources[key].site_url}{slug}/"
        item, created = NewsItem.objects.get_or_create(
            url_hash=normalize.url_hash(url),
            defaults={
                "source": sources[key],
                "title": title,
                "url": url,
                "canonical_url": url,
                "title_hash": normalize.title_hash(title),
                "summary": summary,
                "published_at": now - timedelta(days=days, hours=2),
                "fetched_at": now,
                "language": sources[key].language,
            },
        )
        if created:
            new_items.append(item)
    if new_items:
        classify.classify_items(new_items)
        recommend.recommend_items([item.pk for item in new_items], now=now)
        result.news = len(new_items)

    demo_people = list(people.values())
    if StoryIdea.objects.filter(proposed_by__in=demo_people).exists():
        return
    # Da sugestão à pauta: a Carla transforma a primeira sugestão dela em pauta.
    first = (
        NewsRecommendation.objects.filter(user=people["carla"], status="suggested")
        .order_by("-score")
        .first()
    )
    if first is not None:
        ideas.idea_from_recommendation(people["carla"], first)
        result.ideas += 1
    for key, title, notes, topic_names, status in demo_data.STORY_IDEAS:
        idea = ideas.create_idea(
            people[key],
            title=title,
            notes=notes,
            topics=Topic.objects.filter(name__in=topic_names),
            keep=status != "open",
        )
        if status == "in_progress":
            ideas.start_draft(people[key], idea)  # rascunho da demonstração, apagado junto
        result.ideas += 1
    # Uma pauta concluída: ligada a uma publicação da demonstração que já está no ar.
    published = Article.objects.filter(
        created_by__in=demo_people, status=Article.Status.PUBLISHED
    ).first()
    if published is not None:
        done = ideas.create_idea(published.created_by, title=f"Pauta: {published.title}")
        StoryIdea.objects.filter(pk=done.pk).update(
            status=StoryIdea.Status.DONE,
            assigned_to=published.created_by,
            article=published,
            done_at=now,
        )
        result.ideas += 1


def _remove_curation(users) -> dict[str, int]:
    from apps.curation.models import NewsSource, StoryIdea

    ideas = StoryIdea.objects.filter(Q(proposed_by__in=users) | Q(assigned_to__in=users))
    sources = NewsSource.objects.filter(
        feed_url__in=[data["feed_url"] for data in demo_data.NEWS_SOURCES]
    )
    counts = {"pautas": ideas.count(), "fontes de notícias": sources.count()}
    ideas.delete()
    sources.delete()  # as notícias, classificações e sugestões vão junto
    return counts


@transaction.atomic
def seed_demo() -> DemoResult:
    ensure_allowed()
    seed_taxonomy()
    seed_site()
    result = DemoResult()
    people = _ensure_people(result)
    for variant, data in enumerate(demo_data.ARTICLES):
        _create_article(data, people, variant, result)
    _ensure_featured(people, result)
    _ensure_curation(people, result)
    invalidate_public_content()
    return result


@transaction.atomic
def remove_demo() -> dict[str, int]:
    """Apaga pessoas fictícias, as publicações delas e todas as imagens que enviaram."""
    ensure_allowed()
    users = demo_users()
    articles = Article.objects.filter(created_by__in=users)
    assets = MediaAsset.objects.filter(Q(uploaded_by__in=users) | Q(article__in=articles))
    counts = {
        **_remove_curation(users),
        "imagens": assets.count(),
        "publicações": articles.count(),
        "pessoas": users.count(),
    }
    User.objects.filter(pk__in=users).update(avatar=None)
    for asset in assets:
        asset.delete()  # o sinal apaga original e variantes depois do commit
    articles.delete()
    users.delete()
    invalidate_public_content()
    return counts
