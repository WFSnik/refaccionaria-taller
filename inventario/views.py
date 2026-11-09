from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Case, Count, DecimalField, F, IntegerField, Prefetch, Q, Sum, Value, When
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import MovimientoForm, ProductoEditarForm, ProductoForm, UbicacionForm
from .models import AlertaReorden, Categoria, Existencia, Movimiento, Producto, Ubicacion
from .services import StockInsuficiente, contexto_correo, registrar_alta, registrar_baja


@login_required
def dashboard(request):
    activos = Producto.objects.filter(activo=True)
    existencias = Existencia.objects.filter(producto__activo=True)
    totales = existencias.aggregate(
        unidades=Coalesce(Sum("cantidad"), 0),
        valor=Coalesce(Sum(F("cantidad") * F("producto__costo"), output_field=DecimalField()), Value(0, DecimalField())),
    )
    hoy = timezone.localdate()
    movs_hoy = Movimiento.objects.filter(fecha__date=hoy).aggregate(
        altas=Count("id", filter=Q(tipo=Movimiento.Tipo.ALTA)),
        bajas=Count("id", filter=Q(tipo=Movimiento.Tipo.BAJA)),
    )
    categorias = Categoria.objects.annotate(
        productos_n=Count("productos", filter=Q(productos__activo=True), distinct=True),
        unidades=Coalesce(Sum("productos__existencias__cantidad", filter=Q(productos__activo=True)), 0),
    ).filter(productos_n__gt=0)
    max_unidades = max((c.unidades for c in categorias), default=0) or 1
    for c in categorias:
        c.pct = round(c.unidades / max_unidades * 100, 1)

    return render(
        request,
        "inventario/dashboard.html",
        {
            "productos_n": activos.count(),
            "unidades": totales["unidades"],
            "valor": totales["valor"],
            "movs_hoy": movs_hoy,
            "por_reordenar": activos.con_stock().filter(stock__lte=F("punto_reorden")).select_related("marca")
            .order_by("stock", "nombre")[:6],
            "ultimos": Movimiento.objects.select_related("producto", "ubicacion", "usuario")[:8],
            "categorias": categorias,
        },
    )


@login_required
def productos_lista(request):
    q = request.GET.get("q", "").strip()
    categoria = request.GET.get("categoria", "")
    estado = request.GET.get("estado", "")

    productos = (
        Producto.objects.filter(activo=True).con_stock().select_related("marca", "categoria").order_by("nombre", "codigo")
    )
    if q:
        productos = productos.filter(
            Q(codigo__icontains=q)
            | Q(codigo_barras=q)
            | Q(numero_parte__icontains=q)
            | Q(nombre__icontains=q)
            | Q(marca__nombre__icontains=q)
            | Q(especificacion__icontains=q)
        )
    if categoria.isdigit():
        productos = productos.filter(categoria_id=int(categoria))
    if estado == "agotado":
        productos = productos.filter(stock=0)
    elif estado == "bajo":
        productos = productos.filter(stock__gt=0, stock__lte=F("punto_reorden"))
    elif estado == "ok":
        productos = productos.filter(stock__gt=F("punto_reorden"))

    pagina = Paginator(productos, 25).get_page(request.GET.get("pagina"))
    filtros = request.GET.copy()
    filtros.pop("pagina", None)
    return render(
        request,
        "inventario/productos_lista.html",
        {
            "pagina": pagina,
            "q": q,
            "categoria": categoria,
            "estado": estado,
            "categorias": Categoria.objects.all(),
            "filtros": filtros.urlencode(),
        },
    )


@login_required
def producto_detalle(request, pk):
    producto = get_object_or_404(Producto.objects.select_related("marca", "categoria"), pk=pk)
    return render(
        request,
        "inventario/producto_detalle.html",
        {
            "producto": producto,
            "stock": producto.stock_total(),
            "existencias": producto.existencias.filter(cantidad__gt=0).select_related("ubicacion"),
            "movimientos": producto.movimientos.select_related("ubicacion", "usuario")[:30],
            "alerta": producto.alertas.filter(estado=AlertaReorden.Estado.PENDIENTE).first(),
        },
    )


@login_required
def producto_crear(request):
    form = ProductoForm(request.POST or None, initial={"codigo": request.GET.get("codigo", "")})
    if form.is_valid():
        producto = form.save()
        messages.success(request, f"Producto {producto.codigo} registrado. Dale entrada para asignarle ubicación.")
        return redirect("producto_detalle", pk=producto.pk)
    return render(request, "inventario/producto_form.html", {"form": form})


