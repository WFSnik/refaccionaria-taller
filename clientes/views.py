from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from taller.roles import modulo_requerido
from taller.utils import pagina_form

from .forms import ClienteForm, VehiculoForm
from .models import Cliente, VehiculoCliente


@modulo_requerido("clientes")
def lista(request):
    q = request.GET.get("q", "").strip()
    clientes = Cliente.objects.annotate(vehiculos_n=Count("vehiculos", distinct=True)).order_by("nombre", "pk")
    if q:
        clientes = clientes.filter(
            Q(nombre__icontains=q) | Q(telefono__icontains=q) | Q(vehiculos__placas__icontains=q)
        ).distinct()
    pagina = Paginator(clientes, 25).get_page(request.GET.get("pagina"))
    filtros = request.GET.copy()
    filtros.pop("pagina", None)
    return render(request, "clientes/lista.html", {"pagina": pagina, "q": q, "filtros": filtros.urlencode()})


@modulo_requerido("clientes")
def crear(request):
    form = ClienteForm(request.POST or None)
    if form.is_valid():
        cliente = form.save()
        messages.success(request, f"Cliente {cliente} registrado. Ahora agrega su vehículo.")
        return redirect("clientes:vehiculo_crear", cliente.pk)
    return pagina_form(request, form, "Nuevo cliente", reverse("clientes:lista"))


@modulo_requerido("clientes")
def detalle(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk)
    vehiculos = cliente.vehiculos.prefetch_related("ordenes")
    return render(request, "clientes/detalle.html", {"cliente": cliente, "vehiculos": vehiculos})


@modulo_requerido("clientes")
def editar(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk)
    form = ClienteForm(request.POST or None, instance=cliente)
    if form.is_valid():
        form.save()
        messages.success(request, "Datos del cliente actualizados.")
        return redirect("clientes:detalle", cliente.pk)
    return pagina_form(request, form, f"Editar a {cliente}", reverse("clientes:detalle", args=[cliente.pk]))


@modulo_requerido("clientes")
def vehiculo_crear(request, cliente_pk):
    cliente = get_object_or_404(Cliente, pk=cliente_pk)
    form = VehiculoForm(request.POST or None)
    if form.is_valid():
        vehiculo = form.save(commit=False)
        vehiculo.cliente = cliente
        vehiculo.save()
        messages.success(request, f"Vehículo {vehiculo} agregado.")
        return redirect("clientes:detalle", cliente.pk)
    return pagina_form(request, form, f"Vehículo de {cliente}", reverse("clientes:detalle", args=[cliente.pk]))


@modulo_requerido("clientes")
def vehiculo_editar(request, pk):
    vehiculo = get_object_or_404(VehiculoCliente.objects.select_related("cliente"), pk=pk)
    form = VehiculoForm(request.POST or None, instance=vehiculo)
    if form.is_valid():
        form.save()
        messages.success(request, "Vehículo actualizado.")
        return redirect("clientes:detalle", vehiculo.cliente_id)
    return pagina_form(request, form, f"Editar {vehiculo}", reverse("clientes:detalle", args=[vehiculo.cliente_id]))
