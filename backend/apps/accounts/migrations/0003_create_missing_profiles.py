from django.db import migrations
from django.utils.text import slugify


def create_missing_profiles(apps, schema_editor):
    """Contas criadas antes da E10 ganham perfil (as novas ganham pelo sinal post_save)."""
    User = apps.get_model("accounts", "User")
    TeacherProfile = apps.get_model("accounts", "TeacherProfile")
    used = set(TeacherProfile.objects.values_list("slug", flat=True))
    for user in User.objects.filter(profile__isnull=True).order_by("pk"):
        base = slugify(user.display_name or user.full_name)[:80] or "perfil"
        slug, n = base, 2
        while slug in used:
            slug, n = f"{base}-{n}", n + 1
        used.add(slug)
        TeacherProfile.objects.create(user=user, slug=slug)


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_teacherprofile_accesslink"),
    ]

    operations = [
        migrations.RunPython(create_missing_profiles, migrations.RunPython.noop),
    ]
