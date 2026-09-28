from django import forms

from apps.accounts.forms import active_disciplines, active_topics
from apps.accounts.models import User


class StoryIdeaForm(forms.Form):
    """Criar ou editar uma pauta (E49). "keep" só na criação; "assigned_to" só para editores."""

    title = forms.CharField(
        label="Título",
        max_length=200,
        error_messages={"required": "Dê um título à pauta."},
    )
    notes = forms.CharField(
        label="Notas",
        max_length=2000,
        required=False,
        widget=forms.Textarea(attrs={"rows": 4}),
        help_text="Ângulo, quem entrevistar, ligação com a escola.",
    )
    topics = forms.ModelMultipleChoiceField(
        label="Tópicos", queryset=active_topics(), required=False
    )
    disciplines = forms.ModelMultipleChoiceField(
        label="Disciplinas", queryset=active_disciplines(), required=False
    )
    keep = forms.BooleanField(label="Fico com esta pauta", required=False)
    assigned_to = forms.ModelChoiceField(
        label="Com quem está",
        queryset=User.objects.none(),
        required=False,
        empty_label="Ninguém (aberta)",
    )

    def __init__(self, *args, creating: bool = True, can_assign: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["topics"].queryset = active_topics()
        self.fields["disciplines"].queryset = active_disciplines()
        if not creating:
            del self.fields["keep"]
        if can_assign:
            self.fields["assigned_to"].queryset = User.objects.filter(is_active=True).order_by(
                "full_name"
            )
        else:
            del self.fields["assigned_to"]
