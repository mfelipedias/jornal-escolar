"""Comentários públicos (docs/20; E40). Aceite: comentário novo é invisível ao público.

A moderação (aprovar, rejeitar) é da E41; aqui os testes aprovam direto no banco.
"""

import uuid
from datetime import timedelta
from io import StringIO

import pytest
from django.contrib.auth.models import AnonymousUser
from django.contrib.messages import get_messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.test import Client
from django.utils import timezone

from apps.accounts import privacy
from apps.core.audit import hash_ip
from apps.core.models import SiteSetting
from apps.dashboard import selectors as dashboard
from apps.editorial import permissions
from apps.engagement import presentation, services, visitor
from apps.engagement.models import Comment
from apps.publications import services as article_services
from apps.publications.cache import public_version
from apps.publications.models import Article
from tests.factories import ArticleFactory, UserFactory

pytestmark = pytest.mark.django_db

HX = {"HTTP_HX_REQUEST": "true"}
OK = {"author_name": "Mariana", "body": "Adorei a parte sobre os sensores!"}


@pytest.fixture
def author():
    return UserFactory(full_name="Carla Souza")


@pytest.fixture
def article(author):
    item = ArticleFactory(ready=True, author=author, created_by=author, title="Horta da escola")
    article_services.publish(author, item)
    item.refresh_from_db()
    return item


def url(article: Article) -> str:
    return f"/x/articles/{article.pk}/comments/"


def visitor_client(key: uuid.UUID | None = None) -> Client:
    client = Client()
    client.cookies[visitor.COOKIE_NAME] = str(key or uuid.uuid4())
    return client


def approve(comment: Comment) -> Comment:
    Comment.objects.filter(pk=comment.pk).update(status=Comment.Status.APPROVED)
    services.recount_comments(comment.article_id)
    comment.refresh_from_db()
    return comment


def make(article: Article, **kwargs) -> Comment:
    data = {"author_name": "Pedro", "body": "Muito legal!", "anon_key": uuid.uuid4()} | kwargs
    return services.submit_comment(article, **data)


# --- aceite ---


def test_comentario_novo_nasce_pendente_e_invisivel(article, author):
    client = visitor_client()
    response = client.post(url(article), OK, **HX)

    assert response.status_code == 200
    assert "Seu comentário aparece depois que o autor aprovar" in response.content.decode()
    comment = Comment.objects.get()
    assert comment.status == Comment.Status.PENDING
    assert comment.author_name == "Mariana"
    assert comment.ip_hash == hash_ip("127.0.0.1")
    assert str(comment.anon_key) == client.cookies[visitor.COOKIE_NAME].value

    for viewer in (Client(), client, _logged(author), _logged(UserFactory(admin=True))):
        html = viewer.get(article.get_absolute_url()).content.decode()
        assert "Adorei a parte sobre os sensores" not in html
        assert "Mariana" not in html
    article.refresh_from_db()
    assert article.comments_count == 0


def test_aprovado_aparece_na_pagina_com_contagem(client, article):
    approve(make(article, author_name="Mariana", body="Dá para fazer na escola?"))
    make(article, author_name="Pedro", body="Este ainda espera.")

    html = client.get(article.get_absolute_url()).content.decode()

    assert 'id="comentarios"' in html
    assert "Comentários" in html
    assert "(1)" in html
    assert "Mariana" in html
    assert "Dá para fazer na escola?" in html
    assert "Este ainda espera" not in html
    article.refresh_from_db()
    assert article.comments_count == 1


def _logged(user) -> Client:
    client = Client()
    client.force_login(user)
    return client


# --- formulário e regras ---


def test_pagina_mostra_formulario_com_honeypot(client, article):
    html = client.get(article.get_absolute_url()).content.decode()

    assert "Deixe um comentário" in html
    assert 'name="author_name"' in html
    assert 'name="body"' in html
    assert 'class="hp-field" aria-hidden="true"' in html
    assert 'name="website"' in html
    assert 'tabindex="-1"' in html
    assert "Use só o primeiro nome" in html
    assert "Ainda não há comentários" in html


def test_honeypot_preenchido_finge_sucesso_e_nao_grava(article):
    response = visitor_client().post(url(article), OK | {"website": "http://spam"}, **HX)

    assert response.status_code == 200
    assert "Recebido!" in response.content.decode()
    assert not Comment.objects.exists()


def test_links_sao_removidos_e_marcados(article):
    body = "Vejam https://exemplo.com/x e www.spam.net, bit.ly/abc, site.com.br ou a@b.com aqui"
    comment = make(article, body=body)

    assert comment.had_links
    assert comment.body == "Vejam e ou aqui"
    assert "http" not in comment.body


