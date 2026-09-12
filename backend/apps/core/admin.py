from typing import Any

from django import forms
from django.contrib import admin
from django.http import HttpRequest, HttpResponse

from . import site_settings
from .models import SiteSetting, StaticPage


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
    readonly_fields = ("updated_by", "updated_at")
    fields = ("slug", "title", "lead", "body", "is_published", "updated_by", "updated_at")
    view_on_site = True

    def save_model(self, request: HttpRequest, obj: StaticPage, form: Any, change: bool) -> None:
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)
