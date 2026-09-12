from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import AdminUserCreationForm, UserChangeForm

from .models import User


class UserCreationForm(AdminUserCreationForm):
    class Meta:
        model = User
        fields = ("email", "full_name", "role", "staff_kind")


class UserEditForm(UserChangeForm):
    class Meta:
        model = User
        fields = "__all__"


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    form = UserEditForm
    add_form = UserCreationForm

    list_display = ("full_name", "email", "role", "staff_kind", "is_active", "last_login")
    list_filter = ("role", "staff_kind", "is_active")
    search_fields = ("full_name", "display_name", "email")
    ordering = ("full_name",)
    readonly_fields = ("is_staff", "last_login", "date_joined")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Identificação", {"fields": ("full_name", "display_name", "staff_kind")}),
        ("Acesso", {"fields": ("role", "is_active", "deactivated_at", "is_staff")}),
        ("Datas", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "full_name",
                    "role",
                    "staff_kind",
                    "usable_password",
                    "password1",
                    "password2",
                ),
            },
        ),
    )
