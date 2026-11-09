from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from mostrador.models import OrdenTrabajo
from taller.roles import modulo_requerido
from taller.utils import ReglaNegocio, pagina_form

from . import services
from .forms import GastoForm, PagoForm
from .models import Factura, Gasto, Pago


@modulo_requerido("contabilidad")
def resumen(request):
    hoy = timezone.localdate()
    pagos_mes = Pago.objects.filter(fecha__year=hoy.year, fecha__month=hoy.month)
    gastos_mes = Gasto.objects.filter(fecha__year=hoy.year, fecha__month=hoy.month)
    ingresos = pagos_mes.aggregate(s=Sum("monto"))["s"] or 0
    gastos = gastos_mes.aggregate(s=Sum("monto"))["s"] or 0
    por_cobrar = Factura.objects.filter(estado=Factura.Estado.EMITIDA).prefetch_related("pagos")
    return render(
        request,
        "contabilidad/resumen.html",
        {
            "ingresos": ingresos,
            "gastos": gastos,
            "resultado": ingresos - gastos,
            "por_cobrar": por_cobrar,
            "saldo_por_cobrar": sum(f.saldo for f in por_cobrar),
            "por_facturar": OrdenTrabajo.objects.filter(estado=OrdenTrabajo.Estado.TERMINADA).select_related("vehiculo__cliente"),
            "gastos_categoria": gastos_mes.values("categoria").annotate(s=Sum("monto")).order_by("-s"),
            "etiquetas": dict(Gasto.Categoria.choices),
        },
    )


@modulo_requerido("contabilidad")
@require_POST
def emitir(request, orden_pk):
    orden = get_object_or_404(OrdenTrabajo.objects.select_related("vehiculo__cliente"), pk=orden_pk)
    try:
        factura = services.emitir_factura(orden, request.user)
    except ReglaNegocio as e:
        messages.error(request, str(e))
        return redirect("mostrador:detalle", orden.pk)
    messages.success(request, f"Factura {factura.folio} emitida.")
    return redirect("contabilidad:factura", factura.pk)


@modulo_requerido("contabilidad")
def facturas(request):
    pagina = Paginator(Factura.objects.all(), 25).get_page(request.GET.get("pagina"))
    return render(request, "contabilidad/facturas.html", {"pagina": pagina})


@modulo_requerido("contabilidad")
def factura(request, pk):
    f = get_object_or_404(Factura.objects.select_related("orden__vehiculo"), pk=pk)
    form = PagoForm(request.POST or None, initial={"monto": f.saldo})
    if form.is_valid():
        try:
            services.registrar_pago(factura=f, usuario=request.user, **form.cleaned_data)
            messages.success(request, "Pago registrado.")
        except ReglaNegocio as e:
            messages.error(request, str(e))
        return redirect("contabilidad:factura", f.pk)
    return render(request, "contabilidad/factura.html", {"factura": f, "form": form})


@modulo_requerido("contabilidad")
def imprimir(request, pk):
    f = get_object_or_404(Factura.objects.select_related("orden__vehiculo"), pk=pk)
    return render(request, "contabilidad/imprimir.html", {"factura": f})


@modulo_requerido("contabilidad")
@require_POST
def cancelar(request, pk):
    f = get_object_or_404(Factura, pk=pk)
    try:
        services.cancelar_factura(f, request.user)
        messages.info(request, f"{f.folio} cancelada; la orden regresó a terminada.")
    except ReglaNegocio as e:
        messages.error(request, str(e))
    return redirect("contabilidad:factura", f.pk)


@modulo_requerido("contabilidad")
def gastos(request):
    pagina = Paginator(Gasto.objects.all(), 25).get_page(request.GET.get("pagina"))
    return render(request, "contabilidad/gastos.html", {"pagina": pagina})


@modulo_requerido("contabilidad")
def gasto_crear(request):
    form = GastoForm(request.POST or None, initial={"fecha": timezone.localdate()})
    if form.is_valid():
        gasto = form.save(commit=False)
        gasto.usuario = request.user
        gasto.save()
        messages.success(request, "Gasto registrado.")
        return redirect("contabilidad:gastos")
    return pagina_form(request, form, "Nuevo gasto", reverse("contabilidad:gastos"))
