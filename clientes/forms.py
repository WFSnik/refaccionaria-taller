from datetime import date

from django import forms

from .models import Cliente, VehiculoCliente


class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = ["nombre", "telefono", "correo", "rfc", "notas"]


class VehiculoForm(forms.ModelForm):
    class Meta:
        model = VehiculoCliente
        fields = ["marca", "modelo", "anio", "placas", "vin", "color"]

    def clean_anio(self):
        anio = self.cleaned_data["anio"]
        if not 1950 <= anio <= date.today().year + 1:
            raise forms.ValidationError("Revisa el año del vehículo.")
        return anio

    def clean_placas(self):
        # La restricción de placas únicas es condicional, así que el ModelForm no la valida solo.
        placas = self.cleaned_data["placas"].strip().upper()
        if placas and VehiculoCliente.objects.filter(placas=placas).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Ya hay un vehículo registrado con esas placas.")
        return placas
