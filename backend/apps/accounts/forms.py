from urllib.parse import urlsplit

from django import forms
from django.contrib.auth.forms import PasswordChangeForm, SetPasswordForm
from django.utils import timezone
from django.utils.text import slugify

from apps.taxonomy.models import Discipline, KnowledgeArea, Topic

from .models import TeacherProfile, User
from .services import AVATAR_MAX_BYTES, EDUCATION_LIMIT, LINKS_LIMIT

PASSWORD_HELP = "Pelo menos 10 caracteres. Evite senhas comuns ou parecidas com seu nome e e-mail."


class AccessLinkPasswordForm(SetPasswordForm):
    """Criar a senha a partir de um link de acesso, com os validadores do Django (mín. 10).

    A gravação é feita por services.use_access_link, não por form.save().
    """

    def __init__(self, user: User, *args, **kwargs) -> None:
        super().__init__(user, *args, **kwargs)
        self.fields["new_password1"].label = "Nova senha"
        self.fields["new_password1"].help_text = PASSWORD_HELP
        self.fields["new_password2"].label = "Repita a senha"
        self.fields["new_password2"].help_text = ""


class AccountPasswordForm(PasswordChangeForm):
    """/painel/conta/: alterar a senha, pedindo a atual."""

    def __init__(self, user: User, *args, **kwargs) -> None:
        super().__init__(user, *args, **kwargs)
        self.fields["old_password"].label = "Senha atual"
        self.fields["new_password1"].label = "Nova senha"
        self.fields["new_password1"].help_text = PASSWORD_HELP
        self.fields["new_password2"].label = "Repita a nova senha"
        self.fields["new_password2"].help_text = ""
        self.error_messages["password_incorrect"] = "A senha atual não confere."


# --- Perfil e assistente de primeiro acesso (E23, docs/14) ---

PHOTO_ACCEPT = "image/jpeg,image/png,image/webp"
NAME_REQUIRED = "Informe como seu nome aparece no jornal."


def active_disciplines():
    return Discipline.objects.filter(is_active=True, area__is_active=True).select_related("area")


def active_areas():
    return KnowledgeArea.objects.filter(is_active=True)


def active_topics():
    return Topic.objects.filter(is_active=True)


def _clean_display_name(value: str) -> str:
    value = " ".join((value or "").split())
    if not value:
        raise forms.ValidationError(NAME_REQUIRED)
    return value


def _is_http_url(url: str) -> bool:
    """Mesma regra de public_views.safe_links: só http e https, com domínio."""
    parts = urlsplit(url)
    return parts.scheme in ("http", "https") and bool(parts.netloc)


class PhotoFormMixin(forms.Form):
    photo = forms.FileField(
        label="Foto",
        required=False,
        help_text="Aparece nas suas publicações e no seu perfil. JPG, PNG ou WebP até 5 MB.",
        widget=forms.FileInput(attrs={"accept": PHOTO_ACCEPT}),
    )

    def clean_photo(self):
        photo = self.cleaned_data.get("photo")
        if photo and photo.size > AVATAR_MAX_BYTES:
            raise forms.ValidationError("A foto pode ter no máximo 5 MB.")
        return photo


class IdentityStepForm(PhotoFormMixin):
    """Passo 1 do assistente: quem é você."""

    display_name = forms.CharField(
        label="Nome de exibição", max_length=80, error_messages={"required": NAME_REQUIRED}
    )
    headline = forms.CharField(label="Apresentação curta", max_length=120, required=False)

    def clean_display_name(self) -> str:
        return _clean_display_name(self.cleaned_data.get("display_name", ""))


class WorkStepForm(forms.Form):
    """Passo 2 do assistente: disciplinas (docentes) ou áreas (demais cargos)."""

    disciplines = forms.ModelMultipleChoiceField(queryset=Discipline.objects.none(), required=False)
    areas = forms.ModelMultipleChoiceField(queryset=KnowledgeArea.objects.none(), required=False)

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.fields["disciplines"].queryset = active_disciplines()
        self.fields["areas"].queryset = active_areas()


class InterestsStepForm(forms.Form):
    """Passo 3 do assistente: tópicos de interesse e "Sobre mim"."""

    topics = forms.ModelMultipleChoiceField(queryset=Topic.objects.none(), required=False)
    new_topic = forms.CharField(label="Sugerir um tópico", max_length=80, required=False)
    bio = forms.CharField(label="Sobre mim", max_length=800, required=False)

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.fields["topics"].queryset = active_topics()


