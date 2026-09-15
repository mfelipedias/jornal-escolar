"""Página de Privacidade (docs/23, E28)."""

import pytest

from apps.core.models import StaticPage
from apps.core.services import (
    E28_PRIVACY_MARKER,
    E38_PRIVACY_MARKER,
    OLD_PRIVACY_MARKER,
    seed_site,
    text_to_document,
)

pytestmark = pytest.mark.django_db


def test_text_to_document_entende_subtitulo_e_lista():
    doc = text_to_document("## Alunos\n\n- um\n- dois\n\nlinha 1\nlinha 2")

    heading, bullet, paragraph = doc["content"]
    assert heading == {
        "type": "heading",
        "attrs": {"level": 2},
        "content": [{"type": "text", "text": "Alunos"}],
    }
    assert bullet["type"] == "bulletList"
    assert [item["content"][0]["content"][0]["text"] for item in bullet["content"]] == [
        "um",
        "dois",
    ]
    assert [node["type"] for node in paragraph["content"]] == ["text", "hardBreak", "text"]


def test_seed_cria_privacidade_completa_e_despublicada():
    seed_site()

    page = StaticPage.objects.get(slug="privacidade")
    assert not page.is_published  # precisa da aprovação da direção
    html = page.body_html
    assert "RASCUNHO" not in html
    for trecho in (
        "<h2>Quem só lê o jornal</h2>",
        "<h2>Alunos</h2>",
        "<h2>Equipe da escola</h2>",
        "<h2>Comentários</h2>",
        "<h2>Seus direitos</h2>",
        "<ul>",
        "Lei 13.709/2018",
        "primeiro nome com a inicial do sobrenome",
        "secretaria",
        "e-mail de contato",
    ):
        assert trecho in html


def test_seed_atualiza_rascunho_antigo_nunca_editado():
    old = text_to_document(f"{OLD_PRIVACY_MARKER}\n\nTexto curto.")
    StaticPage.objects.create(
        slug="privacidade",
        title="Privacidade",
        body_json=old,
        body_html=f"<p>{OLD_PRIVACY_MARKER}</p><p>Texto curto.</p>",
        is_published=False,
    )

    seed_site()

    page = StaticPage.objects.get(slug="privacidade")
    assert "<h2>Seus direitos</h2>" in page.body_html
    assert not page.is_published


def test_privacidade_descreve_o_cookie_das_reacoes():
    seed_site()

    html = StaticPage.objects.get(slug="privacidade").body_html
    assert "cookie “jv”" in html
    assert "um ano" in html
    assert E28_PRIVACY_MARKER not in html


def test_seed_atualiza_texto_da_e28_nunca_editado():
    StaticPage.objects.create(
        slug="privacidade",
        title="Privacidade",
        body_html=f"<p>{E28_PRIVACY_MARKER}, um cookie...</p>",
        is_published=True,
    )

    seed_site()

    page = StaticPage.objects.get(slug="privacidade")
    assert "cookie “jv”" in page.body_html
    assert page.is_published  # a publicação da página não muda


def test_seed_nao_mexe_em_texto_da_e28_editado(editor_user):
    StaticPage.objects.create(
        slug="privacidade",
        title="Privacidade",
        body_html=f"<p>{E28_PRIVACY_MARKER}, revisado pela direção.</p>",
        updated_by=editor_user,
    )

    seed_site()

    assert "revisado pela direção" in StaticPage.objects.get(slug="privacidade").body_html


def test_seed_nao_mexe_em_privacidade_editada(editor_user):
    StaticPage.objects.create(
        slug="privacidade",
        title="Privacidade",
        body_html=f"<p>{OLD_PRIVACY_MARKER}</p><p>Revisado pela direção.</p>",
        is_published=True,
        updated_by=editor_user,
    )

    seed_site()

    page = StaticPage.objects.get(slug="privacidade")
    assert "Revisado pela direção." in page.body_html
    assert page.is_published


def test_privacidade_descreve_os_comentarios():
    seed_site()

    html = StaticPage.objects.get(slug="privacidade").body_html
    assert "não pedimos e-mail nem telefone" in html
    assert "aparece em público" in html
    assert "apagados em 30 dias" in html
    assert "remoção de um comentário" in html
    assert E38_PRIVACY_MARKER not in html


def test_seed_atualiza_texto_da_e38_nunca_editado():
    StaticPage.objects.create(
        slug="privacidade",
        title="Privacidade",
        body_html=f"<p>{E38_PRIVACY_MARKER}, nunca o endereço em si.</p>",
        is_published=True,
    )

    seed_site()

    page = StaticPage.objects.get(slug="privacidade")
    assert "não pedimos e-mail nem telefone" in page.body_html
    assert page.is_published
