from django import forms
from django.contrib import admin, messages
from django.db.models import Count, QuerySet
from django.http import HttpRequest

from apps.curation import services as curation

from .models import ArticleType, Discipline, KnowledgeArea, Topic


class DisciplineInline(admin.TabularInline):
    model = Discipline
    fields = ("name", "slug", "order", "is_active")
    extra = 0
    show_change_link = True


@admin.register(KnowledgeArea)
class KnowledgeAreaAdmin(admin.ModelAdmin):
    list_display = ("name", "short_name", "color", "order", "is_active", "discipline_count")
    list_editable = ("short_name", "color", "order", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}
    fields = ("name", "short_name", "slug", "color", "description", "order", "is_active")
    inlines = [DisciplineInline]

    def get_queryset(self, request: HttpRequest) -> QuerySet[KnowledgeArea]:
        return super().get_queryset(request).annotate(_discipline_count=Count("disciplines"))

    @admin.display(description="disciplinas", ordering="_discipline_count")
    def discipline_count(self, obj: KnowledgeArea) -> int:
        return obj._discipline_count


@admin.register(Discipline)
class DisciplineAdmin(admin.ModelAdmin):
    list_display = ("name", "area", "order", "is_active")
    list_editable = ("order", "is_active")
    list_filter = ("area", "is_active")
    search_fields = ("name",)
    list_select_related = ("area",)
    prepopulated_fields = {"slug": ("name",)}
    fields = ("area", "name", "slug", "description", "order", "is_active")


class TopicForm(forms.ModelForm):
    """Palavras-chave digitadas separadas por vírgula, em vez de JSON."""

    keywords = forms.CharField(
        label="palavras-chave",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Separe por vírgulas. Ex.: robótica, Arduino, sensores",
    )

    class Meta:
        model = Topic
        fields = ("name", "slug", "is_active", "disciplines", "keywords")

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        if self.instance.pk and isinstance(self.instance.keywords, list):
            self.initial["keywords"] = ", ".join(self.instance.keywords)

    def clean_keywords(self) -> list[str]:
        raw = self.cleaned_data.get("keywords") or ""
        seen: dict[str, str] = {}
        for term in raw.split(","):
            term = " ".join(term.split())
            if term and term.lower() not in seen:
                seen[term.lower()] = term
        return list(seen.values())


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    form = TopicForm
    list_display = ("name", "is_active", "keyword_list")
    list_filter = ("is_active", "disciplines__area")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}
    filter_horizontal = ("disciplines",)
    actions = ["approve_topics"]

    @admin.display(description="palavras-chave")
    def keyword_list(self, obj: Topic) -> str:
        return ", ".join(obj.keywords or [])

    @admin.action(description="Aprovar (ativar) tópicos selecionados")
    def approve_topics(self, request: HttpRequest, queryset: QuerySet[Topic]) -> None:
        updated = queryset.filter(is_active=False).update(is_active=True)
        if updated:
            curation.schedule_reclassification()
        self.message_user(request, f"{updated} tópico(s) aprovado(s).", messages.SUCCESS)

    def save_related(self, request, form, formsets, change) -> None:
        # Palavras-chave e disciplinas mudam a classificação das notícias (docs/21).
        super().save_related(request, form, formsets, change)
        if {"keywords", "disciplines", "is_active"} & set(form.changed_data):
            curation.schedule_reclassification()
            self.message_user(
                request, "As notícias guardadas serão classificadas de novo em instantes."
            )


@admin.register(ArticleType)
class ArticleTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "has_event_date", "order", "is_active")
    list_editable = ("has_event_date", "order", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}
    fields = ("name", "slug", "description", "has_event_date", "order", "is_active")
