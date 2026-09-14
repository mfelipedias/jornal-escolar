# Páginas institucionais passam a usar o editor das publicações (E25).
# O texto simples antigo vira documento do editor (um parágrafo por bloco) e HTML.

import html

from django.db import migrations, models


def _paragraph(block: str) -> dict:
    content: list[dict] = []
    for index, line in enumerate(block.split("\n")):
        if index:
            content.append({"type": "hardBreak"})
        if line:
            content.append({"type": "text", "text": line})
    return {"type": "paragraph", "content": content}


def text_to_body(apps, schema_editor):
    StaticPage = apps.get_model("core", "StaticPage")
    for page in StaticPage.objects.all():
        blocks = [b.strip() for b in page.body.replace("\r\n", "\n").split("\n\n") if b.strip()]
        page.body_json = {"type": "doc", "content": [_paragraph(b) for b in blocks]}
        page.body_html = "".join(
            f"<p>{html.escape(b).replace(chr(10), '<br>')}</p>" for b in blocks
        )
        page.save(update_fields=["body_json", "body_html"])


def body_to_text(apps, schema_editor):
    StaticPage = apps.get_model("core", "StaticPage")
    for page in StaticPage.objects.all():
        blocks = []
        for node in page.body_json.get("content", []):
            parts = [
                "\n" if child.get("type") == "hardBreak" else child.get("text", "")
                for child in node.get("content", [])
            ]
            blocks.append("".join(parts))
        page.body = "\n\n".join(b for b in blocks if b)
        page.save(update_fields=["body"])


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="staticpage",
            name="body_html",
            field=models.TextField(blank=True, verbose_name="corpo em HTML"),
        ),
        migrations.AddField(
            model_name="staticpage",
            name="body_json",
            field=models.JSONField(
                blank=True, default=dict, verbose_name="corpo (documento do editor)"
            ),
        ),
        migrations.RunPython(text_to_body, body_to_text),
        migrations.RemoveField(
            model_name="staticpage",
            name="body",
        ),
    ]
