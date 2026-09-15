"""Telas do painel ligadas à conta: perfil, assistente de primeiro acesso e conta (docs/14, E23)."""

from typing import Any

from allauth.socialaccount.models import SocialAccount
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods

from apps.core.http import attachment
from apps.publications.media import MediaError
from apps.publications.presentation import initials

from . import privacy, selectors, services
from .forms import (
    PHOTO_ACCEPT,
    AccountPasswordForm,
    IdentityStepForm,
    InterestsStepForm,
    ProfileForm,
    WorkStepForm,
)
from .models import User

ONBOARDING_STEPS = {
    1: ("Quem é você", IdentityStepForm),
    2: ("O que você ensina ou faz", WorkStepForm),
    3: ("O que interessa a você", InterestsStepForm),
}


def _display_name_value(user: User, name: str) -> str:
    """Nome igual ao completo fica vazio: assim segue o nome completo se o admin corrigi-lo."""
    return "" if name == user.full_name else name


def _save_photo(request: HttpRequest, form, user: User) -> bool:
    """Envia a foto escolhida. Erro de imagem vira erro do campo, sem perder o resto."""
    photo = form.cleaned_data.get("photo")
    if not photo:
        return True
    try:
        services.set_avatar(user, photo)
    except MediaError as exc:
        form.add_error("photo", exc.message)
        return False
    return True


def _suggest_topic(request: HttpRequest, name: str) -> Any:
    if not name.strip():
        return None
    topic = services.suggest_topic(name)
    if topic is None:
        messages.info(request, "Tópico sugerido. Ele aparece depois que o administrador aprovar.")
    return topic


# --- assistente de primeiro acesso ---


def _step_context(user: User, step: int, form) -> dict[str, Any]:
    profile = services.ensure_profile(user)
    title, _ = ONBOARDING_STEPS[step]
    context: dict[str, Any] = {
        "step": step,
        "steps": [{"number": n, "title": t} for n, (t, _) in ONBOARDING_STEPS.items()],
        "title": title,
        "form": form,
        "person": user,
        "profile": profile,
        "is_teacher": user.staff_kind == User.StaffKind.TEACHER,
    }
    if step == 1:
        context["photo_accept"] = PHOTO_ACCEPT
        context["initials"] = initials(user.public_name)
        context["avatar_url"] = user.avatar.variant_url("w480") if user.avatar_id else ""
    elif step == 2:
        context["areas"] = selectors.areas_with_disciplines()
        context["selected_disciplines"] = set(profile.disciplines.values_list("pk", flat=True))
        context["selected_areas"] = set(profile.areas.values_list("pk", flat=True))
    else:
        disciplines = profile.disciplines.values_list("pk", flat=True)
        context["topics"] = selectors.topics_for_profile(disciplines)
        context["selected_topics"] = set(profile.topics.values_list("pk", flat=True))
    return context


def _initial(user: User, step: int) -> dict[str, Any]:
    profile = services.ensure_profile(user)
    if step == 1:
        return {"display_name": user.public_name, "headline": profile.headline}
    if step == 3:
        return {"bio": profile.bio}
    return {}


def _next_step(step: int) -> HttpResponse:
    if step < len(ONBOARDING_STEPS):
        return redirect("accounts:onboarding", step=step + 1)
    return redirect("accounts:onboarding_done")


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def onboarding(request: HttpRequest, step: int) -> HttpResponse:
    """/painel/primeiro-acesso/<passo>/: três passos, cada um pode ser pulado (docs/14)."""
    if step not in ONBOARDING_STEPS:
        raise Http404
    user = request.user
    _, form_class = ONBOARDING_STEPS[step]

    if request.method == "POST" and request.POST.get("action") == "skip":
        return _next_step(step)

    form = form_class(request.POST or None, request.FILES or None, initial=_initial(user, step))
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        saved = True
        if step == 1:
            saved = _save_photo(request, form, user)
            if saved:
                services.save_profile(
                    user,
                    user_fields={"display_name": _display_name_value(user, data["display_name"])},
                    profile_fields={"headline": data["headline"]},
                )
        elif step == 2:
            if user.staff_kind == User.StaffKind.TEACHER:
                services.save_profile(user, disciplines=data["disciplines"], areas=[])
            else:
                services.save_profile(user, areas=data["areas"])
        else:
            topics = list(data["topics"])
            if suggested := _suggest_topic(request, data["new_topic"]):
                topics.append(suggested)
            services.save_profile(user, profile_fields={"bio": data["bio"]}, topics=topics)
        if saved:
            return _next_step(step)

    return render(request, "accounts/onboarding.html", _step_context(user, step, form))


@login_required
@require_http_methods(["GET", "POST"])
def onboarding_done(request: HttpRequest) -> HttpResponse:
    """Fim do assistente (ou "pular tudo"): não aparece mais no login."""
    services.complete_onboarding(request.user)
    missing = selectors.missing_profile_items(request.user)
    if missing:
        messages.info(
            request,
            "Tudo certo! Quando quiser, complete seu perfil: falta " + ", ".join(missing) + ".",
        )
    else:
        messages.success(request, "Perfil pronto. Boas-vindas ao jornal!")
    return redirect("core:home")


