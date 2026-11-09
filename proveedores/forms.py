from django import forms

from inventario.models import Producto, Ubicacion

from .models import Proveedor


class ProveedorForm(forms.ModelForm):
    class Meta:
        model = Proveedor
        fields = ["nombre", "rfc", "contacto", "telefono", "correo", "dias_entrega", "activo"]


class SolicitudManualForm(forms.Form):
    producto = forms.ModelChoiceField(queryset=Producto.objects.filter(activo=True))
    cantidad = forms.IntegerField(min_value=1, max_value=100000)
    referencia = forms.CharField(max_length=60, required=False)


class OrdenCompraForm(forms.Form):
    proveedor = forms.ModelChoiceField(queryset=Proveedor.objects.filter(activo=True))


class RecepcionForm(forms.Form):
    ubicacion = forms.ModelChoiceField(queryset=Ubicacion.objects.filter(activa=True), label="Se guarda en")