def test_texto_sem_link_nao_e_marcado(article):
    comment = make(article, body="Adorei a parte sobre os sensores.Dá para fazer em 2.5 dias?")

    assert not comment.had_links
    assert comment.body == "Adorei a parte sobre os sensores.Dá para fazer em 2.5 dias?"


def test_so_link_nao_vira_comentario(article):
    with pytest.raises(ValidationError) as error:
        make(article, body="https://exemplo.com/muito-longo")
    assert "Links e e-mails não são aceitos" in str(error.value)
    assert not Comment.objects.exists()


def test_nome_com_link_e_recusado(article):
    response = visitor_client().post(url(article), OK | {"author_name": "www.spam.com"}, **HX)

    assert response.status_code == 400
    assert "Use só o seu nome" in response.content.decode()
    assert not Comment.objects.exists()


@pytest.mark.parametrize(
    ("data", "mensagem"),
    [
        ({"author_name": "M"}, "pelo menos 2 letras"),
        ({"author_name": "x" * 61}, "no máximo 60"),
        ({"body": "Oi"}, "pelo menos 5 caracteres"),
        ({"body": "a" * 1001}, "no máximo 1000"),
        ({"author_name": ""}, "Escreva seu nome"),
    ],
)
def test_tamanhos_invalidos_devolvem_400_com_erro(article, data, mensagem):
    response = visitor_client().post(url(article), OK | data, **HX)

    assert response.status_code == 400
    html = response.content.decode()
    assert mensagem in html
    assert 'aria-invalid="true"' in html
    assert not Comment.objects.exists()


def test_espacos_e_caracteres_de_controle_sao_limpos(article):
    comment = make(
        article, author_name="  Ana   Maria ", body="Linha 1\r\n\r\n\r\n\r\nLinha\x07 2  "
    )

    assert comment.author_name == "Ana Maria"
    assert comment.body == "Linha 1\n\nLinha 2"


def test_corpo_e_escapado_na_pagina(client, article):
    approve(make(article, author_name="<b>Ana</b>", body="<script>alert(1)</script>\nlinha 2"))

    html = client.get(article.get_absolute_url()).content.decode()

    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;<br>linha 2" in html
    assert "&lt;b&gt;Ana&lt;/b&gt;" in html


def test_sem_javascript_redireciona_com_mensagem(article):
    client = visitor_client()
    response = client.post(url(article), OK)

    assert response.status_code == 302
    assert response["Location"] == f"{article.get_absolute_url()}#comentarios"
    assert any("Recebido!" in m.message for m in get_messages(response.wsgi_request))
    assert Comment.objects.filter(status=Comment.Status.PENDING).count() == 1


def test_sem_javascript_erro_mostra_pagina_com_formulario(article):
    response = visitor_client().post(url(article), OK | {"body": "Oi"})

    assert response.status_code == 400
    html = response.content.decode()
    assert "Não deu para enviar" in html
    assert "pelo menos 5 caracteres" in html


def test_visitante_sem_cookie_nao_grava_e_recebe_cookie(client, article):
    response = client.post(url(article), OK, **HX)

    assert response.status_code == 200
    assert "precisa aceitar cookies" in response.content.decode()
    assert visitor.COOKIE_NAME in response.cookies
    assert not Comment.objects.exists()


def test_equipe_logada_comenta_sem_cookie_e_vai_para_moderacao(article):
    member = UserFactory(full_name="Marcos Lima")
    client = _logged(member)

    page = client.get(article.get_absolute_url()).content.decode()
    assert 'value="Marcos Lima"' in page  # nome já preenchido
    response = client.post(url(article), OK | {"author_name": "Marcos"}, **HX)

    assert response.status_code == 200
    comment = Comment.objects.get()
    assert comment.status == Comment.Status.PENDING
    assert comment.anon_key is None


def test_rascunho_nao_recebe_comentario(author):
    draft = ArticleFactory(author=author, created_by=author)

    assert visitor_client().post(url(draft), OK, **HX).status_code == 404
    with pytest.raises(PermissionDenied):
        make(draft)


def test_exige_csrf(article):
    client = Client(enforce_csrf_checks=True)
    client.cookies[visitor.COOKIE_NAME] = str(uuid.uuid4())

    assert client.post(url(article), OK).status_code == 403


def test_comentar_nao_invalida_o_cache_publico(article):
    before = public_version()
    approve(make(article))

    assert public_version() == before


# --- ligar e desligar ---


