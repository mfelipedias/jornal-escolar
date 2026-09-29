"""Prints do README (docs/img/), tirados com o navegador a partir da demonstração.

SÓ PARA DESENVOLVIMENTO. Passo a passo:

    make assets                               # build do frontend (o servidor usa os arquivos)
    uv run python manage.py seed_demo         # equipe, publicações, notícias e pautas fictícias
    uv run playwright install chromium        # uma vez: baixa o navegador
    uv run python manage.py screenshots

O comando sobe um servidor próprio numa porta livre, entra no painel como a professora fictícia
"Carla" (sessão criada direto no banco, sem senha), esconde o bloco do clima (não mostra a
cidade da escola) e grava WebP comprimidos em docs/img/. Use num banco só com dados de
demonstração: tudo o que estiver no banco pode aparecer nos prints.
"""

import io
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

from django.conf import settings
from django.contrib.auth import BACKEND_SESSION_KEY, HASH_SESSION_KEY, SESSION_KEY
from django.contrib.sessions.backends.db import SessionStore
from django.core.management.base import BaseCommand, CommandError
from PIL import Image, ImageDraw, ImageFilter

from apps.accounts.models import User
from apps.core import demo, demo_data
from apps.publications.models import Article, ArticleContributor

HIDE = "[data-weather] { display: none !important; }"
WEBP_QUALITY = 82
DESKTOP = (1280, 800)
PHONE = (390, 844)
PAPER = (255, 253, 247)  # --color-paper (frontend/src/css/app.css)
ACCENT_SOFT = (255, 225, 238)  # --color-accent-soft


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait(url: str, seconds: int = 30) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2):
                return
        except OSError:
            time.sleep(0.3)
    raise CommandError(f"O servidor não respondeu em {url}.")


def _save(image: Image.Image, path: Path) -> int:
    image.convert("RGB").save(path, "WEBP", quality=WEBP_QUALITY, method=6)
    return path.stat().st_size


def _rounded(image: Image.Image, radius: int) -> Image.Image:
    mask = Image.new("L", image.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, *image.size), radius=radius, fill=255)
    out = image.convert("RGBA")
    out.putalpha(mask)
    return out


def _shadow(canvas: Image.Image, box: tuple[int, int, int, int], radius: int) -> None:
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    x0, y0, x1, y1 = box
    ImageDraw.Draw(layer).rounded_rectangle(
        (x0 + 6, y0 + 14, x1 + 6, y1 + 14), radius=radius, fill=(60, 30, 40, 70)
    )
    canvas.alpha_composite(layer.filter(ImageFilter.GaussianBlur(18)))


def compose_cover(desktop: Image.Image, phone: Image.Image) -> Image.Image:
    """Capa do README: o site no computador e, na frente, no celular."""
    width, height = 1600, 940
    canvas = Image.new("RGBA", (width, height), (*PAPER, 255))
    ImageDraw.Draw(canvas).ellipse((900, -300, 2000, 700), fill=(*ACCENT_SOFT, 255))
    desk = _rounded(desktop.resize((1180, int(1180 * desktop.height / desktop.width))), 18)
    desk_box = (60, 60, 60 + desk.width, 60 + desk.height)
    _shadow(canvas, desk_box, 18)
    canvas.alpha_composite(desk, desk_box[:2])
    ph = _rounded(phone.resize((330, int(330 * phone.height / phone.width))), 34)
    frame = Image.new("RGBA", (ph.width + 20, ph.height + 20), (0, 0, 0, 0))
    ImageDraw.Draw(frame).rounded_rectangle((0, 0, *frame.size), radius=42, fill=(28, 24, 30, 255))
    frame.alpha_composite(ph, (10, 10))
    phone_box = (width - frame.width - 70, height - frame.height - 40)
    _shadow(canvas, (*phone_box, phone_box[0] + frame.width, phone_box[1] + frame.height), 42)
    canvas.alpha_composite(frame, phone_box)
    return canvas


