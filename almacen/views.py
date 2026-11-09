from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from inventario.models import Producto
from inventario.services import StockInsuficiente
from mostrador.models import OrdenTrabajo
from taller.roles import modulo_requerido
from taller.utils import ReglaNegocio, pagina_form

from . import services
from .forms import EntregaForm, HerramientaForm, PrestamoForm
from .models import EntregaMaterial, Herramienta, PrestamoHerramienta, SolicitudPieza


@modulo_requerido("almacen")
def bandeja(request):
    pendientes = SolicitudPieza.objects.pendientes().select_related("orden__vehiculo", "producto")
    for s in pendientes:
        s.stock = s.producto.stock_total()
        s.alcanza = s.stock >= s.pendiente
    en_reparacion = OrdenTrabajo.Estado.EN_REPARACION
    return render(
        request,
        "almacen/bandeja.html",
        {
            "listas": [s for s in pendientes if s.orden.estado == en_reparacion],
            "por_liberar": [s for s in pendientes if s.orden.estado != en_reparacion],
            "entregas": EntregaMaterial.objects.select_related(
                "solicitud__orden", "solicitud__producto", "movimiento__ubicacion"
            )[:10],
        },
    )


@modulo_requerido("almacen")
def existencias(request):
    q = request.GET.get("q", "").strip()
    productos = Producto.objects.none()
    if q:
        productos = (
            Producto.objects.filter(activo=True)
            .filter(Q(nombre__icontains=q) | Q(codigo__icontains=q) | Q(numero_parte__icontains=q) | Q(codigo_barras=q))
            .con_stock().select_related("marca").prefetch_related("existencias__ubicacion")[:30]
        )
    return render(request, "almacen/existencias.html", {"q": q, "productos": productos})


@modulo_requerido("almacen")
def entregar(request, pk):
    solicitud = get_object_or_404(SolicitudPieza.objects.select_related("orden__vehiculo", "producto"), pk=pk)
    form = EntregaForm(request.POST or None, solicitud=solicitud)
    if form.is_valid():
        try:
            services.entregar_pieza(solicitud=solicitud, usuario=request.user, **form.cleaned_data)
            messages.success(request, f"Entrega registrada en {solicitud.orden.folio}; el stock ya se descontó.")
            return redirect("almacen:bandeja")
        except ReglaNegocio as e:
            messages.error(request, str(e))
        except StockInsuficiente as e:
            form.add_error("cantidad", str(e))
    return pagina_form(
        request, form, f"Entregar {solicitud.producto.nombre}", reverse("almacen:bandeja"),
        descripcion=f"{solicitud.orden.folio} · faltan {solicitud.pendiente} de {solicitud.cantidad}.",
        boton="Registrar entrega",
    )


@modulo_requerido("almacen")
@require_POST
def cancelar_pendiente(request, pk):
    solicitud = get_object_or_404(SolicitudPieza.objects.select_related("orden"), pk=pk)
    try:
        services.cancelar_pendiente(solicitud)
        messages.info(request, "Se canceló lo que faltaba por entregar.")
    except ReglaNegocio as e:
        messages.error(request, str(e))
    return redirect("almacen:bandeja")


@modulo_requerido("almacen")
@require_POST
def pedir_faltante(request, pk):
    solicitud = get_object_or_404(SolicitudPieza.objects.select_related("orden", "producto"), pk=pk)
    try:
        material, creada = services.pedir_faltante(solicitud, request.user)
        if creada:
            messages.success(request, f"Se pidieron {material.cantidad} a compras.")
        else:
            messages.info(request, "Compras ya tiene esta solicitud abierta.")
    except ReglaNegocio as e:
        messages.error(request, str(e))
    return redirect("almacen:bandeja")


@modulo_requerido("almacen")
def herramientas(request):
    form = HerramientaForm(request.POST or None)
    if form.is_valid():
        form.save()
        messages.success(request, "Herramienta registrada.")
        return redirect("almacen:herramientas")
    lista = Herramienta.objects.filter(activa=True).prefetch_related("prestamos__orden")
    return render(request, "almacen/herramientas.html", {"form": form, "herramientas": lista})


@modulo_requerido("almacen")
def prestar(request, pk):
    herramienta = get_object_or_404(Herramienta, pk=pk, activa=True)
    form = PrestamoForm(request.POST or None)
    if form.is_valid():
        try:
            services.prestar_herramienta(
                herramienta=herramienta, usuario=request.user,
                mecanico=form.cleaned_data["mecanico"], orden=form.cleaned_data["orden"],
            )
            messages.success(request, f"{herramienta.nombre} prestada a {form.cleaned_data['mecanico']}.")
        except ReglaNegocio as e:
            messages.error(request, str(e))
        return redirect("almacen:herramientas")
    return pagina_form(request, form, f"Prestar {herramienta.nombre}", reverse("almacen:herramientas"), boton="Prestar")


@modulo_requerido("almacen")
@require_POST
def devolver(request, pk):
    prestamo = get_object_or_404(PrestamoHerramienta, pk=pk, devuelta__isnull=True)
    services.devolver_herramienta(prestamo)
    messages.success(request, "Herramienta devuelta.")
    return redirect("almacen:herramientas")