def test_desligado_no_site_esconde_o_bloco_e_recusa(client, article):
    approve(make(article))
    SiteSetting.objects.create(key="comments.enabled", value=False)

    html = client.get(article.get_absolute_url()).content.decode()

    assert 'id="comentarios"' not in html
    assert not permissions.can_comment(AnonymousUser(), article)
    assert visitor_client().post(url(article), OK, **HX).status_code == 403


def test_fechado_na_publicacao_mostra_aprovados_sem_formulario(client, article):
    approve(make(article, body="Comentário antigo aprovado"))
    Article.objects.filter(pk=article.pk).update(comments_enabled=False)
    article.refresh_from_db()

    html = client.get(article.get_absolute_url()).content.decode()

    assert "Comentário antigo aprovado" in html
    assert "estão fechados" in html
    assert "Deixe um comentário" not in html
    assert visitor_client().post(url(article), OK, **HX).status_code == 403


def test_fechado_e_sem_comentarios_nao_mostra_bloco(client, article):
    Article.objects.filter(pk=article.pk).update(comments_enabled=False)

    assert 'id="comentarios"' not in client.get(article.get_absolute_url()).content.decode()


def test_previa_nao_tem_comentarios(author):
    draft = ArticleFactory(ready=True, author=author, created_by=author)

    html = _logged(author).get(f"/publicacoes/previa/{draft.pk}/").content.decode()

    assert 'id="comentarios"' not in html


# --- limites ---


def test_quarto_pendente_da_mesma_pessoa_na_publicacao_e_bloqueado(article, author):
    client = visitor_client()
    for n in range(3):
        assert client.post(url(article), OK | {"body": f"Comentário {n}"}, **HX).status_code == 200

    response = client.post(url(article), OK | {"body": "O quarto"}, **HX)

    assert response.status_code == 429
    assert "aguardando aprovação" in response.content.decode()
    assert Comment.objects.count() == 3
    # Outra publicação e outra pessoa continuam podendo.
    other = ArticleFactory(ready=True, author=author, created_by=author)
    article_services.publish(author, other)
    assert client.post(url(other), OK, **HX).status_code == 200
    assert visitor_client().post(url(article), OK, **HX).status_code == 200


def test_aprovado_libera_vaga_de_pendente(article):
    key = uuid.uuid4()
    comments = [make(article, anon_key=key, body=f"Comentário {n}") for n in range(3)]
    with pytest.raises(services.CommentLimitError):
        make(article, anon_key=key)

    approve(comments[0])

    assert make(article, anon_key=key).status == Comment.Status.PENDING


def test_11o_comentario_do_mesmo_ip_na_hora_e_bloqueado(article):
    for _ in range(10):
        assert visitor_client().post(url(article), OK, **HX).status_code == 200

    response = visitor_client().post(url(article), OK, **HX)

    assert response.status_code == 429
    assert "na última hora" in response.content.decode()
    assert Comment.objects.count() == 10
    other_ip = visitor_client().post(url(article), OK, REMOTE_ADDR="10.0.0.9", **HX)
    assert other_ip.status_code == 200


def test_envio_invalido_nao_gasta_o_limite_do_ip(article, settings):
    settings.COMMENTS_PER_HOUR_PER_IP = 1
    client = visitor_client()
    for _ in range(3):
        assert client.post(url(article), OK | {"body": "Oi"}, **HX).status_code == 400

    assert client.post(url(article), OK, **HX).status_code == 200


# --- resposta da equipe ---


def reply_url(comment: Comment) -> str:
    return f"/x/comments/{comment.pk}/reply/"


def test_autor_responde_e_resposta_aparece(client, article, author):
    comment = approve(make(article, author_name="Mariana"))

    response = _logged(author).post(reply_url(comment), {"reply_body": "Dá sim, em outubro."}, **HX)

    assert response.status_code == 200
    fragment = response.content.decode()
    assert f'id="comentario-{comment.pk}"' in fragment
    assert "Carla Souza (autoria do texto)" in fragment
    comment.refresh_from_db()
    assert comment.reply_body == "Dá sim, em outubro."
    assert comment.replied_by == author
    assert comment.replied_at is not None
    assert comment.status == Comment.Status.APPROVED  # responder não modera
    html = client.get(article.get_absolute_url()).content.decode()
    assert "Resposta de" in html
    assert "Carla Souza (autoria do texto)" in html
    assert "Dá sim, em outubro." in html
    assert "Responder" not in html  # visitante não vê o formulário


def test_editor_responde_como_edicao_do_jornal(article):
    editor = UserFactory(editor=True, full_name="Joana Dias")
    comment = approve(make(article))

    services.reply_to_comment(editor, comment, "Obrigada pelo comentário!")

    item = presentation.comment_item(comment, article)
    assert item.reply_author == "Joana Dias (edição do jornal)"


