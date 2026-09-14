"""Metadados do perfil público: Open Graph com a foto e JSON-LD Person (docs/13, E26).

Só nome, cargo (jobTitle), foto e endereço do perfil. Sem worksFor, que exporia o nome
da escola, e sem e-mail.
"""

from typing import Any

from apps.core import seo

from .models import TeacherProfile, User


def job_title(person: User, profile: TeacherProfile) -> str:
    if profile.headline:
        return profile.headline
    return "" if person.staff_kind == User.StaffKind.OTHER else person.get_staff_kind_display()


def avatar_image(person: User, name: str) -> seo.OgImage | None:
    if not person.avatar_id:
        return None
    avatar = person.avatar
    side = min(480, avatar.width) if avatar.width else None
    return seo.OgImage(
        url=seo.absolute_url(avatar.variant_url("w480")),
        width=side,
        height=side,
        alt=f"Foto de {name}",
    )


def person_json_ld(person: User, profile: TeacherProfile) -> dict[str, Any]:
    name = person.public_name
    data: dict[str, Any] = {
        "@context": seo.SCHEMA_CONTEXT,
        "@type": "Person",
        "name": name,
        "url": seo.absolute_url(profile.get_absolute_url()),
    }
    if title := job_title(person, profile):
        data["jobTitle"] = title
    if image := avatar_image(person, name):
        data["image"] = image.url
    return data


def page_meta(person: User, profile: TeacherProfile) -> seo.PageMeta:
    name = person.public_name
    if not profile.is_public:
        return seo.PageMeta(title=name, description=profile.headline, noindex=True)
    return seo.PageMeta(
        title=name,
        description=job_title(person, profile) or f"Publicações de {name}",
        path=profile.get_absolute_url(),
        image=avatar_image(person, name),
        og_type="profile",
        json_ld=[person_json_ld(person, profile)],
    )