class ProfileForm(PhotoFormMixin):
    """/painel/perfil/: tudo numa página, um botão salvar (docs/14, "Formulário de perfil").

    Formação e links chegam como linhas numeradas (edu_degree_0, link_url_0...) e viram as
    listas JSON do perfil. Linhas vazias são ignoradas. Cargo e papel não entram: só o admin.
    """

    remove_photo = forms.BooleanField(label="Remover foto", required=False)
    display_name = forms.CharField(
        label="Nome de exibição", max_length=80, error_messages={"required": NAME_REQUIRED}
    )
    update_credits = forms.BooleanField(required=False)
    headline = forms.CharField(
        label="Apresentação curta",
        max_length=120,
        error_messages={"required": "Escreva uma apresentação curta."},
    )
    bio = forms.CharField(label="Sobre mim", max_length=800, required=False)
    since_year = forms.IntegerField(label="Na escola desde", required=False, min_value=1950)
    is_public = forms.BooleanField(label="Perfil público", required=False)
    slug = forms.CharField(label="Endereço do perfil", max_length=90)
    disciplines = forms.ModelMultipleChoiceField(queryset=Discipline.objects.none(), required=False)
    areas = forms.ModelMultipleChoiceField(queryset=KnowledgeArea.objects.none(), required=False)
    topics = forms.ModelMultipleChoiceField(queryset=Topic.objects.none(), required=False)
    new_topic = forms.CharField(label="Sugerir um tópico", max_length=80, required=False)
    accepts_english = forms.BooleanField(required=False)
    include_low_trust = forms.BooleanField(required=False)
    show_reviewer_credit = forms.BooleanField(required=False)
    reviewers_may_publish = forms.BooleanField(required=False)
    show_reads = forms.BooleanField(required=False)

    PROFILE_FIELDS = (
        "headline",
        "bio",
        "since_year",
        "is_public",
        "slug",
        "accepts_english",
        "include_low_trust",
        "show_reviewer_credit",
        "reviewers_may_publish",
        "show_reads",
        "links",
        "education",
    )

    def __init__(self, user: User, *args, **kwargs) -> None:
        self.user = user
        self.profile = user.profile
        super().__init__(*args, **kwargs)
        self.fields["disciplines"].queryset = active_disciplines()
        self.fields["areas"].queryset = active_areas()
        self.fields["topics"].queryset = active_topics()
        self.link_errors: list[str] = []
        self.education_errors: list[str] = []
        if not self.is_bound:
            profile = self.profile
            self.initial.update(
                {
                    "display_name": user.public_name,
                    "headline": profile.headline,
                    "bio": profile.bio,
                    "since_year": profile.since_year,
                    "is_public": profile.is_public,
                    "slug": profile.slug,
                    "disciplines": list(profile.disciplines.values_list("pk", flat=True)),
                    "areas": list(profile.areas.values_list("pk", flat=True)),
                    "topics": list(profile.topics.values_list("pk", flat=True)),
                    "accepts_english": profile.accepts_english,
                    "include_low_trust": profile.include_low_trust,
                    "show_reviewer_credit": profile.show_reviewer_credit,
                    "reviewers_may_publish": profile.reviewers_may_publish,
                    "show_reads": profile.show_reads,
                }
            )

    # --- linhas de formação e links ---

    def link_rows(self) -> list[dict[str, str]]:
        if self.is_bound:
            rows = [
                {
                    "label": self.data.get(f"link_label_{i}", "").strip(),
                    "url": self.data.get(f"link_url_{i}", "").strip(),
                }
                for i in range(LINKS_LIMIT)
            ]
        else:
            saved = [i for i in self.profile.links if isinstance(i, dict)][:LINKS_LIMIT]
            rows = [
                {"label": str(i.get("label") or ""), "url": str(i.get("url") or "")} for i in saved
            ]
            rows += [{"label": "", "url": ""} for _ in range(LINKS_LIMIT - len(rows))]
        return [dict(row, index=n) for n, row in enumerate(rows)]

    def education_rows(self) -> list[dict[str, str]]:
        keys = ("degree", "institution", "year")
        if self.is_bound:
            rows = [
                {k: self.data.get(f"edu_{k}_{i}", "").strip() for k in keys}
                for i in range(EDUCATION_LIMIT)
            ]
        else:
            saved = [i for i in self.profile.education if isinstance(i, dict)][:EDUCATION_LIMIT]
            rows = [{k: str(i.get(k) or "") for k in keys} for i in saved]
            rows += [dict.fromkeys(keys, "") for _ in range(EDUCATION_LIMIT - len(rows))]
        return [dict(row, index=n) for n, row in enumerate(rows)]

    def _clean_links(self) -> list[dict[str, str]]:
        links = []
        for row in self.link_rows():
            if not row["url"] and not row["label"]:
                continue
            if not row["url"]:
                self.link_errors.append(f'Informe o endereço do link "{row["label"][:40]}".')
            elif len(row["url"]) > 300 or not _is_http_url(row["url"]):
                self.link_errors.append(
                    f'Link "{row["url"][:60]}" inválido: use um endereço que comece com https://.'
                )
            else:
                links.append({"label": row["label"][:40], "url": row["url"]})
        return links

    def _clean_education(self) -> list[dict[str, str]]:
        items = []
        for row in self.education_rows():
            if not (row["degree"] or row["institution"] or row["year"]):
                continue
            if not row["degree"]:
                self.education_errors.append("Cada formação precisa de um título.")
            elif row["year"] and not (row["year"].isdigit() and len(row["year"]) == 4):
                self.education_errors.append(f'Ano inválido na formação "{row["degree"][:60]}".')
            else:
                items.append(
                    {
                        "degree": row["degree"][:120],
                        "institution": row["institution"][:120],
                        "year": row["year"],
                    }
                )
        return items

    # --- validação ---

    def clean_display_name(self) -> str:
        return _clean_display_name(self.cleaned_data.get("display_name", ""))

    def clean_since_year(self) -> int | None:
        year = self.cleaned_data.get("since_year")
        if year and year > timezone.localdate().year:
            raise forms.ValidationError("O ano não pode estar no futuro.")
        return year

    def clean_slug(self) -> str:
        slug = slugify(self.cleaned_data.get("slug", ""))[:90]
        if not slug:
            raise forms.ValidationError("Use letras, números e hifens.")
        if TeacherProfile.objects.exclude(pk=self.profile.pk).filter(slug=slug).exists():
            raise forms.ValidationError("Este endereço já é usado por outro perfil.")
        return slug

    def clean(self) -> dict:
        cleaned = super().clean()
        cleaned["links"] = self._clean_links()
        cleaned["education"] = self._clean_education()
        for error in self.link_errors + self.education_errors:
            self.add_error(None, error)
        if cleaned.get("is_public"):
            if self.user.staff_kind == User.StaffKind.TEACHER:
                if not cleaned.get("disciplines"):
                    self.add_error("disciplines", "Marque ao menos uma disciplina.")
            elif not cleaned.get("areas"):
                self.add_error("areas", "Marque ao menos uma área de atuação.")
        return cleaned

    def profile_fields(self) -> dict:
        return {key: self.cleaned_data[key] for key in self.PROFILE_FIELDS}


