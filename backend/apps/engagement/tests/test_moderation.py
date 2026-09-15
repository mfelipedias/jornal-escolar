"""Moderação dos comentários públicos (docs/20 "Moderação no painel", docs/15; E41).

Aceite: o editor vê todos os pendentes; o autor vê só os das suas publicações.
"""

import uuid
from datetime import timedelta
from io import StringIO

import pytest
from django.contrib.messages import get_messages
from django.core.exceptions import PermissionDenied
from django.core.management import call_command
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.core.models import AuditLog
from apps.dashboard import selectors as dashboard
from apps.dashboard.menu import menu_items
from apps.editorial import alerts
from apps.editorial import selectors as editorial_selectors
from apps.editorial.models import Notification
from apps.engagement import selectors, services
from apps.engagement.models import Comment
from apps.publications import services as article_services
from apps.publications.models import Article, ArticleContributor
from tests.factories import ArticleFactory, UserFactory

pytestmark = pytest.mark.django_db

HX = {"HTTP_HX_REQUEST": "true"}
QUEUE = "/painel/comentarios/"


@pytest.fixture
def carla():
    return UserFactory(full_name="Carla Souza")


@pytest.fixture
def pedro():
    return UserFactory(full_name="Pedro Lima")


@pytest.fixture
def editor():
    return UserFactory(editor=True, full_name="Joana Dias")


def published(author, title):
    article = ArticleFactory(ready=True, author=author, created_by=author, title=title)
    article_services.publish(author, article)
    article.refresh_from_db()
    return article


@pytest.fixture
def horta(carla):
    return published(carla, "Horta da escola")


@pytest.fixture
def feira(pedro):
    return published(pedro, "Feira de ciências")


def make(article, **kwargs):
    data = {"author_name": "Mariana", "body": "Muito legal!", "anon_key": uuid.uuid4()} | kwargs
    return services.submit_comment(article, **data)


def logged(user) -> Client:
    client = Client()
    client.force_login(user)
    return client


def action_url(comment, action):
    return f"/x/comments/{comment.pk}/{action}/"


# --- aceite: quem vê o quê ---


def test_editor_ve_todos_os_pendentes(horta, feira, editor):
    c1 = make(horta, body="Comentário na horta")
    c2 = make(feira, body="Comentário na feira")

    assert set(selectors.moderation_queue(editor)) == {c1, c2}
    html = logged(editor).get(QUEUE).content.decode()
    assert "Comentário na horta" in html
    assert "Comentário na feira" in html
    assert "Todos os comentários de leitores do jornal" in html


def test_autor_ve_so_os_pendentes_das_suas_publicacoes(horta, feira, carla):
    mine = make(horta, body="Comentário na horta")
    make(feira, body="Comentário na feira")

    assert list(selectors.moderation_queue(carla)) == [mine]
    html = logged(carla).get(QUEUE).content.decode()
    assert "Comentário na horta" in html
    assert "Comentário na feira" not in html
    assert "nas suas publicações" in html


def test_coautor_ve_e_revisor_e_colega_nao(horta, feira):
    coauthor, reviewer, colleague = UserFactory(), UserFactory(), UserFactory()
    for user, role in ((coauthor, "coauthor"), (reviewer, "reviewer")):
        ArticleContributor.objects.create(
            article=horta, user=user, display_name=user.public_name, role=role
        )
    comment = make(horta)

    assert list(selectors.moderation_queue(coauthor)) == [comment]
    assert not selectors.moderation_queue(reviewer).exists()
    assert not selectors.moderation_queue(colleague).exists()
    assert selectors.pending_count(colleague) == 0


def test_visitante_vai_para_o_login(client):
    response = client.get(QUEUE)
    assert response.status_code == 302
    assert "/entrar/" in response.url


