from django import forms

from clientes.models import VehiculoCliente

from .models import OrdenTrabajo


class VehiculoElegido(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"{obj} — {obj.cliente}"


class OrdenForm(forms.ModelForm):
    vehiculo = VehiculoElegido(
        queryset=VehiculoCliente.objects.select_related("cliente").order_by("cliente__nombre"), label="Vehículo"
    )

    class Meta:
        model = OrdenTrabajo
        fields = ["vehiculo", "kilometraje", "sintomas"]
        widgets = {"sintomas": forms.Textarea(attrs={"rows": 4})}
