from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from mostrador.models import OrdenTrabajo
from taller.roles import modulo_requerido
from taller.utils import ReglaNegocio

from . import services
from .forms import DecisionForm, DiagnosticoForm, RefaccionForm, ServicioForm
from .models import LineaPresupuesto

E = OrdenTrabajo.Estado


@modulo_requerido("ventas")
def bandeja(request):
    ordenes = OrdenTrabajo.objects.select_related("vehiculo__cliente").order_by("creada")
    return render(
        request,
        "ventas/bandeja.html",
        {
            "por_diagnosticar": ordenes.filter(estado=E.RECIBIDA),
            "por_autorizar": ordenes.filter(estado=E.PRESUPUESTADA),
            "en_curso": ordenes.filter(estado__in=[E.AUTORIZADA, E.EN_REPARACION]),
        },
    )


def _pantalla(request, orden, presupuesto, **forms):
    contexto = {
        "orden": orden,
        "presupuesto": presupuesto,
        "lineas": presupuesto.lineas.select_related("producto"),
        "montos": presupuesto.montos(),
        "diagnostico_form": forms.get("diagnostico_form") or DiagnosticoForm(instance=presupuesto),
        "refaccion_form": forms.get("refaccion_form") or RefaccionForm(),
        "servicio_form": forms.get("servicio_form") or ServicioForm(),
        "decision_form": forms.get("decision_form") or DecisionForm(initial={"autorizado_por": orden.cliente.nombre}),
    }
    return render(request, "ventas/presupuesto.html", contexto)


@modulo_requerido("ventas")
def presupuesto(request, orden_pk):
    orden = get_object_or_404(OrdenTrabajo.objects.select_related("vehiculo__cliente"), pk=orden_pk)
    if orden.estado not in (E.RECIBIDA, E.PRESUPUESTADA) and not hasattr(orden, "presupuesto"):
        messages.error(request, f"{orden.folio} no tiene presupuesto.")
        return redirect("mostrador:detalle", orden.pk)
    p = services.obtener_presupuesto(orden, request.user)
    if request.method != "POST":
        return _pantalla(request, orden, p)

    accion = request.POST.get("accion")
    try:
        if accion == "diagnostico":
            form = DiagnosticoForm(request.POST, instance=p)
            if not p.editable:
                raise ReglaNegocio("El presupuesto ya se envió: regrésalo a edición para cambiarlo.")
            if not form.is_valid():
                return _pantalla(request, orden, p, diagnostico_form=form)
            form.save()
            messages.success(request, "Diagnóstico guardado.")
        elif accion == "refaccion":
            form = RefaccionForm(request.POST)
            if not form.is_valid():
                return _pantalla(request, orden, p, refaccion_form=form)
            services.agregar_refaccion(p, form.cleaned_data["producto"], form.cleaned_data["cantidad"])
        elif accion == "servicio":
            form = ServicioForm(request.POST)
            if not form.is_valid():
                return _pantalla(request, orden, p, servicio_form=form)
            services.agregar_servicio(p, **form.cleaned_data)
        elif accion == "enviar":
            services.enviar_presupuesto(p, request.user)
            messages.success(request, "Presupuesto enviado. Falta la decisión del cliente.")
        elif accion == "editar":
            services.regresar_a_edicion(p, request.user)
        elif accion in ("autorizar", "rechazar"):
            form = DecisionForm(request.POST)
            if not form.is_valid():
                return _pantalla(request, orden, p, decision_form=form)
            if accion == "autorizar":
                services.autorizar(p, request.user, **form.cleaned_data)
                messages.success(request, "Reparación autorizada. Se generaron las solicitudes de piezas al almacén.")
                return redirect("mostrador:detalle", orden.pk)
            services.rechazar(p, request.user, **form.cleaned_data)
            messages.info(request, "Presupuesto rechazado; la orden queda cerrada.")
            return redirect("mostrador:detalle", orden.pk)
    except ReglaNegocio as e:
        messages.error(request, str(e))
    return redirect("ventas:presupuesto", orden.pk)


@modulo_requerido("ventas")
@require_POST
def quitar_linea(request, pk):
    linea = get_object_or_404(LineaPresupuesto.objects.select_related("presupuesto__orden"), pk=pk)
    try:
        services.quitar_linea(linea)
    except ReglaNegocio as e:
        messages.error(request, str(e))
    return redirect("ventas:presupuesto", linea.presupuesto.orden_id)


@modulo_requerido("ventas")
@require_POST
def cancelar(request, orden_pk):
    orden = get_object_or_404(OrdenTrabajo, pk=orden_pk)
    try:
        services.cancelar_orden(orden, request.user)
        messages.info(request, f"{orden.folio} cancelada.")
    except ReglaNegocio as e:
        messages.error(request, str(e))
    return redirect("mostrador:detalle", orden.pk)


@modulo_requerido("terminar")
@require_POST
def terminar(request, orden_pk):
    orden = get_object_or_404(OrdenTrabajo, pk=orden_pk)
    try:
        services.terminar_orden(orden, request.user)
        messages.success(request, f"{orden.folio} terminada. Pasa a contabilidad para facturar.")
    except ReglaNegocio as e:
        messages.error(request, str(e))
    return redirect("mostrador:detalle", orden.pk)