def test_abas_contam_e_pendentes_vem_do_mais_antigo(horta, carla):
    old = make(horta, body="Primeiro")
    new = make(horta, body="Segundo")
    Comment.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(hours=2))
    services.moderate_comment(carla, make(horta, body="Terceiro"), Comment.Status.APPROVED)
    services.moderate_comment(carla, make(horta, body="Quarto"), Comment.Status.REJECTED)

    assert selectors.tab_counts(carla) == {"pendentes": 2, "aprovados": 1, "rejeitados": 1}
    assert list(selectors.moderation_queue(carla)) == [old, new]
    html = logged(carla).get(QUEUE + "?aba=rejeitados").content.decode()
    assert "Quarto" in html
    assert "Primeiro" not in html


def test_filtro_por_publicacao(horta, feira, editor, pedro):
    make(horta, body="Na horta")
    make(feira, body="Na feira")

    html = logged(editor).get(f"{QUEUE}?publicacao={feira.pk}").content.decode()
    assert "Na feira" in html
    assert "Na horta" not in html
    assert "Só em" in html
    # Publicação que a pessoa não modera: o filtro é ignorado e não vaza o título.
    html = logged(pedro).get(f"{QUEUE}?publicacao={horta.pk}").content.decode()
    assert "Horta da escola" not in html
    assert "Na feira" in html


def test_marcas_de_links_e_mesmo_ip(horta, carla):
    make(horta, body="Veja www.exemplo.com agora mesmo", ip="10.0.0.1")
    make(horta, body="Outro comentário", ip="10.0.0.1")
    make(horta, body="De outra rede", ip="10.0.0.2")

    html = logged(carla).get(QUEUE).content.decode()
    assert html.count('data-flag="links"') == 1
    assert html.count("mesmo IP enviou 2") == 2


# --- ações ---


def test_aprovar_publica_carimba_e_audita(client, horta, carla):
    comment = make(horta, body="Adorei a horta!")

    response = logged(carla).post(action_url(comment, "approve"), **HX)

    assert response.status_code == 200
    assert f'id="moderacao-{comment.pk}"' in response.content.decode()
    assert "Comentário aprovado." in response.content.decode()
    comment.refresh_from_db()
    assert comment.status == Comment.Status.APPROVED
    assert comment.moderated_by == carla
    assert comment.moderated_at is not None
    horta.refresh_from_db()
    assert horta.comments_count == 1
    assert "Adorei a horta!" in client.get(horta.get_absolute_url()).content.decode()
    log = AuditLog.objects.get(action=AuditLog.Action.COMMENT_MODERATED)
    assert log.actor == carla
    assert log.target_id == str(comment.pk)
    assert log.changes["status"] == "approved"
    assert "Mariana" not in str(log.changes)


def test_rejeitar_aprovado_tira_da_pagina(client, horta, carla):
    comment = make(horta, body="Texto que sai")
    services.moderate_comment(carla, comment, Comment.Status.APPROVED)

    response = logged(carla).post(action_url(comment, "reject"), **HX)

    assert response.status_code == 200
    comment.refresh_from_db()
    assert comment.status == Comment.Status.REJECTED
    horta.refresh_from_db()
    assert horta.comments_count == 0
    assert "Texto que sai" not in client.get(horta.get_absolute_url()).content.decode()


def test_sem_javascript_volta_para_a_fila_com_mensagem(horta, carla):
    comment = make(horta)
    client = logged(carla)

    response = client.post(action_url(comment, "approve"), {"next": f"{QUEUE}?aba=pendentes"})

    assert response.status_code == 302
    assert response.url == f"{QUEUE}?aba=pendentes"
    assert [str(m) for m in get_messages(response.wsgi_request)] == ["Comentário aprovado."]


def test_quem_nao_modera_recebe_403(horta, pedro):
    comment = make(horta)
    reviewer = UserFactory()
    ArticleContributor.objects.create(
        article=horta, user=reviewer, display_name=reviewer.public_name, role="reviewer"
    )

    for user in (pedro, reviewer):
        assert logged(user).post(action_url(comment, "approve"), **HX).status_code == 403
    assert Client().post(action_url(comment, "approve")).status_code == 302  # login
    comment.refresh_from_db()
    assert comment.status == Comment.Status.PENDING
    with pytest.raises(PermissionDenied):
        services.moderate_comment(pedro, comment, Comment.Status.APPROVED)


