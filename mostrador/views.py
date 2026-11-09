from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from taller.roles import modulo_requerido
from taller.utils import ReglaNegocio, pagina_form

from .forms import OrdenForm
from .models import OrdenTrabajo
from .services import emitir_orden, entregar_vehiculo


@modulo_requerido("ordenes")
def lista(request):
    q = request.GET.get("q", "").strip()
    estado = request.GET.get("estado", "abiertas")
    ordenes = OrdenTrabajo.objects.select_related("vehiculo__cliente")
    if estado == "abiertas":
        ordenes = ordenes.filter(estado__in=OrdenTrabajo.ABIERTOS)
    elif estado in OrdenTrabajo.Estado.values:
        ordenes = ordenes.filter(estado=estado)
    if q:
        filtro = (
            Q(vehiculo__cliente__nombre__icontains=q)
            | Q(vehiculo__placas__icontains=q)
            | Q(vehiculo__modelo__icontains=q)
        )
        numero = q.upper().removeprefix("OT-")
        if numero.isdigit():
            filtro |= Q(pk=int(numero))
        ordenes = ordenes.filter(filtro)
    pagina = Paginator(ordenes, 25).get_page(request.GET.get("pagina"))
    filtros = request.GET.copy()
    filtros.pop("pagina", None)
    return render(
        request,
        "mostrador/lista.html",
        {"pagina": pagina, "q": q, "estado": estado, "estados": OrdenTrabajo.Estado.choices, "filtros": filtros.urlencode()},
    )


@modulo_requerido("mostrador")
def crear(request):
    inicial = {}
    if request.GET.get("vehiculo", "").isdigit():
        inicial["vehiculo"] = request.GET["vehiculo"]
    form = OrdenForm(request.POST or None, initial=inicial)
    if form.is_valid():
        orden = emitir_orden(
            vehiculo=form.cleaned_data["vehiculo"],
            sintomas=form.cleaned_data["sintomas"],
            kilometraje=form.cleaned_data["kilometraje"],
            usuario=request.user,
        )
        messages.success(request, f"Orden {orden.folio} emitida. Pasa a ventas para diagnóstico y presupuesto.")
        return redirect("mostrador:detalle", orden.pk)
    return pagina_form(
        request, form, "Recepción de vehículo", reverse("mostrador:lista"),
        descripcion="¿El cliente es nuevo? Regístralo primero en Clientes.", boton="Emitir orden de trabajo",
    )


@modulo_requerido("ordenes")
def detalle(request, pk):
    orden = get_object_or_404(OrdenTrabajo.objects.select_related("vehiculo__cliente", "creada_por"), pk=pk)
    return render(
        request,
        "mostrador/detalle.html",
        {
            "orden": orden,
            "presupuesto": getattr(orden, "presupuesto", None),
            "solicitudes": orden.solicitudes.select_related("producto"),
            "facturas": orden.facturas.all(),
            "factura_vigente": orden.facturas.exclude(estado="CANCELADA").first(),
            "historial": orden.historial.select_related("usuario"),
        },
    )


@modulo_requerido("mostrador")
@require_POST
def entregar(request, pk):
    orden = get_object_or_404(OrdenTrabajo, pk=pk)
    try:
        entregar_vehiculo(orden, request.user)
        messages.success(request, f"{orden.folio} entregada al cliente.")
    except ReglaNegocio as e:
        messages.error(request, str(e))
    return redirect("mostrador:detalle", orden.pk)
