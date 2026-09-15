"""Checklist de segurança antes de ir ao ar (docs/23, E28): o que dá para provar em teste.

Outros itens já têm testes próprios, citados na tabela de docs/23:
limite de login (accounts/tests/test_login.py), envios de imagem (publications/tests/
test_media.py e test_media_endpoints.py) e limpeza do HTML (publications/tests/test_rendering.py).
"""

import json
import os
import secrets
import subprocess
import sys

import pytest
from django.conf import settings
from django.test import Client
from django.urls import reverse

from apps.publications import services
from tests.factories import ArticleFactory, UserFactory

pytestmark = pytest.mark.django_db


def _csp(response) -> dict[str, list[str]]:
    policy = response["Content-Security-Policy"]
    return {
        name: values
        for name, *values in (part.split() for part in policy.split(";") if part.strip())
    }


def test_cabecalhos_de_seguranca_nas_paginas(client):
    response = client.get("/")

    assert response["X-Frame-Options"] == "DENY"
    assert response["X-Content-Type-Options"] == "nosniff"
    assert response["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "camera=()" in response["Permissions-Policy"]
    assert "geolocation=()" in response["Permissions-Policy"]
    csp = _csp(response)
    assert csp["default-src"] == ["'self'"]
    assert "'unsafe-inline'" not in csp["script-src"]
    assert csp["script-src"][0] == "'self'"
    assert csp["style-src"] == ["'self'"]
    assert csp["frame-ancestors"] == ["'none'"]
    assert csp["object-src"] == ["'none'"]
    assert set(csp["img-src"]) <= {"'self'", "data:", "blob:"}


def test_csp_do_admin_so_libera_estilos_inline(admin_client):
    csp = _csp(admin_client.get("/admin/"))

    assert "'unsafe-inline'" in csp["style-src"]
    assert "'unsafe-inline'" not in csp["script-src"]


def test_csp_pode_ser_desligada(client, settings):
    settings.CONTENT_SECURITY_POLICY = None

    assert "Content-Security-Policy" not in client.get("/")


def test_login_exige_csrf():
    client = Client(enforce_csrf_checks=True)
    user = UserFactory()

    response = client.post(reverse("accounts:login"), {"login": user.email, "password": "x"})

    assert response.status_code == 403


def test_endpoints_htmx_exigem_csrf(staff_user):
    article = ArticleFactory(created_by=staff_user)
    client = Client(enforce_csrf_checks=True)
    client.force_login(staff_user)
    url = reverse("publications:save_body", args=[article.pk])

    without = client.put(url, json.dumps({"title": "Oi"}), content_type="application/json")
    assert without.status_code == 403

    client.get(reverse("publications:edit", args=[article.pk]))
    token = client.cookies["csrftoken"].value
    with_token = client.put(
        url,
        json.dumps({"title": "Oi"}),
        content_type="application/json",
        headers={"X-CSRFToken": token},
    )
    assert with_token.status_code == 200


def test_telas_de_cadastro_e_senha_por_email_nao_existem(client):
    for path in ("/entrar/signup/", "/entrar/password/reset/", "/entrar/email/"):
        assert client.get(path).status_code == 404


def test_admin_login_passa_pela_tela_com_limite_de_tentativas(client):
    response = client.get("/admin/login/")

    assert response.status_code == 302
    assert response["Location"].startswith(reverse("accounts:login"))


def test_senhas_usam_argon2_e_minimo_de_10_caracteres():
    from config.settings import base

    assert base.PASSWORD_HASHERS[0].endswith("Argon2PasswordHasher")
    validators = {v["NAME"].rsplit(".", 1)[-1]: v for v in base.AUTH_PASSWORD_VALIDATORS}
    assert validators["MinimumLengthValidator"]["OPTIONS"]["min_length"] == 10
    assert "CommonPasswordValidator" in validators


def test_html_de_publicacao_e_gerado_e_limpo_no_servidor(staff_user):
    article = ArticleFactory(created_by=staff_user)
    hostile = {
        "type": "doc",
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": "<script>x()</script>"}]},
            {"type": "script", "content": [{"type": "text", "text": "alert(1)"}]},
            {
                "type": "paragraph",
                "content": [
                    {
                        "type": "text",
                        "text": "link",
                        "marks": [{"type": "link", "attrs": {"href": "javascript:alert(1)"}}],
                    }
                ],
            },
        ],
    }

    services.update_article(staff_user, article, body_json=hostile)

    article.refresh_from_db()
    assert "<script" not in article.body_html
    assert "&lt;script&gt;" in article.body_html
    assert "javascript:" not in article.body_html


def test_sessao_expira_em_14_dias_de_inatividade():
    assert settings.SESSION_COOKIE_AGE == 60 * 60 * 24 * 14
    assert settings.SESSION_SAVE_EVERY_REQUEST
    assert settings.SESSION_COOKIE_SAMESITE == "Lax"


# --- configurações de produção, num processo separado com config.settings.prod ---


def _run_with_prod_settings(*args: str) -> subprocess.CompletedProcess:
    env = {
        **os.environ,
        "DJANGO_SETTINGS_MODULE": "config.settings.prod",
        "SECRET_KEY": secrets.token_urlsafe(50),
        "ALLOWED_HOSTS": "jornal.exemplo.com.br",
        "CSRF_TRUSTED_ORIGINS": "https://jornal.exemplo.com.br",
        "SITE_URL": "https://jornal.exemplo.com.br",
        "DEBUG": "True",  # prod.py precisa ignorar
    }
    return subprocess.run(
        [sys.executable, "manage.py", *args],
        cwd=settings.BASE_DIR,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
    )


def test_check_deploy_sem_avisos_com_configuracao_de_producao():
    result = _run_with_prod_settings("check", "--deploy", "--fail-level", "WARNING")

    assert result.returncode == 0, result.stdout + result.stderr


def test_producao_liga_cookies_seguros_hsts_e_desliga_debug():
    code = (
        "import json; from django.conf import settings as s; print(json.dumps({"
        "'debug': s.DEBUG, 'session': s.SESSION_COOKIE_SECURE, 'csrf': s.CSRF_COOKIE_SECURE, "
        "'httponly': s.SESSION_COOKIE_HTTPONLY, 'ssl': s.SECURE_SSL_REDIRECT, "
        "'hsts': s.SECURE_HSTS_SECONDS, 'csp': bool(s.CONTENT_SECURITY_POLICY), "
        "'proxy': s.SECURE_PROXY_SSL_HEADER, 'cache': s.CACHES['default']['BACKEND']}))"
    )
    result = _run_with_prod_settings("shell", "-c", code)

    assert result.returncode == 0, result.stderr
    values = json.loads(result.stdout.strip().splitlines()[-1])
    assert values == {
        "debug": False,
        "session": True,
        "csrf": True,
        "httponly": True,
        "ssl": True,
        "hsts": 60 * 60 * 24 * 30,
        "csp": True,
        "proxy": ["HTTP_X_FORWARDED_PROTO", "https"],
        # Cache no banco, compartilhado pelos workers do Gunicorn (limites e invalidação).
        "cache": "django.core.cache.backends.db.DatabaseCache",
    }