def test_acao_desconhecida_e_404(horta, carla):
    comment = make(horta)
    assert logged(carla).post(action_url(comment, "apagar")).status_code == 404


def test_editar_nome_aplica_a_limpeza_do_envio(horta, carla):
    comment = make(horta, author_name="Mariana Souza")

    response = logged(carla).post(
        action_url(comment, "rename"), {"author_name": "  Mariana\x07   S. "}, **HX
    )

    assert response.status_code == 200
    comment.refresh_from_db()
    assert comment.author_name == "Mariana S."
    assert comment.status == Comment.Status.PENDING


@pytest.mark.parametrize("name", ["M", "Mariana www.site.com", "a@b.com"])
def test_nome_invalido_devolve_400_sem_mudar(horta, carla, name):
    comment = make(horta, author_name="Mariana")

    response = logged(carla).post(action_url(comment, "rename"), {"author_name": name}, **HX)

    assert response.status_code == 400
    assert 'aria-invalid="true"' in response.content.decode()
    comment.refresh_from_db()
    assert comment.author_name == "Mariana"


def test_responder_e_aprovar(client, horta, carla):
    comment = make(horta, body="Dá para fazer na escola?")

    response = logged(carla).post(
        action_url(comment, "reply-approve"), {"reply_body": "Dá sim, em outubro."}, **HX
    )

    assert response.status_code == 200
    comment.refresh_from_db()
    assert comment.status == Comment.Status.APPROVED
    assert comment.reply_body == "Dá sim, em outubro."
    assert comment.replied_by == carla
    html = client.get(horta.get_absolute_url()).content.decode()
    assert "Carla Souza (autoria do texto)" in html


def test_responder_e_aprovar_exige_texto(horta, carla):
    comment = make(horta)

    response = logged(carla).post(action_url(comment, "reply-approve"), {"reply_body": " "}, **HX)

    assert response.status_code == 400
    assert "Escreva a resposta." in response.content.decode()
    comment.refresh_from_db()
    assert comment.status == Comment.Status.PENDING


# --- lote ---


def test_aprovar_em_lote_so_os_que_a_pessoa_modera(horta, feira, carla):
    mine = [make(horta, body=f"Na horta {i}") for i in range(3)]
    other = make(feira)
    ids = [c.pk for c in mine] + [other.pk]

    response = logged(carla).post(
        reverse("engagement:moderate_bulk"), {"acao": "aprovar", "ids": ids, "next": QUEUE}
    )

    assert response.status_code == 302
    assert Comment.objects.filter(status=Comment.Status.APPROVED).count() == 3
    other.refresh_from_db()
    assert other.status == Comment.Status.PENDING
    horta.refresh_from_db()
    assert horta.comments_count == 3
    assert [str(m) for m in get_messages(response.wsgi_request)] == ["3 comentários aprovados."]
    log = AuditLog.objects.get(action=AuditLog.Action.COMMENT_MODERATED)
    assert sorted(log.changes["comments"]) == sorted(c.pk for c in mine)


def test_rejeitar_em_lote_pelo_editor(horta, feira, editor):
    ids = [make(horta).pk, make(feira).pk]

    logged(editor).post(reverse("engagement:moderate_bulk"), {"acao": "rejeitar", "ids": ids})

    assert Comment.objects.filter(status=Comment.Status.REJECTED).count() == 2


@pytest.mark.parametrize(
    ("data", "message"),
    [
        ({"acao": "aprovar"}, "Marque ao menos um comentário."),
        ({"acao": "apagar", "ids": ["1"]}, "Escolha aprovar ou rejeitar."),
    ],
)
def test_lote_invalido(carla, data, message):
    response = logged(carla).post(reverse("engagement:moderate_bulk"), data)
    assert [str(m) for m in get_messages(response.wsgi_request)] == [message]