def test_quem_nao_assina_nao_responde(article):
    comment = approve(make(article))
    colleague = UserFactory()

    assert _logged(colleague).post(reply_url(comment), {"reply_body": "x"}, **HX).status_code == 403
    assert Client().post(reply_url(comment), {"reply_body": "x"}, **HX).status_code == 403
    with pytest.raises(PermissionDenied):
        services.reply_to_comment(colleague, comment, "Oi")
    comment.refresh_from_db()
    assert comment.reply_body == ""


def test_autor_ve_botao_responder_na_pagina(article, author):
    comment = approve(make(article))

    html = _logged(author).get(article.get_absolute_url()).content.decode()

    assert f'action="/x/comments/{comment.pk}/reply/"' in html
    assert "Responder" in html


def test_resposta_vazia_apaga_e_longa_e_recusada(article, author):
    comment = approve(make(article))
    services.reply_to_comment(author, comment, "Primeira resposta")

    response = _logged(author).post(reply_url(comment), {"reply_body": "x" * 1001}, **HX)
    assert response.status_code == 400
    assert "no máximo 1000" in response.content.decode()

    services.reply_to_comment(author, comment, "   ")
    comment.refresh_from_db()
    assert comment.reply_body == ""
    assert comment.replied_by is None


def test_resposta_sem_javascript_volta_para_o_comentario(article, author):
    comment = approve(make(article))

    response = _logged(author).post(reply_url(comment), {"reply_body": "Valeu!"})

    assert response.status_code == 302
    assert response["Location"] == f"{article.get_absolute_url()}#comentario-{comment.pk}"


# --- contagem, exclusão e limpeza ---


def test_apagar_aprovado_refaz_contagem(article, django_capture_on_commit_callbacks):
    comment = approve(make(article))
    article.refresh_from_db()
    assert article.comments_count == 1

    with django_capture_on_commit_callbacks(execute=True):
        comment.delete()

    article.refresh_from_db()
    assert article.comments_count == 0


def test_limpeza_apaga_rejeitados_antigos_e_dados_tecnicos(article):
    old = timezone.now() - timedelta(days=31)
    rejected_old = make(article)
    rejected_new = make(article)
    approved_old = approve(make(article))
    Comment.objects.filter(pk=rejected_old.pk).update(
        status=Comment.Status.REJECTED, moderated_at=old, created_at=old
    )
    Comment.objects.filter(pk=rejected_new.pk).update(
        status=Comment.Status.REJECTED, moderated_at=timezone.now(), created_at=old
    )
    Comment.objects.filter(pk=approved_old.pk).update(created_at=old, ip_hash="a" * 64)

    out = StringIO()
    call_command("cleanup", stdout=out)

    assert not Comment.objects.filter(pk=rejected_old.pk).exists()
    assert Comment.objects.filter(pk=rejected_new.pk).exists()
    approved_old.refresh_from_db()
    assert approved_old.ip_hash == ""
    assert approved_old.anon_key is None
    assert "Comentários rejeitados apagados: 1." in out.getvalue()


# --- painel, exportação e anonimização ---


def test_painel_conta_comentarios_aprovados(article, author):
    approve(make(article))
    approve(make(article))
    make(article)

    assert dashboard.stats(author)["comments_approved"] == 2
    html = _logged(author).get("/painel/").content.decode()
    assert "Comentários aprovados" in html


def test_exportacao_inclui_respostas_da_conta_sem_o_comentario_do_leitor(article, author):
    comment = approve(make(article, author_name="Mariana", body="Pergunta do leitor"))
    services.reply_to_comment(author, comment, "Resposta da Carla")

    data = privacy.export_user_data(author)

    assert data["respostas_a_comentarios"] == [
        {
            "publicacao": {"id": article.pk, "titulo": "Horta da escola", "estado": "Publicado"},
            "resposta": "Resposta da Carla",
            "situacao_do_comentario": "Aprovado",
            "respondida_em": timezone.localtime(comment.replied_at).isoformat(),
        }
    ]
    assert "Mariana" not in str(data)


def test_anonimizar_mantem_resposta_sem_nome(client, article, author):
    comment = approve(make(article))
    services.reply_to_comment(author, comment, "Aqui é a Carla Souza, obrigada!")

    privacy.anonymize_user(UserFactory(admin=True), author)

    comment.refresh_from_db()
    assert comment.reply_body == f"Aqui é a {privacy.ANONYMIZED_NAME}, obrigada!"
    html = client.get(article.get_absolute_url()).content.decode()
    assert "Resposta de" in html
    assert "equipe do jornal" in html
    assert "Carla" not in html
