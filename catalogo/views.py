from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import ConsultaPendiente, Vehiculo
from .services import buscar_numero, buscar_vehiculos, piezas_para, registrar_pendiente


def _entero(valor):
    return int(valor) if (valor or "").isdigit() else None


@login_required
def vehiculos(request):
    q = request.GET.get("q", "").strip()
    marca = request.GET.get("marca", "")
    modelo = request.GET.get("modelo", "")
    anio = _entero(request.GET.get("anio"))
    vehiculo = None
    encontrados = []

    if _entero(request.GET.get("v")):
        vehiculo = get_object_or_404(Vehiculo, pk=request.GET["v"])
    elif q or modelo:
        encontrados = list(buscar_vehiculos(q, marca=marca, modelo=modelo, anio=anio))
        if len(encontrados) == 1:
            vehiculo = encontrados[0]
        elif not encontrados and q:
            registrar_pendiente(q, ConsultaPendiente.Canal.MOSTRADOR)

    return render(
        request,
        "catalogo/vehiculos.html",
        {
            "q": q,
            "marca": marca,
            "modelo": modelo,
            "anio": anio or "",
            "buscado": bool(q or modelo),
            "marcas": Vehiculo.objects.order_by("marca").values_list("marca", flat=True).distinct(),
            "encontrados": encontrados,
            "vehiculo": vehiculo,
            "grupos": piezas_para(vehiculo) if vehiculo else [],
        },
    )


@login_required
def opciones(request):
    """Opciones de los selectores encadenados marca → modelo → año."""
    marca = request.GET.get("marca", "")
    modelo = request.GET.get("modelo", "")
    datos = {}
    if marca:
        datos["modelos"] = list(
            Vehiculo.objects.filter(marca=marca).order_by("modelo").values_list("modelo", flat=True).distinct()
        )
    if marca and modelo:
        rangos = Vehiculo.objects.filter(marca=marca, modelo=modelo).values_list("anio_inicio", "anio_fin")
        datos["anios"] = sorted({a for i, f in rangos for a in range(i, f + 1)}, reverse=True)
    return JsonResponse(datos)


@login_required
def numero(request):
    n = request.GET.get("n", "").strip()
    resultado = buscar_numero(n) if n else None
    if n and not resultado:
        registrar_pendiente(f"Número {n}", ConsultaPendiente.Canal.MOSTRADOR)
    return render(request, "catalogo/numero.html", {"n": n, "resultado": resultado})


@login_required
def pendientes(request):
    return render(
        request,
        "catalogo/pendientes.html",
        {"pendientes": ConsultaPendiente.objects.filter(atendida=False)[:200],
         "atendidas_n": ConsultaPendiente.objects.filter(atendida=True).count()},
    )


@login_required
@require_POST
def pendiente_atender(request, pk):
    consulta = get_object_or_404(ConsultaPendiente, pk=pk)
    consulta.atendida = True
    consulta.save(update_fields=["atendida"])
    messages.success(request, "Consulta marcada como atendida.")
    return redirect("catalogo_pendientes")