def test_pagina_tem_formulario_de_lote_fora_dos_itens(horta, carla):
    make(horta)
    html = logged(carla).get(QUEUE).content.decode()
    assert 'id="moderacao-lote"' in html
    assert 'form="moderacao-lote"' in html
    assert "Aprovar marcados" in html


# --- notificações ---


def test_comentario_novo_avisa_autor_e_coautor_agrupado(horta, carla):
    coauthor = UserFactory()
    ArticleContributor.objects.create(
        article=horta, user=coauthor, display_name=coauthor.public_name, role="coauthor"
    )
    make(horta)
    make(horta)

    for user in (carla, coauthor):
        notification = Notification.objects.get(user=user)
        assert notification.kind == Notification.Kind.COMMENT_PENDING
        assert notification.message == "2 comentários aguardam aprovação em “Horta da escola”."
        assert notification.url == f"{QUEUE}?publicacao={horta.pk}"


def test_aviso_lido_e_comentario_novo_cria_outro(horta, carla):
    make(horta)
    Notification.objects.update(read_at=timezone.now())
    make(horta)

    assert Notification.objects.filter(user=carla).count() == 2
    unread = Notification.objects.get(user=carla, read_at__isnull=True)
    assert unread.message.startswith("2 comentários aguardam")


def test_equipe_comentando_no_proprio_texto_nao_se_avisa(horta, carla):
    services.submit_comment(horta, author_name="Carla", body="Obrigada a todos!", user=carla)
    assert not Notification.objects.filter(user=carla).exists()


def test_moderar_tudo_tira_o_aviso_do_sino(horta, carla):
    c1, c2 = make(horta), make(horta)

    services.moderate_comment(carla, c1, Comment.Status.APPROVED)
    notification = Notification.objects.get(user=carla)
    assert notification.read_at is None
    assert notification.message.startswith("1 comentário aguarda")

    services.moderate_comment(carla, c2, Comment.Status.REJECTED)
    notification.refresh_from_db()
    assert notification.read_at is not None


def test_pendente_ha_mais_de_3_dias_avisa_editores_uma_vez(horta, carla, editor):
    admin = UserFactory(admin=True)
    staff = UserFactory()
    comment = make(horta)
    Comment.objects.filter(pk=comment.pk).update(created_at=timezone.now() - timedelta(days=2))
    assert services.remind_stale_pending_comments() == 0

    Comment.objects.filter(pk=comment.pk).update(created_at=timezone.now() - timedelta(days=5))
    out = StringIO()
    call_command("notify_pending_comments", stdout=out)

    assert "Avisos de comentários pendentes: 2." in out.getvalue()
    for user in (editor, admin):
        notification = Notification.objects.get(user=user)
        assert "há mais de 3 dias" in notification.message
        assert notification.url == f"{QUEUE}?publicacao={horta.pk}"
    assert not Notification.objects.filter(user=staff).exists()
    # No dia seguinte, com o aviso lido, rodar de novo não repete.
    yesterday = timezone.now() - timedelta(days=1)
    Notification.objects.update(read_at=yesterday, updated_at=yesterday)
    assert services.remind_stale_pending_comments() == 0
    # Um pendente mais novo que também passou dos 3 dias gera novo aviso.
    newer = make(horta)
    Comment.objects.filter(pk=newer.pk).update(
        created_at=timezone.now() - timedelta(days=3, hours=1)
    )
    Notification.objects.filter(user=carla).update(read_at=yesterday)
    assert services.remind_stale_pending_comments() == 2
    assert Notification.objects.filter(user=editor, read_at__isnull=True).count() == 1


# --- abrir e fechar comentários ---


def toggle_url(article):
    return f"/x/articles/{article.pk}/comments-toggle/"


