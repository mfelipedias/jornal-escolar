"""Fábricas de dados para testes (factory-boy).

Uso: UserFactory() cria um membro da equipe; UserFactory(editor=True) ou
UserFactory(admin=True) mudam o papel; UserFactory.build() cria sem salvar.
"""

import factory

from apps.accounts.models import User
from apps.publications.models import Article, ArticleContributor
from apps.taxonomy.models import ArticleType, Discipline, KnowledgeArea

DEFAULT_PASSWORD = "senha-forte-123"


def text_doc(text: str = "Texto da publicação.") -> dict:
    """Documento mínimo do editor (ProseMirror/TipTap) com um parágrafo."""
    return {
        "type": "doc",
        "content": [{"type": "paragraph", "content": [{"type": "text", "text": text}]}],
    }


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
        django_get_or_create = ("email",)

    email = factory.Sequence(lambda n: f"pessoa{n}@professor.educacao.sp.gov.br")
    full_name = factory.Faker("name", locale="pt_BR")
    password = factory.django.Password(DEFAULT_PASSWORD)
    role = User.Role.STAFF
    staff_kind = User.StaffKind.TEACHER

    class Params:
        editor = factory.Trait(role=User.Role.EDITOR, staff_kind=User.StaffKind.COORDINATOR)
        admin = factory.Trait(role=User.Role.ADMIN)
        # Sem senha utilizável: entra só pela Microsoft ou por link de acesso.
        microsoft_only = factory.Trait(password=factory.django.Password(None))


class KnowledgeAreaFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = KnowledgeArea
        django_get_or_create = ("slug",)

    name = factory.Sequence(lambda n: f"Área {n}")
    slug = factory.Sequence(lambda n: f"area-{n}")
    color = "verde"
    short_name = ""


class DisciplineFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Discipline
        django_get_or_create = ("slug",)

    area = factory.SubFactory(KnowledgeAreaFactory)
    name = factory.Sequence(lambda n: f"Disciplina {n}")
    slug = factory.Sequence(lambda n: f"disciplina-{n}")


class ArticleTypeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ArticleType
        django_get_or_create = ("slug",)

    name = factory.Sequence(lambda n: f"Tipo {n}")
    slug = factory.Sequence(lambda n: f"tipo-{n}")


class ArticleFactory(factory.django.DjangoModelFactory):
    """Rascunho com autor. ArticleFactory(ready=True) já passa na checklist de publicação."""

    class Meta:
        model = Article
        skip_postgeneration_save = True

    title = factory.Sequence(lambda n: f"Publicação de teste {n}")
    created_by = factory.SubFactory(UserFactory)

    class Params:
        ready = factory.Trait(
            subtitle="Linha fina de teste",
            type=factory.SubFactory(ArticleTypeFactory),
            body_json=factory.LazyFunction(text_doc),
        )

    @factory.post_generation
    def author(self, create, extracted, **kwargs):
        if not create:
            return
        user = extracted or self.created_by
        ArticleContributor.objects.create(
            article=self, user=user, display_name=user.public_name, role="author"
        )

    @factory.post_generation
    def disciplines(self, create, extracted, **kwargs):
        if not create:
            return
        if extracted is not None:
            self.disciplines.set(extracted)
        elif self.type_id:  # trait ready
            self.disciplines.add(DisciplineFactory())