# --- formulário de perfil ---


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def profile_edit(request: HttpRequest) -> HttpResponse:
    """/painel/perfil/: uma página com seções e um botão salvar (docs/14)."""
    user = request.user
    services.ensure_profile(user)
    form = ProfileForm(user, request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid() and _save_photo(request, form, user):
        data = form.cleaned_data
        old_slug = user.profile.slug
        topics = list(data["topics"])
        if suggested := _suggest_topic(request, data["new_topic"]):
            topics.append(suggested)
        name_changed = data["display_name"] != user.public_name
        services.save_profile(
            user,
            user_fields={"display_name": _display_name_value(user, data["display_name"])},
            profile_fields=form.profile_fields(),
            disciplines=data["disciplines"],
            areas=data["areas"],
            topics=topics,
            update_credits=name_changed and data["update_credits"],
        )
        if data["remove_photo"] and not data.get("photo"):
            services.remove_avatar(user)
        messages.success(request, "Perfil salvo.")
        if user.profile.slug != old_slug:
            messages.warning(
                request, "O endereço do perfil mudou. Links antigos para ele não funcionam mais."
            )
        return redirect("accounts:profile_edit")

    profile = user.profile
    selected = form.data if form.is_bound else form.initial
    context = {
        "form": form,
        "person": user,
        "profile": profile,
        "is_teacher": user.staff_kind == User.StaffKind.TEACHER,
        "avatar_url": user.avatar.variant_url("w480") if user.avatar_id else "",
        "photo_accept": PHOTO_ACCEPT,
        "initials": initials(user.public_name),
        "areas": selectors.areas_with_disciplines(),
        "topics": selectors.topics_for_profile(profile.disciplines.values_list("pk", flat=True)),
        "selected_disciplines": _ids(selected, "disciplines"),
        "selected_areas": _ids(selected, "areas"),
        "selected_topics": _ids(selected, "topics"),
        "missing": selectors.missing_profile_items(user),
        "profile_url": profile.get_absolute_url(),
        "current_year": timezone.localdate().year,
    }
    return render(request, "accounts/profile_edit.html", context)


def _ids(source: Any, key: str) -> set[int]:
    values = source.getlist(key) if hasattr(source, "getlist") else source.get(key, [])
    ids = set()
    for value in values:
        try:
            ids.add(int(getattr(value, "pk", value)))
        except (TypeError, ValueError):
            continue
    return ids


# --- conta ---


@never_cache
@login_required
@sensitive_post_parameters("old_password", "new_password1", "new_password2")
@require_http_methods(["GET", "POST"])
def account_settings(request: HttpRequest) -> HttpResponse:
    """/painel/conta/: forma de entrar, senha, sessões, baixar meus dados e pedir exclusão
    (docs/14, "Conta"; docs/23, "Direitos dos titulares")."""
    user = request.user
    has_password = user.has_usable_password()
    action = request.POST.get("action") if request.method == "POST" else None

    password_form = AccountPasswordForm(user, request.POST if action == "password" else None)
    if action == "password":
        if not has_password:
            raise Http404
        if password_form.is_valid():
            password_form.save()
            # Trocar a senha encerra as outras sessões; esta continua aberta.
            update_session_auth_hash(request, password_form.user)
            messages.success(request, "Senha alterada. As outras sessões foram encerradas.")
            return redirect("accounts:account_settings")
    elif action == "end_sessions":
        ended = services.end_other_sessions(user, request.session.session_key)
        if ended:
            messages.success(request, f"{ended} outra(s) sessão(ões) encerrada(s).")
        else:
            messages.info(request, "Não havia outras sessões abertas.")
        return redirect("accounts:account_settings")
    elif action == "export":
        fmt = "zip" if request.POST.get("formato") == "zip" else "json"
        return attachment(*privacy.export_for(user, user, fmt=fmt, request=request))
    elif action == "request_deletion":
        if request.POST.get("confirmar") != "sim":
            messages.error(request, "Marque a confirmação para enviar o pedido de exclusão.")
            return redirect(reverse("accounts:account_settings") + "#sec-exclusao")
        privacy.request_deletion(user, request=request)
        messages.success(
            request,
            "Pedido de exclusão enviado ao administrador. Sua conta continua funcionando até"
            " ele concluir.",
        )
        return redirect("accounts:account_settings")

    current_key = request.session.session_key
    sessions = [
        {"expire_date": s.expire_date, "is_current": s.session_key == current_key}
        for s in services.user_sessions(user)
    ]
    context = {
        "person": user,
        "uses_microsoft": SocialAccount.objects.filter(user=user, provider="microsoft").exists(),
        "has_password": has_password,
        "password_form": password_form,
        "sessions": sessions,
        "other_sessions": sum(1 for s in sessions if not s["is_current"]),
        "profile_edit_url": reverse("accounts:profile_edit"),
        "deletion_request": privacy.last_deletion_request(user),
    }
    return render(request, "accounts/account_settings.html", context)
