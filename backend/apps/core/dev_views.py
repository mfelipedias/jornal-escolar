"""/dev/components/: vitrine dos componentes do design system (docs/09, E19).

Dados montados à mão, sem banco: a página funciona mesmo com o banco vazio. Aberta em
desenvolvimento (DEBUG) e, em produção, só para o papel admin.
"""

from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import render
from django.templatetags.static import static
from django.utils import timezone
from django.views.decorators.http import require_GET

from apps.publications.presentation import ArticleCard, CardImage, Credit
from apps.taxonomy.models import AreaColor, KnowledgeArea

TOAST_LEVELS = {
    "success": (messages.SUCCESS, "Publicado! A publicação já está no ar."),
    "error": (messages.ERROR, "Não foi possível salvar. Tente de novo em instantes."),
    "warning": (messages.WARNING, "Esta publicação tem aluno sem autorização marcada."),
    "info": (messages.INFO, "Rascunho salvo automaticamente."),
}

AREA_NAMES = {
    AreaColor.CORAL: "Linguagens",
    AreaColor.VERDE: "Ciências da Natureza",
    AreaColor.AZUL: "Matemática",
    AreaColor.AMBAR: "Ciências Humanas",
    AreaColor.VIOLETA: "Formação e Projetos",
    AreaColor.PETROLEO: "Escola e Comunidade",
    AreaColor.MAGENTA: "Magenta",
    AreaColor.GRAFITE: "Geral",
}


def _can_see(request: HttpRequest) -> bool:
    user = request.user
    return settings.DEBUG or (user.is_authenticated and user.role == user.Role.ADMIN)


def _sample_cards() -> list[ArticleCard]:
    now = timezone.now()
    areas = {color: KnowledgeArea(name=name, color=color) for color, name in AREA_NAMES.items()}
    carla = Credit(name="Carla Souza", detail="Professora de Física", is_staff=True)
    rafael = Credit(name="Rafael S.", detail="Aluno, 2ª série B", is_staff=False)
    joao = Credit(name="João Pereira", detail="Coordenação", is_staff=True)
    return [
        ArticleCard(
            title="Feira de Ciências reúne projetos de energia solar",
            subtitle="Turmas da 2ª série montaram painéis, fornos e carregadores com material "
            "reciclado e mediram quanto cada um produz.",
            url="#",
            area=areas[AreaColor.VERDE],
            type_name="Reportagem",
            people=[carla, rafael],
            published_at=now - timedelta(days=1),
            reading_minutes=6,
            image=CardImage(src=static("img/demo/capa-verde.svg"), width=960, height=640),
        ),
        ArticleCard(
            title="O que os gráficos da conta de luz dizem sobre a escola",
            subtitle="Um ano de consumo em números, e onde dá para economizar.",
            url="#",
            area=areas[AreaColor.AZUL],
            type_name="Análise",
            people=[joao, carla, rafael],
            published_at=now - timedelta(days=4),
            reading_minutes=4,
            image=CardImage(src=static("img/demo/capa-azul.svg"), width=960, height=640),
        ),
        ArticleCard(
            title="Sarau de poesia marginal na biblioteca",
            subtitle="Inscrições abertas até sexta para quem quiser ler no palco.",
            url="#",
            area=areas[AreaColor.CORAL],
            type_name="Evento",
            people=[joao],
            published_at=now - timedelta(days=6),
            reading_minutes=2,
        ),
        ArticleCard(
            title="Entrevista: a história do bairro contada por quem viveu",
            url="#",
            area=areas[AreaColor.AMBAR],
            type_name="Entrevista",
            people=[rafael],
            published_at=now - timedelta(days=9),
            reading_minutes=8,
        ),
    ]


@require_GET
def components(request: HttpRequest) -> HttpResponse:
    if not _can_see(request):
        raise Http404

    is_htmx = request.headers.get("HX-Request") == "true"
    if is_htmx and request.GET.get("toast") in TOAST_LEVELS:
        level, text = TOAST_LEVELS[request.GET["toast"]]
        messages.add_message(request, level, text)
        return HttpResponse("")  # o toast vai junto pelo HtmxMessagesMiddleware

    cards = _sample_cards()
    paginator = Paginator([f"Item de exemplo {n}" for n in range(1, 121)], 5)
    page_obj = paginator.get_page(request.GET.get("page"))
    if is_htmx:
        return render(request, "core/partials/components_more.html", {"page_obj": page_obj})

    context = {
        "cards": cards,
        "hero": cards[0],
        "areas": [KnowledgeArea(name=name, color=color) for color, name in AREA_NAMES.items()],
        "statuses": [
            "draft",
            "in_review",
            "changes_requested",
            "approved",
            "published",
            "archived",
        ],
        "page_obj": page_obj,
        "toast_levels": [
            ("success", "sucesso"),
            ("error", "erro"),
            ("warning", "aviso"),
            ("info", "informação"),
        ],
    }
    response = render(request, "core/components.html", context)
    response["X-Robots-Tag"] = "noindex"
    return response
