"""Formulários dos comentários públicos (docs/20).

Os tamanhos aqui valem para o texto como chegou; as regras que dependem da limpeza (links
removidos, limite de pendentes) ficam em services.submit_comment.
"""

from django import forms

from .models import Comment

# Campo armadilha: invisível para pessoas (classe hp-field), preenchido por robôs.
HONEYPOT_FIELD = "website"


class CommentForm(forms.Form):
    author_name = forms.CharField(
        label="Seu nome",
        min_length=Comment.NAME_MIN,
        max_length=Comment.NAME_MAX,
        help_text="Use só o primeiro nome. Ele aparece junto do comentário.",
        error_messages={
            "required": "Escreva seu nome.",
            "min_length": f"O nome precisa de pelo menos {Comment.NAME_MIN} letras.",
            "max_length": f"O nome pode ter no máximo {Comment.NAME_MAX} caracteres.",
        },
    )
    body = forms.CharField(
        label="Comentário",
        min_length=Comment.BODY_MIN,
        max_length=Comment.BODY_MAX,
        widget=forms.Textarea,
        error_messages={
            "required": "Escreva o comentário.",
            "min_length": f"O comentário precisa de pelo menos {Comment.BODY_MIN} caracteres.",
            "max_length": f"O comentário pode ter no máximo {Comment.BODY_MAX} caracteres.",
        },
    )
    website = forms.CharField(label="Não preencha este campo", required=False)

    def is_bot(self) -> bool:
        """O campo armadilha veio preenchido."""
        return bool(self.data.get(HONEYPOT_FIELD, "").strip())


class ReplyForm(forms.Form):
    reply_body = forms.CharField(
        label="Resposta",
        required=False,
        max_length=Comment.REPLY_MAX,
        widget=forms.Textarea,
        help_text="Aparece abaixo do comentário, com o seu nome. Deixe vazio para apagar.",
        error_messages={
            "max_length": f"A resposta pode ter no máximo {Comment.REPLY_MAX} caracteres.",
        },
    )