@login_required
def producto_editar(request, pk):
    producto = get_object_or_404(Producto, pk=pk)
    form = ProductoEditarForm(request.POST or None, instance=producto)
    if form.is_valid():
        form.save()
        messages.success(request, "Cambios guardados.")
        return redirect("producto_detalle", pk=producto.pk)
    return render(request, "inventario/producto_form.html", {"form": form, "producto": producto})


def _serializar(producto):
    return {
        "id": producto.pk,
        "codigo": producto.codigo,
        "codigo_barras": producto.codigo_barras or "",
        "nombre": producto.nombre,
        "marca": str(producto.marca),
        "categoria": str(producto.categoria),
        "presentacion": producto.presentacion,
        "especificacion": producto.especificacion,
        "punto_reorden": producto.punto_reorden,
        "stock": sum(e.cantidad for e in producto.existencias.all()),
        "existencias": [
            {"ubicacion": e.ubicacion_id, "codigo": e.ubicacion.codigo, "cantidad": e.cantidad}
            for e in producto.existencias.all()
            if e.cantidad > 0
        ],
    }


@login_required
def api_productos(request):
    q = request.GET.get("q", "").strip()
    if not q:
        return JsonResponse({"resultados": []})
    exacto = Q(codigo__iexact=q) | Q(codigo_barras=q) | Q(numero_parte__iexact=q)
    productos = (
        Producto.objects.filter(activo=True)
        .filter(
            exacto
            | Q(codigo__icontains=q)
            | Q(nombre__icontains=q)
            | Q(marca__nombre__icontains=q)
            | Q(especificacion__icontains=q)
        )
        .annotate(prioridad=Case(When(exacto, then=0), default=1, output_field=IntegerField()))
        .select_related("marca", "categoria")
        .prefetch_related(Prefetch("existencias", queryset=Existencia.objects.select_related("ubicacion")))
        .order_by("prioridad", "nombre")[:8]
    )
    return JsonResponse({"resultados": [_serializar(p) for p in productos]})


@login_required
def movimiento_nuevo(request):
    form = MovimientoForm(request.POST or None, initial={"tipo": request.GET.get("tipo", "")})
    nuevo = ProductoForm(request.POST or None, prefix="nuevo")
    crear = request.method == "POST" and request.POST.get("crear_producto") == "1"

    if request.method == "POST":
        validos = form.is_valid()
        if validos and form.cleaned_data["tipo"] != Movimiento.Tipo.ALTA:
            crear = False
        if crear:
            validos = nuevo.is_valid() and validos
        elif validos and not form.cleaned_data["producto"]:
            form.add_error(None, "Selecciona un producto.")
            validos = False

        if validos:
            d = form.cleaned_data
            datos = {
                "ubicacion": d["ubicacion"],
                "cantidad": d["cantidad"],
                "motivo": d["motivo"],
                "referencia": d["referencia"],
                "notas": d["notas"],
                "usuario": request.user,
            }
            try:
                if d["tipo"] == Movimiento.Tipo.ALTA:
                    with transaction.atomic():
                        producto = nuevo.save() if crear else d["producto"]
                        movimiento, alerta = registrar_alta(producto=producto, **datos)
                else:
                    movimiento, alerta = registrar_baja(producto=d["producto"], **datos)
            except StockInsuficiente as e:
                form.add_error("cantidad", str(e))
                if e.alerta:
                    messages.warning(request, "No hay stock suficiente: se generó una alerta de reorden para compras.")
            else:
                verbo = "Entrada" if movimiento.tipo == Movimiento.Tipo.ALTA else "Salida"
                messages.success(
                    request,
                    f"{verbo} registrada: {movimiento.cantidad} × {movimiento.producto.nombre} "
                    f"en {movimiento.ubicacion}. Stock actual: {movimiento.stock_resultante}.",
                )
                if alerta:
                    messages.warning(request, "El producto llegó a su punto de reorden y se avisó a compras.")
                return redirect("producto_detalle", pk=movimiento.producto_id)

    # Estado con el que arranca el asistente: al volver con errores o al llegar
    # desde la ficha de un producto (?tipo=ALTA&producto=ID).
    seleccionado = None
    pid = request.GET.get("producto") if not form.is_bound else (None if crear else form.data.get("producto"))
    if pid and str(pid).isdigit():
        p = (
            Producto.objects.filter(pk=pid, activo=True)
            .select_related("marca", "categoria")
            .prefetch_related(Prefetch("existencias", queryset=Existencia.objects.select_related("ubicacion")))
            .first()
        )
        seleccionado = _serializar(p) if p else None

    tipo = form.data.get("tipo") if form.is_bound else request.GET.get("tipo")
    tipo = tipo if tipo in Movimiento.Tipo.values else ""
    if form.is_bound:
        paso = 2 if (crear and nuevo.errors) or not (seleccionado or crear) else 3
    else:
        paso = 3 if seleccionado else 2

    return render(
        request,
        "inventario/movimiento_nuevo.html",
        {
            "form": form,
            "nuevo": nuevo,
            "crear": crear,
            "ubicaciones": Ubicacion.objects.filter(activa=True),
            "estado_inicial": {
                "tipo": tipo,
                "seleccionado": seleccionado,
                "crear": crear,
                "paso": paso,
                "motivo": form.data.get("motivo", "") if form.is_bound else "",
                "api": reverse("api_productos"),
                "motivos": {
                    "ALTA": [[m.value, m.label] for m in Movimiento.MOTIVOS_ALTA],
                    "BAJA": [[m.value, m.label] for m in Movimiento.MOTIVOS_BAJA],
                },
            },
        },
    )


