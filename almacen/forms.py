from django import forms

from inventario.models import Ubicacion
from mostrador.models import OrdenTrabajo

from .models import Herramienta, PrestamoHerramienta


class EntregaForm(forms.Form):
    ubicacion = forms.ModelChoiceField(queryset=Ubicacion.objects.none(), label="Sale de")
    cantidad = forms.IntegerField(min_value=1)
    recibio = forms.CharField(max_length=120, label="Quién recibe", help_text="Mecánico que recoge la pieza")

    def __init__(self, *args, solicitud, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["ubicacion"].queryset = Ubicacion.objects.filter(
            existencias__producto=solicitud.producto, existencias__cantidad__gt=0
        ).distinct()
        self.fields["cantidad"].max_value = solicitud.pendiente
        self.fields["cantidad"].initial = solicitud.pendiente


class HerramientaForm(forms.ModelForm):
    class Meta:
        model = Herramienta
        fields = ["codigo", "nombre", "ubicacion"]


class PrestamoForm(forms.ModelForm):
    class Meta:
        model = PrestamoHerramienta
        fields = ["mecanico", "orden"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["orden"].queryset = OrdenTrabajo.objects.filter(estado=OrdenTrabajo.Estado.EN_REPARACION)
