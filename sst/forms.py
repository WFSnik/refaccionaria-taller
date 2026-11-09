from django import forms

from .models import EntregaEPP, Incidente, Inspeccion, Protocolo
from .services import protocolos_de_orden


class ProtocoloForm(forms.ModelForm):
    class Meta:
        model = Protocolo
        fields = ["nombre", "descripcion", "norma", "frecuencia_dias", "requerido_en_orden", "activo"]


class InspeccionForm(forms.ModelForm):
    class Meta:
        model = Inspeccion
        fields = ["resultado", "observaciones", "fecha"]
        widgets = {"fecha": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}


class IncidenteForm(forms.ModelForm):
    class Meta:
        model = Incidente
        fields = ["tipo", "severidad", "area", "descripcion"]
        widgets = {"descripcion": forms.Textarea(attrs={"rows": 4})}


class CerrarIncidenteForm(forms.Form):
    accion_correctiva = forms.CharField(label="Acción correctiva", widget=forms.Textarea(attrs={"rows": 4}))


class EppForm(forms.ModelForm):
    class Meta:
        model = EntregaEPP
        fields = ["empleado", "equipo", "cantidad", "costo_total", "fecha"]
        widgets = {"fecha": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}

    def clean_costo_total(self):
        costo = self.cleaned_data["costo_total"]
        if costo < 0:
            raise forms.ValidationError("El costo no puede ser negativo.")
        return costo


class LiberacionForm(forms.Form):
    confirmados = forms.ModelMultipleChoiceField(
        queryset=Protocolo.objects.none(), widget=forms.CheckboxSelectMultiple, required=False, label="Protocolos confirmados"
    )
    notas = forms.CharField(max_length=250, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["confirmados"].queryset = protocolos_de_orden()
