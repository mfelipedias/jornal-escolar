import io
import zipfile
from typing import Any

from django.contrib import admin, messages
from django.contrib.admin import helpers
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import AdminUserCreationForm, UserChangeForm
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import QuerySet
from django.http import HttpRequest, HttpResponse
from django.template.response import TemplateResponse
from django.utils import timezone
from django.utils.html import format_html, format_html_join

from apps.core import audit
from apps.core.http import attachment

from . import approval, privacy, services
from .models import AccessLink, TeacherProfile, User


class UserCreationForm(AdminUserCreationForm):
    class Meta:
        model = User
        fields = ("email", "full_name", "role", "staff_kind")


class UserEditForm(UserChangeForm):
    class Meta:
        model = User
        fields = "__all__"


class TeacherProfileInline(admin.StackedInline):
    model = TeacherProfile
    can_delete = False
    extra = 0
    fields = (
        "slug",
        "headline",
        "bio",
        "since_year",
        "is_public",
        "disciplines",
        "areas",
        "topics",
        (
            "show_reviewer_credit",
            "reviewers_may_publish",
            "show_reads",
            "accepts_english",
            "include_low_trust",
        ),
    )
    filter_horizontal = ("disciplines", "areas", "topics")


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    form = UserEditForm
    add_form = UserCreationForm
    inlines = [TeacherProfileInline]

    list_display = (
        "full_name",
        "email",
        "role",
        "staff_kind",
        "is_active",
        "is_approved",
        "login_method",
        "last_login",
    )
    list_filter = ("is_approved", "role", "staff_kind", "is_active")
    search_fields = ("full_name", "display_name", "email")
    ordering = ("full_name",)
    readonly_fields = ("is_staff", "last_login", "date_joined", "deactivated_at", "anonymized_at")
    actions = [
        "approve_users",
        "generate_access_links",
        "deactivate_users",
        "reactivate_users",
        "export_user_data",
        "anonymize_users",
    ]

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Identificação", {"fields": ("full_name", "display_name", "staff_kind")}),
        (
            "Acesso",
            {
                "fields": (
                    "role",
                    "is_active",
                    "is_approved",
                    "deactivated_at",
                    "anonymized_at",
                    "is_staff",
                )
            },
        ),
        ("Datas", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "description": (
                    "Deixe sem senha: a pessoa entra com a conta Microsoft da escola ou por um "
                    "link de acesso gerado depois (ação “Gerar link de acesso”)."
                ),
                "fields": (
                    "email",
                    "full_name",
                    "role",
                    "staff_kind",
                    "usable_password",
                    "password1",
                    "password2",
                ),
            },
        ),
    )

    def get_inlines(self, request: HttpRequest, obj: User | None):
        return self.inlines if obj else []

    def save_model(self, request: HttpRequest, obj: User, form: Any, change: bool) -> None:
        """Criação, troca de papel e ativação pelo formulário vão para a auditoria (docs/23)."""
        before = User.objects.filter(pk=obj.pk).values("role", "is_active").first()
        if before and before["is_active"] != obj.is_active:
            obj.deactivated_at = None if obj.is_active else timezone.now()
        super().save_model(request, obj, form, change)
        if not before:
            audit.record(
                audit.Action.USER_CREATED,
                actor=request.user,
                target=obj,
                changes={"role": obj.role},
                request=request,
            )
            return
        if before["role"] != obj.role:
            audit.record(
                audit.Action.ROLE_CHANGED,
                actor=request.user,
                target=obj,
                changes={"role": [before["role"], obj.role]},
                request=request,
            )
        if before["is_active"] != obj.is_active:
            action = (
                audit.Action.USER_REACTIVATED if obj.is_active else audit.Action.USER_DEACTIVATED
            )
            audit.record(action, actor=request.user, target=obj, request=request)

    @admin.display(description="entra com")
    def login_method(self, obj: User) -> str:
        return "Senha" if obj.has_usable_password() else "Microsoft ou link"

    @admin.action(description="Aprovar contas do cadastro próprio")
    def approve_users(self, request: HttpRequest, queryset: QuerySet[User]) -> None:
        count = 0
        for user in queryset.filter(is_approved=False, is_active=True):
            approval.approve(request.user, user, request)
            count += 1
        self.message_user(request, f"{count} conta(s) aprovada(s).", messages.SUCCESS)

    @admin.action(description="Gerar link de acesso (criar ou redefinir senha)")
    def generate_access_links(self, request: HttpRequest, queryset: QuerySet[User]) -> None:
        created: list[tuple[str, str]] = []
        for user in queryset:
            try:
                link = services.create_access_link(user, created_by=request.user)
            except services.AccessLinkError as exc:
                self.message_user(request, f"{user.email}: {exc}", messages.WARNING)
                continue
            audit.record(
                audit.Action.ACCESS_LINK_CREATED,
                actor=request.user,
                target=user,
                changes={"purpose": link.purpose},
                request=request,
            )
            created.append((user.public_name, services.access_link_url(link)))
        if created:
            items = format_html_join("", "<li><strong>{}</strong>: <code>{}</code></li>", created)
            self.message_user(
                request,
                format_html(
                    "Links gerados. Copie e envie para cada pessoa (valem 7 dias, uso único; "
                    "links anteriores foram cancelados):<ul>{}</ul>",
                    items,
                ),
                messages.SUCCESS,
            )

    @admin.action(description="Desativar contas selecionadas")
    def deactivate_users(self, request: HttpRequest, queryset: QuerySet[User]) -> None:
        count = 0
        for user in queryset.filter(is_active=True).exclude(pk=request.user.pk):
            services.deactivate_user(user)
            audit.record(
                audit.Action.USER_DEACTIVATED, actor=request.user, target=user, request=request
            )
            count += 1
        if queryset.filter(pk=request.user.pk).exists():
            self.message_user(request, "Você não pode desativar a própria conta.", messages.WARNING)
        self.message_user(request, f"{count} conta(s) desativada(s).", messages.SUCCESS)

    @admin.action(description="Reativar contas selecionadas")
    def reactivate_users(self, request: HttpRequest, queryset: QuerySet[User]) -> None:
        count = 0
        for user in queryset.filter(is_active=False, anonymized_at__isnull=True):
            services.reactivate_user(user)
            audit.record(
                audit.Action.USER_REACTIVATED, actor=request.user, target=user, request=request
            )
            count += 1
        if queryset.filter(anonymized_at__isnull=False).exists():
            self.message_user(
                request, "Contas anonimizadas não podem ser reativadas.", messages.WARNING
            )
        self.message_user(request, f"{count} conta(s) reativada(s).", messages.SUCCESS)

    @admin.action(description="Exportar dados (JSON)")
    def export_user_data(self, request: HttpRequest, queryset: QuerySet[User]) -> HttpResponse:
        """Uma conta: o JSON dela. Várias: um .zip com um JSON por conta (docs/18)."""
        people = list(queryset.order_by("pk"))
        if len(people) == 1:
            return attachment(*privacy.export_for(request.user, people[0], request=request))
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for person in people:
                content, filename, _ = privacy.export_for(request.user, person, request=request)
                archive.writestr(filename, content)
        name = f"dados-de-{len(people)}-contas-{timezone.localdate():%Y-%m-%d}.zip"
        return attachment(buffer.getvalue(), name, "application/zip")

    @admin.action(description="Anonimizar (apaga dados pessoais, não dá para desfazer)")
    def anonymize_users(
        self, request: HttpRequest, queryset: QuerySet[User]
    ) -> TemplateResponse | None:
        """Pede confirmação numa página intermediária antes de anonimizar."""
        people = list(queryset.order_by("full_name"))
        if request.POST.get("confirmar") != "sim":
            context = {
                **self.admin_site.each_context(request),
                "title": "Anonimizar contas",
                "opts": self.model._meta,
                "people": people,
                "action_checkbox_name": helpers.ACTION_CHECKBOX_NAME,
                "credit_name": privacy.ANONYMIZED_CREDIT,
                "anonymized_name": privacy.ANONYMIZED_NAME,
            }
            return TemplateResponse(
                request, "admin/accounts/user/anonymize_confirmation.html", context
            )
        done = 0
        for person in people:
            try:
                privacy.anonymize_user(request.user, person, request=request)
                done += 1
            except PermissionDenied:
                self.message_user(request, f"{person.email}: sem permissão.", messages.WARNING)
            except ValidationError as exc:
                self.message_user(
                    request, f"{person.email}: {' '.join(exc.messages)}", messages.WARNING
                )
        if done:
            self.message_user(request, f"{done} conta(s) anonimizada(s).", messages.SUCCESS)
        return None


@admin.register(AccessLink)
class AccessLinkAdmin(admin.ModelAdmin):
    list_display = ("user", "purpose", "status_label", "created_at", "expires_at", "created_by")
    list_filter = ("purpose",)
    search_fields = ("user__email", "user__full_name")
    list_select_related = ("user", "created_by")
    readonly_fields = (
        "user",
        "purpose",
        "status_label",
        "created_by",
        "created_at",
        "expires_at",
        "used_at",
        "revoked_at",
    )
    fields = readonly_fields

    @admin.display(description="situação")
    def status_label(self, obj: AccessLink) -> str:
        return AccessLink.Status(obj.status).label

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False  # Links são gerados pela ação em Usuários ou pelo comando access_link.

    def has_change_permission(self, request: HttpRequest, obj: AccessLink | None = None) -> bool:
        return False
