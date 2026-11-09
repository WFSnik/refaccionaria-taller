from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from mostrador.models import OrdenTrabajo
from taller.roles import modulo_requerido
from taller.utils import ReglaNegocio, pagina_form

from . import services
from .forms import CerrarIncidenteForm, EppForm, IncidenteForm, InspeccionForm, LiberacionForm, ProtocoloForm
from .models import EntregaEPP, Incidente, Protocolo


@modulo_requerido("sst")
def panel(request):
    return render(
        request,
        "sst/panel.html",
        {
            "por_liberar": OrdenTrabajo.objects.filter(estado=OrdenTrabajo.Estado.AUTORIZADA).select_related("vehiculo__cliente"),
            "protocolos": Protocolo.objects.filter(activo=True).prefetch_related("inspecciones"),
            "incidentes": Incidente.objects.filter(cerrado=False),
            "epp": EntregaEPP.objects.all()[:8],
        },
    )


@modulo_requerido("sst")
def liberar(request, orden_pk):
    orden = get_object_or_404(OrdenTrabajo.objects.select_related("vehiculo__cliente"), pk=orden_pk)
    form = LiberacionForm(request.POST or None)
    if form.is_valid():
        try:
            services.liberar_orden(
                orden=orden, confirmados=form.cleaned_data["confirmados"],
                notas=form.cleaned_data["notas"], usuario=request.user,
            )
            messages.success(request, f"{orden.folio} liberada: inicia la reparación y almacén ya puede entregar.")
            return redirect("mostrador:detalle", orden.pk)
        except ReglaNegocio as e:
            messages.error(request, str(e))
    return pagina_form(
        request, form, f"Liberar {orden.folio}", reverse("sst:panel"),
        descripcion=f"{orden.vehiculo}. Confirma cada protocolo antes de iniciar la reparación.",
        boton="Liberar orden",
    )


@modulo_requerido("sst")
def protocolo_form(request, pk=None):
    protocolo = get_object_or_404(Protocolo, pk=pk) if pk else None
    form = ProtocoloForm(request.POST or None, instance=protocolo)
    if form.is_valid():
        form.save()
        messages.success(request, "Protocolo guardado.")
        return redirect("sst:panel")
    return pagina_form(request, form, f"Editar {protocolo}" if protocolo else "Nuevo protocolo", reverse("sst:panel"))


@modulo_requerido("sst")
def inspeccion_crear(request, protocolo_pk):
    protocolo = get_object_or_404(Protocolo, pk=protocolo_pk)
    form = InspeccionForm(request.POST or None, initial={"fecha": timezone.localdate()})
    if form.is_valid():
        inspeccion = form.save(commit=False)
        inspeccion.protocolo = protocolo
        inspeccion.usuario = request.user
        inspeccion.save()
        messages.success(request, "Inspección registrada.")
        return redirect("sst:panel")
    return pagina_form(request, form, f"Inspección: {protocolo}", reverse("sst:panel"), descripcion=protocolo.norma)


@modulo_requerido("sst")
def incidente_crear(request):
    form = IncidenteForm(request.POST or None)
    if form.is_valid():
        incidente = form.save(commit=False)
        incidente.reportado_por = request.user
        incidente.save()
        messages.success(request, "Reporte registrado.")
        return redirect("sst:panel")
    return pagina_form(request, form, "Reportar riesgo o incidente", reverse("sst:panel"), boton="Registrar reporte")


@modulo_requerido("sst")
def incidente_cerrar(request, pk):
    incidente = get_object_or_404(Incidente, pk=pk, cerrado=False)
    form = CerrarIncidenteForm(request.POST or None)
    if form.is_valid():
        services.cerrar_incidente(incidente, form.cleaned_data["accion_correctiva"])
        messages.success(request, "Reporte cerrado.")
        return redirect("sst:panel")
    return pagina_form(
        request, form, f"Cerrar: {incidente}", reverse("sst:panel"), descripcion=incidente.descripcion, boton="Cerrar reporte"
    )


@modulo_requerido("sst")
def epp_crear(request):
    form = EppForm(request.POST or None, initial={"fecha": timezone.localdate()})
    if form.is_valid():
        services.entregar_epp(usuario=request.user, **form.cleaned_data)
        messages.success(request, "Entrega de EPP registrada; su costo ya está en contabilidad.")
        return redirect("sst:panel")
    return pagina_form(request, form, "Entrega de equipo de protección", reverse("sst:panel"), boton="Registrar entrega")