@login_required
def movimientos_lista(request):
    q = request.GET.get("q", "").strip()
    tipo = request.GET.get("tipo", "")
    movimientos = Movimiento.objects.select_related("producto", "ubicacion", "usuario")
    if q:
        movimientos = movimientos.filter(
            Q(producto__codigo__icontains=q) | Q(producto__nombre__icontains=q) | Q(referencia__icontains=q)
        )
    if tipo in Movimiento.Tipo.values:
        movimientos = movimientos.filter(tipo=tipo)
    pagina = Paginator(movimientos, 30).get_page(request.GET.get("pagina"))
    filtros = request.GET.copy()
    filtros.pop("pagina", None)
    return render(
        request,
        "inventario/movimientos_lista.html",
        {"pagina": pagina, "q": q, "tipo": tipo, "filtros": filtros.urlencode()},
    )


@login_required
def ubicaciones(request):
    form = UbicacionForm(request.POST or None)
    if form.is_valid():
        ubicacion = form.save()
        messages.success(request, f"Ubicación {ubicacion.codigo} agregada.")
        return redirect("ubicaciones")
    lista = (
        Ubicacion.objects.filter(activa=True)
        .annotate(
            productos_n=Count("existencias", filter=Q(existencias__cantidad__gt=0)),
            unidades=Coalesce(Sum("existencias__cantidad"), 0),
        )
        .prefetch_related(
            Prefetch(
                "existencias",
                queryset=Existencia.objects.filter(cantidad__gt=0).select_related("producto").order_by("producto__nombre"),
                to_attr="contenido",
            )
        )
        .order_by("codigo")
    )
    return render(request, "inventario/ubicaciones.html", {"ubicaciones": lista, "form": form})


@login_required
def alertas(request):
    base = AlertaReorden.objects.select_related("producto__marca", "atendida_por")
    pendientes = list(base.filter(estado=AlertaReorden.Estado.PENDIENTE))
    stock = dict(
        Producto.objects.filter(pk__in=[a.producto_id for a in pendientes]).con_stock().values_list("pk", "stock")
    )
    for a in pendientes:
        a.stock_actual = stock.get(a.producto_id, 0)
    return render(
        request,
        "inventario/alertas.html",
        {"pendientes": pendientes, "atendidas": base.filter(estado=AlertaReorden.Estado.ATENDIDA)[:20]},
    )


@login_required
def alerta_correo(request, pk):
    """Muestra el correo que recibe compras para esta alerta."""
    alerta = get_object_or_404(AlertaReorden.objects.select_related("producto__marca", "producto__categoria"), pk=pk)
    return render(request, "correo/alerta_reorden.html", contexto_correo(alerta))


@login_required
@require_POST
def alerta_atender(request, pk):
    alerta = get_object_or_404(AlertaReorden, pk=pk, estado=AlertaReorden.Estado.PENDIENTE)
    alerta.estado = AlertaReorden.Estado.ATENDIDA
    alerta.atendida_en = timezone.now()
    alerta.atendida_por = request.user
    alerta.save(update_fields=["estado", "atendida_en", "atendida_por"])
    messages.success(request, f"Alerta de {alerta.producto.codigo} marcada como atendida.")
    return redirect("alertas")