class Command(BaseCommand):
    help = "SÓ PARA DESENVOLVIMENTO: tira os prints do README (docs/img/) a partir do seed_demo."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--saida",
            default=str(settings.BASE_DIR.parent / "docs" / "img"),
            help="Pasta dos arquivos (padrão: docs/img).",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        try:
            demo.ensure_allowed()
        except demo.DemoNotAllowed as exc:
            raise CommandError(str(exc)) from exc
        if not (settings.BASE_DIR / "static" / "dist" / "manifest.json").exists():
            raise CommandError("Falta o build do frontend: rode make assets antes.")
        teacher = User.objects.filter(email=demo.email_for("carla")).first()
        if teacher is None:
            raise CommandError("Falta a demonstração: rode seed_demo antes.")
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise CommandError("Falta o Playwright: rode uv sync (dependências de dev).") from exc

        out = Path(options["saida"])
        out.mkdir(parents=True, exist_ok=True)
        session = SessionStore()
        session[SESSION_KEY] = str(teacher.pk)
        session[BACKEND_SESSION_KEY] = "django.contrib.auth.backends.ModelBackend"
        session[HASH_SESSION_KEY] = teacher.get_session_auth_hash()
        session.create()
        article = self._showcase_article()

        port = _free_port()
        base = f"http://127.0.0.1:{port}"
        server = subprocess.Popen(
            [sys.executable, "manage.py", "runserver", f"127.0.0.1:{port}", "--noreload"],
            cwd=settings.BASE_DIR,
            env={**os.environ, "VITE_DEV_MODE": "False"},
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            _wait(f"{base}/healthz/")
            with sync_playwright() as pw:
                browser = pw.chromium.launch()
                shots = self._shoot(browser, base, session.session_key, article)
                browser.close()
        finally:
            server.terminate()
            server.wait(timeout=10)
            session.delete()

        cover = compose_cover(shots.pop("inicio"), shots.pop("inicio-celular"))
        files = {"capa": cover, **shots}
        for name, image in files.items():
            size = _save(image, out / f"{name}.webp")
            self.stdout.write(f"docs/img/{name}.webp: {size // 1024} KB")
        self.stdout.write(self.style.SUCCESS("Prints prontos."))

    def _showcase_article(self) -> Article:
        """Publicação da demonstração com capa e aluno creditado, a mais completa."""
        demo_articles = Article.objects.filter(
            created_by__email__endswith=f"@{demo_data.DEMO_EMAIL_DOMAIN}",
            status=Article.Status.PUBLISHED,
            cover__isnull=False,
        )
        with_student = demo_articles.filter(
            pk__in=ArticleContributor.objects.filter(is_student=True).values("article")
        )
        article = with_student.first() or demo_articles.first()
        if article is None:
            raise CommandError("Nenhuma publicação da demonstração no ar: rode seed_demo.")
        return article

    def _shoot(self, browser, base: str, session_key: str, article: Article) -> dict:
        def page_for(viewport: tuple[int, int], logged: bool):
            context = browser.new_context(
                viewport={"width": viewport[0], "height": viewport[1]},
                reduced_motion="reduce",
                # A CSP do site bloqueia estilo inline; só o navegador dos prints a ignora.
                bypass_csp=True,
                locale="pt-BR",
            )
            if logged:
                context.add_cookies([{"name": "sessionid", "value": session_key, "url": base}])
            return context.new_page()

        def grab(page, path: str, full: bool = False) -> Image.Image:
            page.goto(base + path, wait_until="networkidle")
            page.add_style_tag(content=HIDE)
            page.wait_for_timeout(300)
            return Image.open(io.BytesIO(page.screenshot(full_page=full)))

        public = page_for(DESKTOP, logged=False)
        phone = page_for(PHONE, logged=False)
        panel = page_for((1280, 900), logged=True)
        return {
            "inicio": grab(public, "/"),
            "inicio-celular": grab(phone, "/"),
            "publicacao": grab(public, article.get_absolute_url()),
            "sugestoes": grab(panel, "/painel/sugestoes/"),
            "pautas": grab(panel, "/painel/pautas/"),
        }
