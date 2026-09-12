from django import forms

from .models import MediaAsset


class MediaAssetMetadataForm(forms.ModelForm):
    """Campos que o diálogo da imagem no editor altera (docs/16)."""

    class Meta:
        model = MediaAsset
        fields = ("alt_text", "is_decorative", "credit", "license", "has_people", "consent_ok")
