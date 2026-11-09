from django import forms

from inventario.models import Producto

from .models import Presupuesto


class DiagnosticoForm(forms.ModelForm):
    class Meta:
        model = Presupuesto
        fields = ["diagnostico"]
        widgets = {"diagnostico": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["diagnostico"].required = True


class ProductoConStock(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.nombre} {obj.marca} ({obj.codigo}) — {obj.stock} en stock — ${obj.precio_venta:,.2f}"


class RefaccionForm(forms.Form):
    producto = ProductoConStock(
        queryset=Producto.objects.filter(activo=True).con_stock().select_related("marca"), label="Refacción"
    )
    cantidad = forms.IntegerField(min_value=1, max_value=10000, initial=1)


class ServicioForm(forms.Form):
    descripcion = forms.CharField(max_length=200, label="Mano de obra o servicio")
    cantidad = forms.IntegerField(min_value=1, max_value=1000, initial=1)
    precio_unitario = forms.DecimalField(min_value=0, max_digits=10, decimal_places=2, label="Precio unitario (sin IVA)")


class DecisionForm(forms.Form):
    autorizado_por = forms.CharField(max_length=160, label="Quién decidió")
    medio = forms.ChoiceField(choices=Presupuesto.Medio.choices, label="Medio")
