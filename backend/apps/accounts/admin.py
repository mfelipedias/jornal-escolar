from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import AdminUserCreationForm, UserChangeForm
from django.db.models import QuerySet
from django.http import HttpRequest
from django.utils.html import format_html, format_html_join

from . import services
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
        ("show_reviewer_credit", "reviewers_may_publish", "show_reads", "accepts_english"),
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
        "login_method",
        "last_login",
    )
    list_filter = ("role", "staff_kind", "is_active")
    search_fields = ("full_name", "display_name", "email")
    ordering = ("full_name",)
    readonly_fields = ("is_staff", "last_login", "date_joined", "deactivated_at")
    actions = ["generate_access_links", "deactivate_users", "reactivate_users"]

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Identificação", {"fields": ("full_name", "display_name", "staff_kind")}),
        ("Acesso", {"fields": ("role", "is_active", "deactivated_at", "is_staff")}),
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

    @admin.display(description="entra com")
    def login_method(self, obj: User) -> str:
        return "Senha" if obj.has_usable_password() else "Microsoft ou link"

    @admin.action(description="Gerar link de acesso (criar ou redefinir senha)")
    def generate_access_links(self, request: HttpRequest, queryset: QuerySet[User]) -> None:
        created: list[tuple[str, str]] = []
        for user in queryset:
            try:
                link = services.create_access_link(user, created_by=request.user)
            except services.AccessLinkError as exc:
                self.message_user(request, f"{user.email}: {exc}", messages.WARNING)
                continue
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
            count += 1
        if queryset.filter(pk=request.user.pk).exists():
            self.message_user(request, "Você não pode desativar a própria conta.", messages.WARNING)
        self.message_user(request, f"{count} conta(s) desativada(s).", messages.SUCCESS)

    @admin.action(description="Reativar contas selecionadas")
    def reactivate_users(self, request: HttpRequest, queryset: QuerySet[User]) -> None:
        count = 0
        for user in queryset.filter(is_active=False):
            services.reactivate_user(user)
            count += 1
        self.message_user(request, f"{count} conta(s) reativada(s).", messages.SUCCESS)


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
