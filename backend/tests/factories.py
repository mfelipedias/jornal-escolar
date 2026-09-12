"""Fábricas de dados para testes (factory-boy).

Uso: UserFactory() cria um membro da equipe; UserFactory(editor=True) ou
UserFactory(admin=True) mudam o papel; UserFactory.build() cria sem salvar.
"""

import factory

from apps.accounts.models import User

DEFAULT_PASSWORD = "senha-forte-123"


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