def test_autor_fecha_e_abre_comentarios(client, horta, carla):
    response = logged(carla).post(
        toggle_url(horta), {"enabled": "0", "next": "/painel/publicacoes/"}
    )

    assert response.status_code == 302
    assert response.url == "/painel/publicacoes/"
    horta.refresh_from_db()
    assert horta.comments_enabled is False
    assert "Os comentários desta publicação estão fechados" not in (
        client.get(horta.get_absolute_url()).content.decode()
    )  # sem aprovados, o bloco some
    logged(carla).post(toggle_url(horta))  # sem o campo, inverte
    horta.refresh_from_db()
    assert horta.comments_enabled is True


def test_fechar_mantem_aprovados_sem_formulario(client, horta, carla):
    services.moderate_comment(carla, make(horta, body="Continua aqui"), Comment.Status.APPROVED)

    logged(carla).post(toggle_url(horta), {"enabled": "0"})

    html = client.get(horta.get_absolute_url()).content.decode()
    assert "Continua aqui" in html
    assert "Os comentários desta publicação estão fechados" in html


def test_colega_nao_fecha_e_editor_fecha(horta, pedro, editor):
    assert logged(pedro).post(toggle_url(horta), {"enabled": "0"}).status_code == 403
    horta.refresh_from_db()
    assert horta.comments_enabled is True

    logged(editor).post(toggle_url(horta), {"enabled": "0"})
    horta.refresh_from_db()
    assert horta.comments_enabled is False


# --- painel ---


def test_inicio_mostra_pendentes_ao_autor(horta, carla):
    make(horta)
    make(horta)

    items, _ = dashboard.pending_items(carla)
    assert items[0].message == "2 comentários aguardam sua aprovação."
    assert items[0].url == QUEUE
    html = logged(carla).get("/painel/").content.decode()
    assert "2 comentários aguardam sua aprovação." in html
    # O aviso do sino não aparece repetido nas pendências.
    assert "em “Horta da escola”" not in html


def test_inicio_do_editor_mostra_total_do_jornal(horta, feira, editor):
    own = published(editor, "Texto do editor")
    make(horta)
    make(feira)
    make(own)

    items, _ = dashboard.pending_items(editor)
    assert (
        items[0].message == "3 comentários aguardam aprovação no jornal (1 nas suas publicações)."
    )


def test_sem_pendentes_nao_ha_linha(carla):
    assert dashboard.comment_pending_items(carla) == []


def test_minhas_publicacoes_mostra_pendentes_e_botao_de_fechar(horta, carla):
    make(horta)
    make(horta)

    html = logged(carla).get("/painel/publicacoes/").content.decode()
    assert f'href="{QUEUE}?publicacao={horta.pk}"' in html
    assert "2 comentários aguardando" in html
    assert "Fechar comentários" in html
    assert f'action="{toggle_url(horta)}"' in html


def test_rascunho_nao_tem_botao_de_fechar(carla):
    ArticleFactory(author=carla, created_by=carla)
    html = logged(carla).get("/painel/publicacoes/").content.decode()
    assert "Fechar comentários" not in html


def test_menu_conta_pendentes(horta, feira, carla, editor):
    make(horta)
    make(feira)

    def count(user):
        return next(item.count for item in menu_items(user) if item.key == "comments")

    assert count(carla) == 1
    assert count(editor) == 2


def test_editorial_conta_e_alerta_pendentes_antigos(horta, editor):
    old = make(horta)
    make(horta)
    Comment.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=5))

    assert editorial_selectors.editorial_counts()["pending_public_comments"] == 2
    group = alerts.pending_public_comments()
    assert len(group.items) == 1
    assert group.items[0].message == "1 comentário aguarda aprovação; o mais antigo há 5 dias."
    html = logged(editor).get("/painel/editorial/").content.decode()
    assert "Comentários de leitores pendentes" in html
    assert f"{QUEUE}?publicacao={horta.pk}" in html


def test_comentarios_desligados_no_site_nao_afetam_a_fila(horta, carla):
    make(horta)
    Article.objects.filter(pk=horta.pk).update(comments_enabled=False)
    assert selectors.pending_count(carla) == 1
