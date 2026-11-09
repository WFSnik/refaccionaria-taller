"""Auditorías de inventario: conteo físico por ubicación y ajustes por las diferencias."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from taller.utils import ReglaNegocio

from .models import Auditoria, Existencia, LineaAuditoria, Movimiento, Ubicacion
from .services import StockInsuficiente, registrar_alta, registrar_baja


def abrir_auditoria(ubicacion, usuario):
    try:
        with transaction.atomic():
            auditoria = Auditoria.objects.create(ubicacion=ubicacion, usuario=usuario)
    except IntegrityError:
        raise ReglaNegocio(f"{ubicacion} ya tiene una auditoría abierta.") from None
    existencias = Existencia.objects.filter(ubicacion=ubicacion, cantidad__gt=0)
    LineaAuditoria.objects.bulk_create(
        LineaAuditoria(auditoria=auditoria, producto_id=e.producto_id, esperado=e.cantidad) for e in existencias
    )
    return auditoria


def cerrar_auditoria(auditoria, usuario):
    """Ajusta el stock por cada diferencia. Regresa los productos que no se pudieron ajustar."""
    fallidos = []
    with transaction.atomic():
        auditoria = Auditoria.objects.select_for_update().get(pk=auditoria.pk)
        if not auditoria.abierta:
            raise ReglaNegocio("Esta auditoría ya se cerró.")
        for linea in auditoria.lineas.select_related("producto"):
            diferencia = linea.diferencia
            if not diferencia:
                continue
            datos = {
                "producto": linea.producto, "ubicacion": auditoria.ubicacion, "cantidad": abs(diferencia),
                "motivo": Movimiento.Motivo.AJUSTE, "usuario": usuario, "referencia": auditoria.folio,
                "notas": linea.nota,
            }
            try:
                (registrar_alta if diferencia > 0 else registrar_baja)(**datos)
            except StockInsuficiente:
                # Hubo salidas después de abrir la auditoría y ya no hay de dónde descontar.
                fallidos.append(linea.producto.nombre)
        auditoria.abierta = False
        auditoria.cerrada_en = timezone.now()
        auditoria.save(update_fields=["abierta", "cerrada_en"])
    return fallidos


@login_required
def lista(request):
    if request.method == "POST":
        ubicacion = get_object_or_404(Ubicacion, pk=request.POST.get("ubicacion") or 0, activa=True)
        try:
            auditoria = abrir_auditoria(ubicacion, request.user)
            return redirect("auditoria_detalle", auditoria.pk)
        except ReglaNegocio as e:
            messages.error(request, str(e))
            return redirect("auditorias")
    return render(
        request,
        "inventario/auditorias.html",
        {
            "auditorias": Auditoria.objects.select_related("ubicacion", "usuario")[:50],
            "ubicaciones": Ubicacion.objects.filter(activa=True),
        },
    )


@login_required
def detalle(request, pk):
    auditoria = get_object_or_404(Auditoria.objects.select_related("ubicacion", "usuario"), pk=pk)
    lineas = list(auditoria.lineas.select_related("producto"))
    if request.method == "POST" and auditoria.abierta:
        for linea in lineas:
            valor = request.POST.get(f"contado_{linea.pk}", "").strip()
            if valor and not valor.isdigit():
                messages.error(request, f"Revisa el conteo de {linea.producto.nombre}: debe ser un número entero.")
                return redirect("auditoria_detalle", auditoria.pk)
            linea.contado = int(valor) if valor else None
            linea.nota = request.POST.get(f"nota_{linea.pk}", "").strip()[:200]
        LineaAuditoria.objects.bulk_update(lineas, ["contado", "nota"])
        if request.POST.get("accion") != "cerrar":
            messages.success(request, "Conteo guardado.")
            return redirect("auditoria_detalle", auditoria.pk)
        try:
            fallidos = cerrar_auditoria(auditoria, request.user)
        except ReglaNegocio as e:
            messages.error(request, str(e))
            return redirect("auditoria_detalle", auditoria.pk)
        if fallidos:
            messages.error(request, "No se pudieron ajustar por falta de stock: " + ", ".join(fallidos) + ".")
        else:
            messages.success(request, "Auditoría cerrada; las diferencias quedaron como ajustes.")
        return redirect("auditoria_detalle", auditoria.pk)
    return render(request, "inventario/auditoria_detalle.html", {"auditoria": auditoria, "lineas": lineas})

