from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from inventario.models import AlertaReorden
from taller.roles import modulo_requerido
from taller.utils import ReglaNegocio, pagina_form

from . import services
from .forms import OrdenCompraForm, ProveedorForm, RecepcionForm, SolicitudManualForm
from .models import OrdenCompra, Proveedor, SolicitudMaterial


@modulo_requerido("proveedores")
def bandeja(request):
    """Compras: lo que almacén pidió y los productos que llegaron a su punto de reorden."""
    pendientes = SolicitudMaterial.objects.filter(estado=SolicitudMaterial.Estado.PENDIENTE).select_related(
        "producto__marca"
    )
    con_solicitud = SolicitudMaterial.objects.filter(referencia="Reorden", estado__in=services.ABIERTAS).values("producto")
    alertas = (
        AlertaReorden.objects.filter(estado=AlertaReorden.Estado.PENDIENTE)
        .exclude(producto__in=con_solicitud).select_related("producto__marca")
    )
    return render(
        request,
        "proveedores/bandeja.html",
        {"pendientes": pendientes, "alertas": alertas, "orden_form": OrdenCompraForm()},
    )


@modulo_requerido("proveedores")
def solicitud_manual(request):
    form = SolicitudManualForm(request.POST or None)
    if form.is_valid():
        _, creada = services.solicitar_material(usuario=request.user, **form.cleaned_data)
        if creada:
            messages.success(request, "Solicitud agregada.")
        else:
            messages.info(request, "Ya hay una solicitud abierta de ese producto con la misma referencia.")
        return redirect("proveedores:bandeja")
    return pagina_form(request, form, "Solicitud de material", reverse("proveedores:bandeja"), boton="Agregar")


@modulo_requerido("proveedores")
@require_POST
def desde_alerta(request, pk):
    alerta = get_object_or_404(AlertaReorden.objects.select_related("producto"), pk=pk)
    solicitud, _ = services.solicitar_desde_alerta(alerta, request.user)
    messages.success(request, f"Se solicitaron {solicitud.cantidad} de {alerta.producto.nombre}.")
    return redirect("proveedores:bandeja")


@modulo_requerido("proveedores")
@require_POST
def orden_crear(request):
    form = OrdenCompraForm(request.POST)
    ids = [i for i in request.POST.getlist("solicitudes") if i.isdigit()]
    solicitudes = list(SolicitudMaterial.objects.filter(pk__in=ids))
    if not form.is_valid() or not solicitudes:
        messages.error(request, "Elige un proveedor y al menos una solicitud.")
        return redirect("proveedores:bandeja")
    try:
        orden = services.crear_orden_compra(
            proveedor=form.cleaned_data["proveedor"], solicitudes=solicitudes, usuario=request.user
        )
    except ReglaNegocio as e:
        messages.error(request, str(e))
        return redirect("proveedores:bandeja")
    messages.success(request, f"Orden {orden.folio} creada.")
    return redirect("proveedores:orden_detalle", orden.pk)


@modulo_requerido("proveedores")
def ordenes(request):
    lista = OrdenCompra.objects.select_related("proveedor").prefetch_related("lineas")
    pagina = Paginator(lista, 25).get_page(request.GET.get("pagina"))
    return render(request, "proveedores/ordenes.html", {"pagina": pagina})


@modulo_requerido("proveedores")
def orden_detalle(request, pk):
    orden = get_object_or_404(OrdenCompra.objects.select_related("proveedor"), pk=pk)
    lineas = orden.lineas.select_related("producto")
    form = RecepcionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        cantidades = {}
        for linea in lineas:
            valor = request.POST.get(f"linea_{linea.pk}", "").strip()
            if valor:
                if not valor.isdigit():
                    messages.error(request, "Las cantidades deben ser números enteros.")
                    return redirect("proveedores:orden_detalle", orden.pk)
                cantidades[linea.pk] = int(valor)
        try:
            services.recibir_material(
                orden=orden, cantidades=cantidades, ubicacion=form.cleaned_data["ubicacion"], usuario=request.user
            )
            messages.success(request, "Material recibido: ya está en el inventario y el costo en contabilidad.")
        except ReglaNegocio as e:
            messages.error(request, str(e))
        return redirect("proveedores:orden_detalle", orden.pk)
    return render(
        request, "proveedores/orden_detalle.html",
        {"orden": orden, "lineas": lineas, "form": form, "abierta": orden.estado in ("ENVIADA", "PARCIAL")},
    )


@modulo_requerido("proveedores")
@require_POST
def orden_cancelar(request, pk):
    orden = get_object_or_404(OrdenCompra, pk=pk)
    try:
        services.cancelar_orden_compra(orden)
        messages.info(request, f"{orden.folio} cancelada; sus solicitudes regresaron a la bandeja.")
    except ReglaNegocio as e:
        messages.error(request, str(e))
    return redirect("proveedores:orden_detalle", orden.pk)


@modulo_requerido("proveedores")
def proveedores(request):
    return render(request, "proveedores/proveedores.html", {"proveedores": Proveedor.objects.all()})


@modulo_requerido("proveedores")
def proveedor_form(request, pk=None):
    proveedor = get_object_or_404(Proveedor, pk=pk) if pk else None
    form = ProveedorForm(request.POST or None, instance=proveedor)
    if form.is_valid():
        form.save()
        messages.success(request, "Proveedor guardado.")
        return redirect("proveedores:proveedores")
    titulo = f"Editar {proveedor}" if proveedor else "Nuevo proveedor"
    return pagina_form(request, form, titulo, reverse("proveedores:proveedores"))
