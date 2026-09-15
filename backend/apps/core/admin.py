from typing import Any

from django import forms
from django.contrib import admin
from django.http import HttpRequest, HttpResponse
from django.urls import reverse
from django.utils.html import format_html

from . import audit, site_settings
from .models import AuditLog, SiteSetting, StaticPage


def build_value_field(spec: site_settings.SettingSpec) -> forms.Field:
    """Campo de formulário adequado ao tipo da configuração (sem JSON para o usuário)."""
    common = {"label": spec.label, "help_text": spec.help_text}
    if spec.kind == "bool":
        return forms.BooleanField(required=False, **common)
    if spec.kind == "int":
        return forms.IntegerField(min_value=spec.min_value, **common)
    if spec.kind == "choice":
        return forms.ChoiceField(choices=spec.choices, **common)
    if spec.kind == "email":
        return forms.EmailField(required=False, **common)
    return forms.CharField(max_length=240, required=spec.key == "site.name", **common)


class SiteSettingForm(forms.ModelForm):
    class Meta:
        model = SiteSetting
        fields = ("value",)

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        spec = site_settings.REGISTRY.get(self.instance.key)
        if spec is not None:
            self.fields["value"] = build_value_field(spec)
            if self.instance.value is None:
                self.initial["value"] = spec.default


@admin.register(SiteSetting)
class SiteSettingAdmin(admin.ModelAdmin):
    form = SiteSettingForm
    list_display = ("label", "current_value", "key", "updated_at")
    readonly_fields = ("key", "help")
    fields = ("key", "help", "value")
    search_fields = ("key", "description")

    @admin.display(description="configuração")
    def label(self, obj: SiteSetting) -> str:
        return str(obj)

    @admin.display(description="valor")
    def current_value(self, obj: SiteSetting) -> str:
        spec = site_settings.REGISTRY.get(obj.key)
        if spec and spec.kind == "bool":
            return "Sim" if obj.value else "Não"
        if spec and spec.kind == "choice":
            return dict(spec.choices).get(obj.value, obj.value)
        return "" if obj.value is None else str(obj.value)

    @admin.display(description="sobre")
    def help(self, obj: SiteSetting) -> str:
        spec = site_settings.REGISTRY.get(obj.key)
        return spec.help_text if spec else ""

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False  # As chaves são fixas no código (site_settings.REGISTRY).

    def save_model(self, request: HttpRequest, obj: SiteSetting, form: Any, change: bool) -> None:
        before = SiteSetting.objects.filter(pk=obj.pk).values_list("value", flat=True).first()
        super().save_model(request, obj, form, change)
        if before != obj.value:
            audit.record(
                audit.Action.SETTING_CHANGED,
                actor=request.user,
                target=obj,
                changes={"key": obj.key, "value": [before, obj.value]},
                request=request,
            )

    def has_delete_permission(self, request: HttpRequest, obj: SiteSetting | None = None) -> bool:
        return False

    def changelist_view(
        self, request: HttpRequest, extra_context: dict[str, Any] | None = None
    ) -> HttpResponse:
        site_settings.ensure_defaults()
        return super().changelist_view(request, extra_context)


@admin.register(StaticPage)
class StaticPageAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "is_published", "updated_at", "updated_by")
    list_filter = ("is_published",)
    readonly_fields = ("text", "updated_by", "updated_at")
    fields = ("slug", "title", "lead", "text", "is_published", "updated_by", "updated_at")
    view_on_site = True

    @admin.display(description="texto")
    def text(self, obj: StaticPage) -> str:
        """O corpo é escrito no editor do painel, não aqui (docs/18)."""
        if not obj.pk:
            return "Salve a página e depois escreva o texto no painel."
        return format_html(
            '<a href="{}">Editar o texto no painel</a>',
            reverse("core:page_edit", args=[obj.slug]),
        )

    def save_model(self, request: HttpRequest, obj: StaticPage, form: Any, change: bool) -> None:
        was_published = (
            StaticPage.objects.filter(pk=obj.pk).values_list("is_published", flat=True).first()
        )
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)
        if was_published is not None and was_published != obj.is_published:
            action = (
                audit.Action.PAGE_PUBLISHED if obj.is_published else audit.Action.PAGE_UNPUBLISHED
            )
            audit.record(
                action,
                actor=request.user,
                target=obj,
                changes={"slug": obj.slug},
                request=request,
            )


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """Auditoria só para leitura, com filtros por ação e por quem fez (docs/18)."""

    list_display = ("created_at", "action", "actor", "target", "short_changes", "short_ip")
    list_filter = ("action", ("actor", admin.RelatedOnlyFieldListFilter), "created_at")
    search_fields = ("target_id", "actor__email", "actor__full_name")
    list_select_related = ("actor",)
    date_hierarchy = "created_at"
    fields = ("created_at", "action", "actor", "target", "changes", "ip_hash")
    readonly_fields = fields

    @admin.display(description="alvo")
    def target(self, obj: AuditLog) -> str:
        if not obj.target_type:
            return "—"
        return f"{obj.target_type} #{obj.target_id}"

    @admin.display(description="detalhes")
    def short_changes(self, obj: AuditLog) -> str:
        text = ", ".join(f"{key}: {value}" for key, value in obj.changes.items())
        return text if len(text) <= 80 else text[:77] + "…"

    @admin.display(description="IP (hash)")
    def short_ip(self, obj: AuditLog) -> str:
        return obj.ip_hash[:10]

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: AuditLog | None = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: AuditLog | None = None) -> bool:
        return False
