from django.contrib.auth.forms import SetPasswordForm

from .models import User


class AccessLinkPasswordForm(SetPasswordForm):
    """Criar a senha a partir de um link de acesso, com os validadores do Django (mín. 10).

    A gravação é feita por services.use_access_link, não por form.save().
    """

    def __init__(self, user: User, *args, **kwargs) -> None:
        super().__init__(user, *args, **kwargs)
        self.fields["new_password1"].label = "Nova senha"
        self.fields[
            "new_password1"
        ].help_text = (
            "Pelo menos 10 caracteres. Evite senhas comuns ou parecidas com seu nome e e-mail."
        )
        self.fields["new_password2"].label = "Repita a senha"
        self.fields["new_password2"].help_text = ""
