from django import forms

from .models import Movimiento, Producto, Ubicacion


class ProductoForm(forms.ModelForm):
    class Meta:
        model = Producto
        fields = [
            "codigo",
            "codigo_barras",
            "nombre",
            "categoria",
            "marca",
            "numero_parte",
            "presentacion",
            "especificacion",
            "costo",
            "precio_venta",
            "punto_reorden",
        ]
        widgets = {
            "costo": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "precio_venta": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
        }


class ProductoEditarForm(ProductoForm):
    class Meta(ProductoForm.Meta):
        fields = ProductoForm.Meta.fields + ["activo"]


class UbicacionForm(forms.ModelForm):
    class Meta:
        model = Ubicacion
        fields = ["codigo", "descripcion"]


class MovimientoForm(forms.Form):
    tipo = forms.ChoiceField(choices=Movimiento.Tipo.choices, widget=forms.RadioSelect)
    producto = forms.ModelChoiceField(
        queryset=Producto.objects.filter(activo=True), required=False, widget=forms.HiddenInput
    )
    ubicacion = forms.ModelChoiceField(queryset=Ubicacion.objects.filter(activa=True), label="Ubicación")
    cantidad = forms.IntegerField(min_value=1, max_value=100000)
    motivo = forms.ChoiceField(choices=Movimiento.Motivo.choices)
    referencia = forms.CharField(max_length=60, required=False, help_text="Factura, ticket o folio")
    notas = forms.CharField(max_length=250, required=False)

    def clean(self):
        datos = super().clean()
        tipo, motivo = datos.get("tipo"), datos.get("motivo")
        validos = Movimiento.MOTIVOS_ALTA if tipo == Movimiento.Tipo.ALTA else Movimiento.MOTIVOS_BAJA
        if tipo and motivo and motivo not in validos:
            self.add_error("motivo", "Ese motivo no aplica para este tipo de movimiento.")
        return datos