# --- Cadastro próprio (Fase 4b, C1) ---


class SignupRequestForm(forms.Form):
    """/cadastro/: nome e e-mail institucional. "website" é o campo-isca contra robôs."""

    full_name = forms.CharField(
        label="Nome completo",
        max_length=150,
        error_messages={"required": "Escreva o seu nome."},
    )
    email = forms.EmailField(
        label="E-mail institucional",
        max_length=254,
        error_messages={
            "required": "Escreva o seu e-mail.",
            "invalid": "Confira o e-mail.",
        },
    )
    website = forms.CharField(required=False)

    def clean_full_name(self) -> str:
        name = " ".join(self.cleaned_data["full_name"].split())
        if len(name) < 3:
            raise forms.ValidationError("Escreva o seu nome completo.")
        return name


class SignupConfirmForm(AccessLinkPasswordForm):
    """/cadastro/confirmar/: código do e-mail e a senha nova."""

    code = forms.CharField(
        label="Código de 6 dígitos",
        max_length=12,
        error_messages={"required": "Digite o código que chegou no seu e-mail."},
    )
    field_order = ["code", "new_password1", "new_password2"]


class PasswordResetRequestForm(forms.Form):
    """/entrar/esqueci/: só o e-mail da conta."""

    email = forms.EmailField(
        label="E-mail da sua conta",
        max_length=254,
        error_messages={"required": "Escreva o seu e-mail.", "invalid": "Confira o e-mail."},
    )
