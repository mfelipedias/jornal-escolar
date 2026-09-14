"""Seed de demonstração (E28): equipe fictícia, publicações, agenda e destaques.

SÓ PARA DESENVOLVIMENTO E APRESENTAÇÕES. Recusa rodar sem DEBUG=True, o que exclui a
produção (config/settings/prod.py fixa DEBUG=False).

- Idempotente: pessoas são procuradas pelo e-mail e publicações pelo título e autor; rodar
  de novo só cria o que falta.
- Tudo passa pelos mesmos serviços das telas (criar, salvar, checklist, publicar, destaques).
- Capas e fotos de perfil são desenhadas aqui com o Pillow; nada é baixado da internet.
- As contas fictícias usam o domínio DEMO_EMAIL_DOMAIN e não têm senha (não entram no site).
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
