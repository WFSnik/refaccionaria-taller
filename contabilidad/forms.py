from decimal import Decimal

from django import forms

from .models import Gasto, Pago

UN_CENTAVO = Decimal("0.01")


class PagoForm(forms.ModelForm):
    monto = forms.DecimalField(min_value=UN_CENTAVO, max_digits=12, decimal_places=2)

    class Meta:
        model = Pago
        fields = ["monto", "metodo", "referencia"]


class GastoForm(forms.ModelForm):
    monto = forms.DecimalField(min_value=UN_CENTAVO, max_digits=12, decimal_places=2)

    class Meta:
        model = Gasto
        fields = ["categoria", "concepto", "monto", "fecha", "referencia"]
        widgets = {"fecha": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}
